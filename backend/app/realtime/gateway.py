"""Native WebSocket gateway for snapshots and pin commands."""
import asyncio
import anyio
from datetime import datetime
import json
import os
import time
from collections import deque
from uuid import UUID, uuid4
from typing import Literal, Annotated

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, ValidationError, field_validator, model_validator
from sqlalchemy import text

from app.api.auth import authenticated, auth_config
from app.auth.tokens import decode_access_token
from app.realtime.rooms import RoomError, envelope, reaction_groups
from app.rooms.moderation import Moderation, moderate
from app.concierge.preferences import ConstraintsUpdate, update_constraints

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
    splitMode: Literal['even','weighted'] = 'even'
    weights: dict[UUID, Annotated[StrictInt,Field(ge=0,le=2**31-1)]] = Field(default_factory=dict,max_length=50)

    @model_validator(mode='after')
    def valid_split(self):
        if self.splitMode=='weighted' and (not self.attendeeIds or set(self.weights)!=set(self.attendeeIds) or sum(self.weights.values())<=0):raise ValueError('weighted split requires attendees and positive weights')
        if self.splitMode=='even' and self.weights:raise ValueError('even split does not accept weights')
        return self


class ItemCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    commandId: UUID
    correlationId: UUID
    itemId: UUID
    expectedPositionVersion: int = Field(ge=1)


class Move(ItemCommand):
    dayIndex: int = Field(ge=0, le=365)
    startTime: datetime
    endTime: datetime


class Unlock(ItemCommand):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator('reason')
    @classmethod
    def valid_reason(cls,value):
        if not value.strip() or '\x00' in value:
            raise ValueError('invalid reason')
        try:
            value.encode('utf-8')
        except UnicodeEncodeError:
            raise ValueError('invalid reason') from None
        return value


class Chat(BaseModel):
    model_config = ConfigDict(extra='forbid')
    commandId: UUID
    correlationId: UUID
    body: str = Field(min_length=1, max_length=2000)

    @field_validator('body')
    @classmethod
    def valid_body(cls, value):
        if not value.strip() or '\x00' in value:
            raise ValueError('invalid message')
        try:
            value.encode('utf-8')
        except UnicodeEncodeError:
            raise ValueError('invalid message') from None
        return value


class Typing(BaseModel):
    model_config = ConfigDict(extra='forbid')
    isTyping: StrictBool


class Ping(BaseModel):
    model_config = ConfigDict(extra='forbid')
    clientSentAt: float = Field(ge=0, allow_inf_nan=False)
    nonce: UUID
    serverReceivedAt: None = None


class ChatBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str = Field(min_length=1, max_length=2000)


class Reaction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    commandId: UUID
    correlationId: UUID
    messageId: UUID
    emoji: Literal['👍', '❤️', '😂', '🎉']
    active: StrictBool


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
            if 'closeCode' in message:
                await socket.close(code=message['closeCode'])
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
            message = None
            try:
                message = json.loads(raw)
                if not isinstance(message,dict) or set(message) != {'event','payload'}:
                    raise ValueError()
                if message['event'] == 'trip.board.pin':
                    command = Pin.model_validate(message['payload'])
                    ack = await room.pin(actor,command)
                    queue.put_nowait(envelope('trip.command.ack',trip_id,ack))
                elif message['event'] in ('trip.board.move', 'trip.board.remove', 'trip.board.lock', 'trip.board.unlock'):
                    operation = message['event'].rsplit('.', 1)[-1]
                    command = ({'move':Move, 'unlock':Unlock}.get(operation, ItemCommand)).model_validate(message['payload'])
                    ack = await room.change_item(actor, command, operation)
                    queue.put_nowait(envelope('trip.command.ack', trip_id, ack))
                elif message['event'] in ('trip.vote.open','trip.vote.cast','trip.vote.start','trip.vote.submit'):
                    from app.voting.service import OpenVote,CastVote,open_vote,cast_vote
                    opening=message['event'] in ('trip.vote.open','trip.vote.start')
                    command=(OpenVote if opening else CastVote).model_validate(message['payload'])
                    ack=await (open_vote if opening else cast_vote)(room,actor,command)
                    queue.put_nowait(envelope('trip.command.ack',trip_id,ack))
                elif message['event']=='trip.board.split':
                    from app.budget.service import SplitUpdate,update_split
                    ack=await update_split(room,actor,SplitUpdate.model_validate(message['payload']))
                    queue.put_nowait(envelope('trip.command.ack',trip_id,ack))
                elif message['event'] == 'trip.chat.send':
                    command = Chat.model_validate(message['payload'])
                    ack = await room.send_chat(actor, command)
                    queue.put_nowait(envelope('trip.command.ack', trip_id, ack))
                elif message['event'] == 'trip.chat.typing':
                    command = Typing.model_validate(message['payload'])
                    await room.typing(actor, command.isTyping)
                elif message['event'] == 'trip.sync.ping':
                    command = Ping.model_validate(message['payload'])
                    received = int(time.time()*1000)
                    queue.put_nowait(envelope('trip.sync.pong', trip_id, {'clientSentAt':command.clientSentAt,
                        'nonce':str(command.nonce),'serverReceivedAt':received,'serverSentAt':int(time.time()*1000)}))
                elif message['event'] == 'trip.chat.react':
                    command = Reaction.model_validate(message['payload'])
                    ack = await room.react_chat(actor, command)
                    queue.put_nowait(envelope('trip.command.ack',trip_id,ack))
                elif message['event'] == 'trip.moderation.command':
                    command = Moderation.model_validate(message['payload'])
                    ack = await moderate(room, actor, command)
                    queue.put_nowait(envelope('trip.command.ack',trip_id,ack))
                elif message['event'] == 'trip.constraints.update':
                    command = ConstraintsUpdate.model_validate(message['payload'])
                    ack = await update_constraints(room,actor,command)
                    queue.put_nowait(envelope('trip.command.ack',trip_id,ack))
                elif message['event'] == 'trip.snapshot.request' and isinstance(message['payload'],dict):
                    async with room.lock:
                        queue.put_nowait(envelope('trip.snapshot',trip_id,await room.snapshot_locked(actor)))
                else:
                    raise ValueError()
            except RoomError as exc:
                if exc.code == 'STALE_POSITION_VERSION':
                    queue.put_nowait(envelope('trip.board.edit.conflict', trip_id, exc.details))
                else:
                    details = {'code':exc.code}
                    if exc.details:
                        details.update(exc.details)
                    try:
                        details['commandId'] = str(UUID(str(message['payload']['commandId'])))
                    except (KeyError, TypeError, ValueError):
                        pass
                    queue.put_nowait(envelope('trip.command.error',trip_id,details))
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
        # TestClient and real disconnects may cancel the handler while cleanup
        # awaits PostgreSQL. Finish presence cleanup even in that cancel scope.
        with anyio.CancelScope(shield=True):
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


