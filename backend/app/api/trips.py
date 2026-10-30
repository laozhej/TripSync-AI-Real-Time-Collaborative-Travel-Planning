"""Trip creation and invitation redemption for the first slice."""
import asyncio
import base64
import hashlib
import json
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Literal
from sqlalchemy import text
from cryptography.fernet import Fernet, InvalidToken
from app.api.auth import authenticated, auth_config
from app.auth.policy import Capability, Membership, Role, permitted

router = APIRouter(prefix="/api/v1/trips", tags=["trips"])
_locks: dict[str, asyncio.Lock] = {}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateTrip(Strict):
    destination: str = Field(min_length=1, max_length=200)
    startDate: date
    endDate: date
    totalBudget: str
    currency: str = Field(pattern="^EUR$")
    maxParticipants: int = Field(ge=2, le=50)

    @field_validator("totalBudget")
    @classmethod
    def budget(cls, value):
        try:
            amount = Decimal(value)
            if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2 or amount > Decimal('9999999999'):
                raise ValueError()
        except (ValueError, InvalidOperation):
            raise ValueError("invalid budget") from None
        return value

    @model_validator(mode="after")
    def dates(self):
        if self.endDate < self.startDate:
            raise ValueError("endDate precedes startDate")
        return self


class JoinTrip(Strict):
    inviteCode: str = Field(min_length=20, max_length=256)


class CreateInvite(Strict):
    role: Literal['viewer', 'planner']
    maxUses: int = Field(ge=1, le=49)
    expiresAt: datetime

    @field_validator('expiresAt')
    @classmethod
    def expiration(cls, value):
        if value.utcoffset() is None or value <= datetime.now(timezone.utc):
            raise ValueError('expiresAt must be an offset-aware future time')
        return value


def key_value(value: str | None) -> UUID:
    try:
        return UUID(value or "")
    except ValueError:
        raise HTTPException(422, "Idempotency-Key must be a UUID") from None


def fingerprint(body):
    return hashlib.sha256(body.model_dump_json().encode()).hexdigest()


async def prior(conn, actor, key, route, body_hash):
    await conn.execute(text("DELETE FROM http_idempotency WHERE user_id=:uid AND key=:key AND created_at < now() - interval '24 hours'"),
                       {"uid": actor['user_id'], "key": key})
    row = (await conn.execute(text("SELECT route,body_hash,response FROM http_idempotency WHERE user_id=:uid AND key=:key"),
                              {"uid": actor['user_id'], "key": key})).mappings().first()
    if row:
        if row['route'] != route or row['body_hash'] != body_hash:
            raise HTTPException(409, "Idempotency key reused with different request")
        try:
            return json.loads(cipher().decrypt(row['response']['encrypted'].encode()))
        except (InvalidToken, KeyError, ValueError):
            raise HTTPException(503, "Saved request result unavailable") from None
    return None


async def remember(conn, actor, key, route, body_hash, result):
    encrypted = cipher().encrypt(json.dumps(result).encode()).decode()
    await conn.execute(text("INSERT INTO http_idempotency (user_id,key,route,body_hash,response) VALUES (:uid,:key,:route,:hash,CAST(:response AS jsonb))"),
                       dict(uid=actor['user_id'], key=key, route=route, hash=body_hash, response=json.dumps({"encrypted":encrypted})))


def cipher():
    key = auth_config()['key'].encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b'tripsync-idempotency-v1:' + key).digest()))


