"""TripSync application entry point."""
from contextlib import asynccontextmanager
import asyncio
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.api.auth import router as auth_router
from app.api.catalog import router as catalog_router
from app.api.trips import router as trips_router
from app.realtime.gateway import router as realtime_router
from app.realtime.rooms import RoomError, RoomManager

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    url = os.getenv("DATABASE_URL")
    if not url or not url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("DATABASE_URL must use postgresql+asyncpg")
    app.state.engine = create_async_engine(url, pool_pre_ping=True)
    app.state.socket_sessions = {}
    app.state.rooms = RoomManager(app.state.engine)
    app.state.rooms.task = asyncio.create_task(app.state.rooms.run())
    try:
        yield
    finally:
        await app.state.rooms.close()
        await app.state.engine.dispose()

app = FastAPI(title="TripSync AI", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(catalog_router)
app.include_router(trips_router)
app.include_router(realtime_router)

@app.exception_handler(RoomError)
async def room_error_handler(request, exc):
    return JSONResponse(status_code=503, content={"detail":"Room persistence unavailable"})

@app.get("/api/v1/health/live")
async def live():
    return {"status": "ok"}

@app.get("/api/v1/health/ready")
async def ready():
    try:
        async with app.state.engine.connect() as connection:
            revision = (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalar_one_or_none()
    except Exception:
        raise HTTPException(status_code=503, detail="Database or schema unavailable") from None
    if revision != "0008_venue_search" or not app.state.rooms.task or app.state.rooms.task.done() or any(room.frozen for room in app.state.rooms.rooms.values()):
        raise HTTPException(status_code=503, detail="Schema or room service not ready")
    return {"status": "ok"}


@app.get("/api/v1/health/gateway")
async def gateway_health():
    if not app.state.rooms.task or app.state.rooms.task.done() or any(room.frozen for room in app.state.rooms.rooms.values()):
        raise HTTPException(status_code=503, detail="Room service unavailable")
    return {"status": "ok"}