@router.get('/api/v1/trips/{trip_id}/chat')
async def chat_history(trip_id: UUID, request: Request, before: int | None = Query(default=None, ge=1),
                       actor=Depends(authenticated)):
    async with request.app.state.engine.connect() as conn:
        member = (await conn.execute(text("SELECT 1 FROM memberships WHERE trip_id=:trip AND user_id=:uid AND status='active'"),
                                     {'trip':trip_id,'uid':actor['user_id']})).first()
        if not member:
            raise HTTPException(404, 'Trip unavailable')
        rows = (await conn.execute(text('''SELECT id,user_id,body,created_at,room_seq FROM chat_messages
            WHERE trip_id=:trip AND room_seq<COALESCE(CAST(:before AS bigint),9223372036854775807)
            ORDER BY room_seq DESC LIMIT 51'''),
            {'trip':trip_id,'before':before})).mappings().all()
        reactions = await reaction_groups(conn, [row['id'] for row in rows[:50]])
    has_more = len(rows) > 50
    rows = rows[:50]
    return {'items':[{'messageId':str(m['id']),'userId':str(m['user_id']),'body':m['body'],
                      'tsSeconds':int(m['created_at'].timestamp()),'roomSeq':m['room_seq'],
                      'reactions':reactions.get(str(m['id']),[])} for m in reversed(rows)],
            'nextCursor':str(rows[-1]['room_seq']) if has_more else None}


@router.post('/api/v1/trips/{trip_id}/moderation')
async def http_moderate(trip_id: UUID, command: Moderation, request: Request, actor=Depends(authenticated)):
    async with request.app.state.engine.connect() as conn:
        exists = (await conn.execute(text("SELECT 1 FROM memberships WHERE trip_id=:trip AND user_id=:uid AND status='active'"),
                    {'trip':trip_id,'uid':actor['user_id']})).first()
    if not exists:
        raise HTTPException(404, 'Trip unavailable')
    try:
        return await moderate(request.app.state.rooms.get(trip_id),actor,command)
    except RoomError as exc:
        status = 404 if exc.code == 'NOT_FOUND' else 403 if exc.code == 'FORBIDDEN' else 503 if exc.code == 'PERSISTENCE_DEGRADED' else 409
        raise HTTPException(status, {'code':exc.code,**(exc.details or {})}) from None


@router.post('/api/v1/trips/{trip_id}/chat', status_code=201)
async def http_chat(trip_id: UUID, body: ChatBody, request: Request,
                    idempotency_key: UUID | None = Header(default=None, alias='Idempotency-Key'),
                    actor=Depends(authenticated)):
    async with request.app.state.engine.connect() as conn:
        member = (await conn.execute(text("SELECT 1 FROM memberships WHERE trip_id=:trip AND user_id=:uid AND status='active'"),
                                     {'trip':trip_id,'uid':actor['user_id']})).first()
    if not member:
        raise HTTPException(404, 'Trip unavailable')
    key = idempotency_key or uuid4()
    try:
        command = Chat(commandId=key, correlationId=key, body=body.body)
        result = await request.app.state.rooms.get(trip_id).send_chat(actor, command)
        return result['message']
    except ValidationError:
        raise HTTPException(422, 'Invalid message') from None
    except RoomError as exc:
        status = 403 if exc.code == 'FORBIDDEN' else 409 if exc.code == 'COMMAND_ID_REUSE' else 503
        raise HTTPException(status, exc.code) from None
