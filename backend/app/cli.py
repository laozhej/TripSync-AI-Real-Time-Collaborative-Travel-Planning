"""Local operator commands."""
import argparse
import asyncio
import os
import secrets
from pathlib import Path

from dotenv import dotenv_values, load_dotenv, set_key
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.datasets.importer import import_initial


async def run(path):
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    url = os.getenv("DATABASE_URL", "")
    if not url.startswith("postgresql+asyncpg://"):
        raise RuntimeError("DATABASE_URL must use postgresql+asyncpg")
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        dataset_id = await import_initial(engine, path)
        print(f"Imported initial dataset {dataset_id}")
    finally:
        await engine.dispose()


def init_local_key(path=None):
    path = path or Path(__file__).resolve().parents[2] / '.env'
    if not path.exists():
        raise RuntimeError('Create .env from .env.example first')
    if dotenv_values(path).get('JWT_SIGNING_KEY'):
        print('Existing signing key retained')
        return
    set_key(str(path), 'JWT_SIGNING_KEY', secrets.token_urlsafe(48))
    print('Generated local signing key')


async def create_admin():
    """Promote an existing registered user, only when explicitly run locally."""
    load_dotenv(Path(__file__).resolve().parents[2] / '.env')
    url = os.getenv('DATABASE_URL', '')
    if not url.startswith('postgresql+asyncpg://'):
        raise RuntimeError('DATABASE_URL must use postgresql+asyncpg')
    email = input('Email of existing account to grant Admin: ').strip().casefold()
    if not email or len(email) > 320:
        raise ValueError('Invalid account')
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text('UPDATE users SET is_admin=true WHERE normalized_email=:email RETURNING id'), {'email':email})
            if result.first() is None:
                raise ValueError('Account not found')
        print('Admin privilege granted to existing account')
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["import-dataset", "init-local-key", "create-admin"])
    parser.add_argument("path", type=Path, nargs='?')
    args = parser.parse_args()
    if args.command == 'import-dataset':
        if args.path is None:
            parser.error('import-dataset requires a path')
        asyncio.run(run(args.path))
    elif args.command == 'init-local-key':
        init_local_key()
    else:
        asyncio.run(create_admin())


if __name__ == "__main__":
    main()
