"""Test-only synchronization profiling. Loaded explicitly by browser_clean_setup."""
from contextvars import ContextVar
import time

from sqlalchemy import event
import app.main as application
from app.realtime import gateway
from app.realtime.rooms import Room
from browser_server import app

current = ContextVar('sync_measurement', default=None)
profiles = []
original_engine = application.create_async_engine
original_actor = gateway.socket_actor
original_init = Room.__init__
original_publish = Room.publish


class MeasuredLock:
    def __init__(self, lock):
        self.lock = lock

    async def __aenter__(self):
        started = time.perf_counter()
        await self.lock.acquire()
        record = current.get()
        if record is not None:
            record['lockWaitMs'] += (time.perf_counter() - started) * 1000
        return self

    async def __aexit__(self, *args):
        self.lock.release()

    def locked(self):
        return self.lock.locked()


def engine(*args, **kwargs):
    result = original_engine(*args, **kwargs)

    @event.listens_for(result.sync_engine, 'before_cursor_execute')
    def before(conn, cursor, statement, parameters, context, executemany):
        context.sync_measure_started = time.perf_counter()

    @event.listens_for(result.sync_engine, 'after_cursor_execute')
    def after(conn, cursor, statement, parameters, context, executemany):
        record = current.get()
        if record is not None:
            record['sqlMs'] += (time.perf_counter() - context.sync_measure_started) * 1000
            record['queries'] += 1

    return result


async def actor(*args, **kwargs):
    record = {'started': time.perf_counter(), 'authMs': 0, 'lockWaitMs': 0, 'sqlMs': 0, 'queries': 0}
    current.set(record)
    result = await original_actor(*args, **kwargs)
    record['authMs'] = (time.perf_counter() - record['started']) * 1000
    return result


def initialize(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    self.lock = MeasuredLock(self.lock)


def publish(self, message):
    record = current.get()
    if record is not None and message['event'] == 'trip.board.update':
        profiles.append({key: value for key, value in record.items() if key != 'started'} | {
            'commandId': message['payload']['commandId'],
            'serverMs': (time.perf_counter() - record['started']) * 1000,
        })
    return original_publish(self, message)


application.create_async_engine = engine
gateway.socket_actor = actor
Room.__init__ = initialize
Room.publish = publish


@app.get('/__test/sync-profile')
async def measurements():
    return profiles