@router.post("", status_code=201)
async def create(body: CreateTrip, request: Request, actor=Depends(authenticated), idempotency_key: str | None = Header(default=None)):
    key, body_hash = key_value(idempotency_key), fingerprint(body)
    lock = _locks.setdefault('user:' + str(actor['user_id']), asyncio.Lock())
    async with lock, request.app.state.engine.begin() as conn:
        existing = await prior(conn, actor, key, 'create', body_hash)
        if existing:
            return existing
        dataset = (await conn.execute(text("SELECT id,timezone,currency FROM datasets WHERE destination=:name AND status='active'"), {"name":body.destination})).mappings().first()
        if not dataset:
            raise HTTPException(422, "Destination has no active dataset")
        if dataset['currency'] != body.currency:
            raise HTTPException(422, "Currency does not match dataset")
        trip, invite, epoch = uuid4(), uuid4(), uuid4()
        code = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        await conn.execute(text("""INSERT INTO trips (id,leader_user_id,dataset_id,destination,timezone,start_date,end_date,
            currency,total_budget_minor,max_participants,room_epoch) VALUES (:id,:leader,:dataset,:destination,:timezone,
            :start,:end,:currency,:budget,:capacity,:epoch)"""), dict(id=trip, leader=actor['user_id'], dataset=dataset['id'],
            destination=body.destination, timezone=dataset['timezone'], start=body.startDate, end=body.endDate,
            currency=body.currency, budget=int(Decimal(body.totalBudget)*100), capacity=body.maxParticipants, epoch=epoch))
        await conn.execute(text("INSERT INTO memberships (trip_id,user_id,role) VALUES (:trip,:uid,'leader')"), dict(trip=trip, uid=actor['user_id']))
        await conn.execute(text("""INSERT INTO invites (id,trip_id,code_hash,assigned_role,expires_at,max_uses)
            VALUES (:id,:trip,:hash,'planner',:expiry,:uses)"""), dict(id=invite, trip=trip,
            hash=hashlib.sha256(code.encode()).hexdigest(), expiry=now+timedelta(days=7), uses=body.maxParticipants-1))
        result = {"tripId":str(trip), "inviteCode":code, "status":"drafting", "leaderUserId":str(actor['user_id']), "createdAt":now.isoformat()}
        await remember(conn, actor, key, 'create', body_hash, result)
        return result


@router.post("/join")
async def join(body: JoinTrip, request: Request, actor=Depends(authenticated), idempotency_key: str | None = Header(default=None)):
    key, body_hash = key_value(idempotency_key), fingerprint(body)
    code_hash = hashlib.sha256(body.inviteCode.encode()).hexdigest()
    async with request.app.state.engine.connect() as conn:
        trip_id = (await conn.execute(text("SELECT trip_id FROM invites WHERE code_hash=:hash"), {"hash":code_hash})).scalar_one_or_none()
    if not trip_id:
        raise HTTPException(404, "Invite unavailable")
    room = request.app.state.rooms.get(trip_id)
    await room.load()
    user_lock = _locks.setdefault('user:' + str(actor['user_id']), asyncio.Lock())
    lock = _locks.setdefault('trip:' + str(trip_id), asyncio.Lock())
    async with user_lock, lock, room.lock, room.transaction_locked() as conn:
        existing = await prior(conn, actor, key, 'join', body_hash)
        if existing:
            return existing
        invite = (await conn.execute(text("""SELECT i.id,i.assigned_role,i.expires_at,i.max_uses,i.uses,i.revoked_at,
            t.room_locked,t.max_participants,t.status FROM invites i JOIN trips t ON t.id=i.trip_id WHERE i.code_hash=:hash"""),
            {"hash":code_hash})).mappings().one()
        member = (await conn.execute(text("SELECT role,status FROM memberships WHERE trip_id=:trip AND user_id=:uid"),
                                     dict(trip=trip_id, uid=actor['user_id']))).mappings().first()
        if member and member['status'] == 'active':
            result = {"tripId":str(trip_id), "role":member['role']}
        else:
            if member or invite['room_locked'] or invite['status'] == 'finalized' or invite['revoked_at'] or invite['expires_at'] <= datetime.now(timezone.utc) or invite['uses'] >= invite['max_uses']:
                raise HTTPException(403, "Invite unavailable")
            count = (await conn.execute(text("SELECT count(*) FROM memberships WHERE trip_id=:trip AND status='active'"), {"trip":trip_id})).scalar_one()
            if count >= invite['max_participants']:
                raise HTTPException(409, "Room is full")
            await conn.execute(text("INSERT INTO memberships (trip_id,user_id,role) VALUES (:trip,:uid,:role)"),
                               dict(trip=trip_id, uid=actor['user_id'], role=invite['assigned_role']))
            await conn.execute(text("UPDATE invites SET uses=uses+1 WHERE id=:id"), {"id":invite['id']})
            await conn.execute(text("UPDATE trips SET status='live', state_version=state_version+1 WHERE id=:trip"), {"trip":trip_id})
            result = {"tripId":str(trip_id), "role":invite['assigned_role']}
        await remember(conn, actor, key, 'join', body_hash, result)
        return result


