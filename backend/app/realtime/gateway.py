"""Native WebSocket gateway for snapshots and pin commands."""
import asyncio
from datetime import datetime
import json
import os
import time
from collections import deque
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import text

from app.api.auth import authenticated, auth_config
from app.auth.tokens import decode_access_token
from app.realtime.rooms import RoomError, envelope

router = APIRouter()


class Pin(BaseModel):
    model_config = ConfigDict(extra='forbid')
    commandId: UUID
    correlationId: UUID
    venueId: UUID
    dayIndex: int = Field(ge=0, le=365)
    startTime: datetime
    endTime: datetime
    attendeeIds: list[UUID] = Field(default_factory=list, max_length=50)
    splitMode: str = Field(default='even', pattern='^even$')


async def socket_actor(socket, trip_id, token):
    try:
        uid, sid = decode_access_token(token, **auth_config())
    except (jwt.InvalidTokenError, ValueError, HTTPException):
        return None
    async with socket.app.state.engine.connect() as conn:
        found = (await conn.execute(text("""SELECT 1 FROM auth_sessions s JOIN memberships m ON m.user_id=s.user_id
            WHERE s.id=:sid AND s.user_id=:uid AND s.revoked_at IS NULL AND s.expires_at>now()
            AND m.trip_id=:trip AND m.status='active'"""), dict(sid=sid,uid=uid,trip=trip_id))).first()
    return {"user_id":uid,"session_id":sid} if found else None


@router.websocket('/ws/v1/trips/{trip_id}')
async def socket_room(socket: WebSocket, trip_id: UUID):
    origin = socket.headers.get('origin')
    allowed = {v.strip() for v in os.getenv('ALLOWED_ORIGINS','').split(',') if v.strip()}
    if origin and origin not in allowed:
        await socket.close(code=1008)
        return
    authorization = socket.headers.get('authorization','')
    token = authorization[7:] if authorization.startswith('Bearer ') else socket.cookies.get('tripsync_ws','')
    actor = await socket_actor(socket, trip_id, token)
    if not actor:
        await socket.close(code=1008)
        return
    room = socket.app.state.rooms.get(trip_id)
    try:
        queue = await room.subscribe(actor)
    except RoomError:
        await socket.close(code=1008)
        return
    await socket.accept()
    sessions = socket.app.state.socket_sessions
    sessions.setdefault(actor['session_id'], set()).add(socket)

    async def sender():
        while True:
            message = await queue.get()
            if message is None:
                await socket.close(code=1013)
                return
            await socket.send_json(message)

    sender_task = asyncio.create_task(sender())
    recent_commands = deque()
    try:
        while not sender_task.done():
            # The timeout also closes idle sockets after token expiry/revocation.
            try:
                raw = await asyncio.wait_for(socket.receive_text(), timeout=5)
            except asyncio.TimeoutError:
                if not await socket_actor(socket,trip_id,token):
                    await socket.close(code=1008)
                    break
                continue
            if len(raw.encode('utf-8')) > 65536:
                await socket.close(code=1009)
                break
            now = time.monotonic()
            while recent_commands and recent_commands[0] <= now - 1:
                recent_commands.popleft()
            if len(recent_commands) >= 40:
                await socket.close(code=1008)
                break
            recent_commands.append(now)
            if not await socket_actor(socket,trip_id,token):
                await socket.close(code=1008)
                break
            try:
                message = json.loads(raw)
                if not isinstance(message,dict) or set(message) != {'event','payload'}:
                    raise ValueError()
                if message['event'] == 'trip.board.pin':
                    command = Pin.model_validate(message['payload'])
                    ack = await room.pin(actor,command)
                    queue.put_nowait(envelope('trip.command.ack',trip_id,ack))
                elif message['event'] == 'trip.snapshot.request' and isinstance(message['payload'],dict):
                    async with room.lock:
                        queue.put_nowait(envelope('trip.snapshot',trip_id,await room.snapshot_locked(actor)))
                else:
                    raise ValueError()
            except RoomError as exc:
                queue.put_nowait(envelope('trip.command.error',trip_id,{'code':exc.code}))
            except (ValueError, ValidationError, TypeError):
                queue.put_nowait(envelope('trip.command.error',trip_id,{'code':'INVALID_COMMAND'}))
            except asyncio.QueueFull:
                await socket.close(code=1013)
                break
    except WebSocketDisconnect:
        pass
    finally:
        sender_task.cancel()
        await asyncio.gather(sender_task,return_exceptions=True)
        await room.unsubscribe(queue)
        active = sessions.get(actor['session_id'])
        if active is not None:
            active.discard(socket)
            if not active:
                sessions.pop(actor['session_id'], None)


@router.post('/api/v1/trips/{trip_id}/items',status_code=201)
async def http_pin(trip_id: UUID, command: Pin, request: Request, actor=Depends(authenticated)):
    async with request.app.state.engine.connect() as conn:
        member = (await conn.execute(text("SELECT 1 FROM memberships WHERE trip_id=:trip AND user_id=:uid AND status='active'"),
                                     {"trip":trip_id,"uid":actor['user_id']})).first()
    if not member:
        raise HTTPException(404, "Trip unavailable")
    try:
        return await request.app.state.rooms.get(trip_id).pin(actor,command)
    except RoomError as exc:
        status = 404 if exc.code == 'NOT_FOUND' else 403 if exc.code == 'FORBIDDEN' else 503 if exc.code in ('PERSISTENCE_DEGRADED','ROOM_BACKPRESSURE') else 409 if exc.code == 'COMMAND_ID_REUSE' else 422
        raise HTTPException(status, exc.code) from None
