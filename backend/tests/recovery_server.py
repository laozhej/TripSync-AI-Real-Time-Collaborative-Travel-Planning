"""Test-only server factory to hold the normal flusher at a reproducible crash boundary.

Production entry point remains app.main:app; this module is never imported there.
"""
import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
from app.main import app

original=app.router.lifespan_context
ROOT=Path(__file__).resolve().parents[2]

@asynccontextmanager
async def lifespan(application):
    async with original(application):
        gate=Path(os.environ['RECOVERY_FLUSH_GATE']).resolve()
        if not gate.is_relative_to((ROOT/'.local').resolve()): raise RuntimeError('invalid test gate path')
        rooms=application.state.rooms
        rooms.task.cancel()
        await asyncio.gather(rooms.task,return_exceptions=True)
        async def gated():
            while not gate.exists(): await asyncio.sleep(.01)
            await rooms.run()
        rooms.task=asyncio.create_task(gated())
        yield

app.router.lifespan_context=lifespan
