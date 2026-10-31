"""Run the two-browser smoke test against a disposable local database."""
import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import httpx
from urllib.request import urlopen
from uuid import uuid4

from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[2]
url = make_url(dotenv_values(ROOT / '.env')['DATABASE_URL'])
name = 'tripsync_browser_' + uuid4().hex
assert name.isidentifier() and name.startswith('tripsync_browser_')
env = os.environ.copy()
env['PYTHONPATH'] = str(ROOT / 'backend')
env['DATABASE_URL'] = url.set(database=name).render_as_string(hide_password=False)
env['JWT_SIGNING_KEY'] = 'temporary-browser-test-key-' + uuid4().hex
env['ALLOWED_ORIGINS'] = 'http://127.0.0.1:5173'
env['BROWSER_SHORT_ACCESS'] = '1'


async def main():
    for port in (8000, 5173):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    # Explicitly preload the local model. Production requests keep their 2.5-s
    # deadline; this setup operation is not counted as inference latency.
    config=dotenv_values(ROOT / '.env')
    model_url=env.get('CONCIERGE_MODEL_URL') or config.get('CONCIERGE_MODEL_URL') or 'http://127.0.0.1:11434'
    from urllib.parse import urlsplit
    parsed=urlsplit(model_url)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','::1') or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
        raise RuntimeError('Browser test requires local inference')
    warm=httpx.post(model_url.rstrip('/')+'/api/chat',json={'model':env.get('CONCIERGE_MODEL') or config.get('CONCIERGE_MODEL') or 'qwen2.5:1.5b',
        'messages':[],'stream':False,'keep_alive':'5m'},timeout=60,trust_env=False)
    warm.raise_for_status()
    admin = create_async_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT')
    processes = []
    created = False
    try:
        async with admin.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        for command in ([sys.executable, '-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', 'head'],
                        [sys.executable, '-m', 'app.cli', 'import-dataset', 'data/destinations/lisbon.json']):
            subprocess.run(command, cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        processes.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'browser_server:app', '--app-dir', 'backend/tests',
            '--host', '127.0.0.1', '--port', '8000', '--workers', '1'], cwd=ROOT, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags))
        processes.append(subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1'],
            cwd=ROOT / 'frontend', env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags))
        for address in ('http://127.0.0.1:8000/api/v1/health/ready', 'http://127.0.0.1:5173/'):
            for _ in range(40):
                if any(process.poll() is not None for process in processes):
                    raise RuntimeError('Test server exited')
                try:
                    with urlopen(address, timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(.25)
            else:
                raise RuntimeError('Test server did not become ready')
        subprocess.run([sys.executable, 'backend/tests/browser_phase1.py'], cwd=ROOT, env=env, check=True, timeout=90)
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(timeout=10)
        if created:
            async with admin.connect() as conn:
                await conn.execute(text(f'DROP DATABASE "{name}"'))
            print('Disposable browser database removed')
        await admin.dispose()


asyncio.run(main())
