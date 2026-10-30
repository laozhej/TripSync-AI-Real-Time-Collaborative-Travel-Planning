"""Opt-in two-browser smoke test. Uses disposable PostgreSQL and removes its own records."""
import asyncio
import os
import re
import secrets
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv(Path(__file__).resolve().parents[2] / '.env')
suffix = secrets.token_hex(12)
emails = [f'leader-{suffix}@example.invalid', f'planner-{suffix}@example.invalid']
password = 'browser test password only'

async def cleanup():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    try:
        async with engine.begin() as conn:
            ids = (await conn.execute(text('SELECT id FROM users WHERE normalized_email=ANY(:emails)'), {'emails':emails})).scalars().all()
            if not ids:
                return
            trips = (await conn.execute(text('SELECT id FROM trips WHERE leader_user_id=ANY(:ids)'), {'ids':ids})).scalars().all()
            for trip in trips:
                await conn.execute(text('DELETE FROM item_attendees WHERE item_id IN (SELECT id FROM itinerary_items WHERE trip_id=:trip)'), {'trip':trip})
                for table in ('room_events','itinerary_items','invites','memberships'):
                    await conn.execute(text(f'DELETE FROM {table} WHERE trip_id=:trip'), {'trip':trip})
                await conn.execute(text('DELETE FROM trips WHERE id=:trip'), {'trip':trip})
            await conn.execute(text('DELETE FROM http_idempotency WHERE user_id=ANY(:ids)'), {'ids':ids})
            await conn.execute(text('DELETE FROM users WHERE id=ANY(:ids)'), {'ids':ids})
    finally:
        await engine.dispose()

try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe')
        contexts = [browser.new_context(), browser.new_context()]
        for context in contexts:
            context.add_init_script("""(() => {
                const Native = window.WebSocket; window.__testSockets = [];
                function TrackingSocket(...args) { const socket = new Native(...args); window.__testSockets.push(socket); return socket; }
                TrackingSocket.prototype = Native.prototype; Object.setPrototypeOf(TrackingSocket, Native);
                window.WebSocket = TrackingSocket;
            })()""")
        pages = [context.new_page() for context in contexts]
        for page,email,name in zip(pages,emails,['Leader','Planner']):
            page.goto('http://127.0.0.1:5173/', wait_until='networkidle')
            page.get_by_role('button',name='Create account').click()
            page.get_by_label('Display name').fill(name)
            page.get_by_label('Email').fill(email)
            page.get_by_label('Password').fill(password)
            page.locator('form').get_by_role('button',name='Create account').click()
            page.get_by_role('heading',name='Start a trip').wait_for()
        leader, planner = pages
        leader.get_by_role('button',name='Create room').click()
        leader.get_by_text('Invite your group').wait_for()
        code = leader.locator('.invite code').inner_text()
        planner.get_by_label('Invitation code').fill(code)
        started = time.monotonic()
        planner.get_by_role('button',name='Join room').click()
        planner.get_by_role('heading',name='Shared itinerary').wait_for()
        planner.locator('[data-snapshot-ready="true"]').wait_for()
        snapshot_ms = (time.monotonic()-started)*1000
        assert snapshot_ms <= 2000, f'Join to snapshot took {snapshot_ms:.1f} ms'
        leader.get_by_text(re.compile(r'· connected$')).wait_for()
        planner.get_by_text(re.compile(r'· connected$')).wait_for()
        place = planner.locator('.place').filter(has=planner.get_by_role('button',name='Add to itinerary')).first
        name = place.locator('h3').inner_text()
        place.get_by_role('button',name='Add to itinerary').click()
        for page in pages:
            page.get_by_role('heading',name='Shared itinerary').wait_for()
            expect(page.get_by_role('heading',name=name,exact=True)).to_have_count(2)
            page.get_by_text('All displayed changes saved').wait_for()
        planner.evaluate("window.__testSockets.at(-1).close(4000)")
        planner.wait_for_function("window.__testSockets.length >= 2 && window.__testSockets.at(-1).readyState === 1")
        expect(planner.get_by_role('heading',name=name,exact=True)).to_have_count(2)
        leader.get_by_label('Participant role').select_option('viewer')
        leader.get_by_role('button',name='Create invitation').click()
        leader.get_by_role('button',name='Revoke displayed invitation').wait_for()
        expect(leader.locator('.invite code')).not_to_have_text(code)
        leader.get_by_role('button',name='Revoke displayed invitation').click()
        expect(leader.get_by_role('button',name='Revoke displayed invitation')).to_have_count(0)
        print(f'Two browser sessions: create, join, pin, committed snapshot, reconnect and invite controls succeeded; join to snapshot {snapshot_ms:.1f} ms')
        for context in contexts:
            context.close()
        browser.close()
finally:
    asyncio.run(cleanup())
