"""Verify migrations/import/tests in a newly created disposable local database.

Requires a PostgreSQL role with CREATEDB and a private DATABASE_URL in .env.
The randomly named database created by this script is dropped in finally.
"""
import asyncio
import os
import re
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[2]
config = dotenv_values(ROOT / '.env')
url = make_url(config['DATABASE_URL'])
name = 'tripsync_verify_' + uuid4().hex
assert name.startswith('tripsync_verify_') and len(name) == len('tripsync_verify_')+32 and name.isidentifier()
admin = create_async_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT')
created = False


def run(label, args, env):
    try:
        result = subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True, timeout=180)
    except subprocess.TimeoutExpired as exc:
        diagnostic=(exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout,bytes) else (exc.stdout or '')
        for secret in (env.get('DATABASE_URL'),env.get('TEST_DATABASE_URL'),config.get('JWT_SIGNING_KEY')):
            if secret:diagnostic=diagnostic.replace(secret,'[REDACTED]')
        diagnostic=re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[REDACTED-JWT]',diagnostic)
        (ROOT/'.local'/'pytest-timeout.log').write_text(diagnostic,encoding='utf-8')
        raise RuntimeError(label+' timed out; sanitized output in .local/pytest-timeout.log') from None
    if result.returncode:
        print(label, 'failed, exit', result.returncode)
        if label == 'tests':
            for line in result.stdout.splitlines():
                if line.startswith('FAILED '): print(line.split(' - ')[0])
            diagnostic=result.stdout+'\n'+result.stderr
            for secret in (env.get('DATABASE_URL'),env.get('TEST_DATABASE_URL'),config.get('JWT_SIGNING_KEY')):
                if secret: diagnostic=diagnostic.replace(secret,'[REDACTED]')
            diagnostic=re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[REDACTED-JWT]',diagnostic)
            (ROOT/'.local').mkdir(exist_ok=True)
            (ROOT/'.local'/'pytest-failure.log').write_text(diagnostic,encoding='utf-8')
        raise RuntimeError(label + ' failed (details suppressed to protect local configuration)')
    if label == 'tests':
        last = [line for line in result.stdout.splitlines() if 'passed' in line]
        print('tests:', last[-1] if last else 'completed')
    else:
        print(label, 'succeeded')


async def main():
    global created
    try:
        async with admin.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        env = os.environ.copy()
        env['PYTHONPATH'] = str(ROOT / 'backend')
        env['DATABASE_URL'] = url.set(database=name).render_as_string(hide_password=False)
        env['TEST_DATABASE_URL'] = env['DATABASE_URL']
        run('migration', [sys.executable, '-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', 'head'], env)
        run('dataset import', [sys.executable, '-m', 'app.cli', 'import-dataset', 'data/destinations/lisbon.json'], env)
        run('Indian dataset import', [sys.executable, '-m', 'app.cli', 'import-dataset', 'data/destinations/bengaluru.json'], env)
        run('tests', [sys.executable, '-m', 'pytest', *(sys.argv[1:] or ['backend/tests']), '-q'], env)
    finally:
        if created:
            async with admin.connect() as conn:
                await conn.execute(text(f'DROP DATABASE "{name}"'))
            print('Disposable verification database removed')
        await admin.dispose()

asyncio.run(main())