@router.get("/{trip_id}")
async def get_trip(trip_id: UUID, request: Request, actor=Depends(authenticated)):
    async with request.app.state.engine.connect() as conn:
        trip = (await conn.execute(text("""SELECT t.id,t.destination,t.start_date,t.end_date,t.currency,t.total_budget_minor,
            t.status,t.room_locked,t.max_participants,t.state_version,t.room_seq,t.committed_seq,m.role,m.can_pin
            FROM trips t JOIN memberships m ON m.trip_id=t.id
            WHERE t.id=:trip AND m.user_id=:uid AND m.status='active'"""),
            dict(trip=trip_id, uid=actor['user_id']))).mappings().first()
        if not trip:
            raise HTTPException(404, "Trip unavailable")
        members = (await conn.execute(text("""SELECT m.user_id,m.role,m.can_pin,u.display_name
            FROM memberships m JOIN users u ON u.id=m.user_id
            WHERE m.trip_id=:trip AND m.status='active' ORDER BY m.joined_at,m.user_id"""),
            {"trip": trip_id})).mappings().all()
    return {"tripId":str(trip['id']), "destination":trip['destination'],
            "startDate":trip['start_date'].isoformat(), "endDate":trip['end_date'].isoformat(),
            "currency":trip['currency'], "totalBudgetMinor":trip['total_budget_minor'],
            "status":trip['status'], "roomLocked":trip['room_locked'], "maxParticipants":trip['max_participants'],
            "stateVersion":trip['state_version'], "roomSeq":trip['room_seq'], "committedSeq":trip['committed_seq'],
            "role":trip['role'], "canPin":trip['can_pin'],
            "members":[{"userId":str(m['user_id']), "displayName":m['display_name'], "role":m['role'], "canPin":m['can_pin']} for m in members]}


async def leader_access(conn, trip_id, user_id):
    row = (await conn.execute(text("""SELECT role FROM memberships WHERE trip_id=:trip AND user_id=:uid
        AND status='active'"""), {'trip':trip_id, 'uid':user_id})).mappings().first()
    if not row:
        raise HTTPException(404, 'Trip unavailable')
    if not permitted(Capability.LEAD, is_admin=False, membership=Membership(Role(row['role']))):
        raise HTTPException(403, 'Leader permission required')


@router.post('/{trip_id}/invites', status_code=201)
async def create_invite(trip_id: UUID, body: CreateInvite, request: Request, actor=Depends(authenticated)):
    async with request.app.state.engine.connect() as conn:
        await leader_access(conn, trip_id, actor['user_id'])
    room = request.app.state.rooms.get(trip_id)
    await room.load()
    async with room.lock, room.transaction_locked() as conn:
        await leader_access(conn, trip_id, actor['user_id'])
        invite_id, code = uuid4(), secrets.token_urlsafe(32)
        await conn.execute(text("""INSERT INTO invites (id,trip_id,code_hash,assigned_role,expires_at,max_uses)
            VALUES (:id,:trip,:hash,:role,:expires,:uses)"""),
            {'id':invite_id, 'trip':trip_id, 'hash':hashlib.sha256(code.encode()).hexdigest(),
             'role':body.role, 'expires':body.expiresAt, 'uses':body.maxUses})
    return {'inviteId':str(invite_id), 'inviteCode':code, 'role':body.role,
            'expiresAt':body.expiresAt.isoformat(), 'maxUses':body.maxUses}


@router.delete('/{trip_id}/invites/{invite_id}', status_code=204)
async def revoke_invite(trip_id: UUID, invite_id: UUID, request: Request, actor=Depends(authenticated)):
    async with request.app.state.engine.connect() as conn:
        await leader_access(conn, trip_id, actor['user_id'])
    room = request.app.state.rooms.get(trip_id)
    await room.load()
    async with room.lock, room.transaction_locked() as conn:
        await leader_access(conn, trip_id, actor['user_id'])
        result = await conn.execute(text("""UPDATE invites SET revoked_at=COALESCE(revoked_at,now())
            WHERE id=:id AND trip_id=:trip RETURNING id"""), {'id':invite_id, 'trip':trip_id})
        if not result.first():
            raise HTTPException(404, 'Invite unavailable')
