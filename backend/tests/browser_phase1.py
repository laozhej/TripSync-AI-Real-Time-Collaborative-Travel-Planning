"""Opt-in two-browser smoke test. Uses disposable PostgreSQL and removes its own records."""
import asyncio
import os
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv(Path(__file__).resolve().parents[2] / '.env')
suffix = secrets.token_hex(12)
emails = [f'leader-{suffix}@example.invalid', f'planner-{suffix}@example.invalid']
password = 'browser test password only'


async def revoke_test_session(email):
    assert email in emails
    engine=create_async_engine(os.environ['DATABASE_URL'])
    try:
        async with engine.begin() as conn:
            await conn.execute(text('''UPDATE auth_sessions SET revoked_at=now()
                WHERE user_id IN (SELECT id FROM users WHERE normalized_email=:email)'''),{'email':email})
    finally:
        await engine.dispose()

async def cleanup():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    try:
        async with engine.begin() as conn:
            ids = (await conn.execute(text('SELECT id FROM users WHERE normalized_email=ANY(:emails)'), {'emails':emails})).scalars().all()
            if not ids:
                return
            trips = (await conn.execute(text('SELECT id FROM trips WHERE leader_user_id=ANY(:ids)'), {'ids':ids})).scalars().all()
            for trip in trips:
                await conn.execute(text('DELETE FROM reactions WHERE message_id IN (SELECT id FROM chat_messages WHERE trip_id=:trip)'), {'trip':trip})
                await conn.execute(text('DELETE FROM chat_messages WHERE trip_id=:trip'), {'trip':trip})
                await conn.execute(text('DELETE FROM item_attendees WHERE item_id IN (SELECT id FROM itinerary_items WHERE trip_id=:trip)'), {'trip':trip})
                for table in ('ai_questions','room_events','itinerary_items','invites','memberships'):
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
        # The test-only server gives the first access token an 8-second TTL.
        # Both the in-memory HTTP token and HttpOnly socket token expire together.
        planner.wait_for_function("window.__testSockets.length >= 2 && window.__testSockets.at(-1).readyState === 1",timeout=20000)
        expect(planner.get_by_role('heading',name=name,exact=True)).to_have_count(2)
        planner.get_by_label('Start time (UTC)').fill('13:00')
        planner.get_by_role('button',name='Move to selected time').click()
        for page in pages:
            expect(page.locator('.board .place').filter(has=page.get_by_role('button',name='Move to selected time')).first).to_contain_text('13:00:00')
        leader.get_by_role('button',name='Lock',exact=True).click()
        expect(leader.get_by_role('button',name='Unlock',exact=True)).to_be_visible()
        expect(planner.get_by_role('button',name='Move to selected time')).to_have_count(0)
        leader.once('dialog', lambda dialog: dialog.accept('Adjust the plan'))
        leader.get_by_role('button',name='Unlock',exact=True).click()
        expect(planner.get_by_role('button',name='Move to selected time')).to_be_visible()
        planner.get_by_label('Message').fill('Hello <travelers>!')
        expect(leader.get_by_text(re.compile(r'(Planner|Traveler) is typing'))).to_be_visible()
        planner.get_by_role('button',name='Send message').click()
        for page in pages:
            expect(page.get_by_text('Hello <travelers>!', exact=False)).to_be_visible()
        planner.get_by_role('button',name='React 👍').click()
        expect(planner.get_by_role('button',name='React 👍')).to_have_attribute('aria-pressed','true')
        expect(leader.get_by_role('button',name='React 👍')).to_contain_text('1')
        planner.evaluate("window.__testSockets.at(-1).close(4000)")
        planner.wait_for_function("window.__testSockets.length >= 2 && window.__testSockets.at(-1).readyState === 1")
        expect(planner.get_by_role('heading',name=name,exact=True)).to_have_count(2)
        expect(planner.get_by_text('Hello <travelers>!', exact=False)).to_be_visible()
        expect(planner.get_by_role('button',name='React 👍')).to_have_attribute('aria-pressed','true')
        # Actual native drag/drop uses the captured version and persists only the drop.
        card=planner.locator('.gridCard').first
        card.drag_to(planner.get_by_role('cell',name='2026-11-11 14:00 UTC',exact=True),source_position={'x':20,'y':20},target_position={'x':50,'y':20})
        for page in pages:
            expect(page.locator('.gridCard').first).to_contain_text('2026-11-11T14:00:00')
            page.get_by_text('All displayed changes saved').wait_for()
        leader.get_by_text('Budget and dietary preferences',exact=True).click()
        leader.get_by_label('Group category ceiling (EUR/person)').fill('25.00')
        leader.get_by_role('button',name='Save group ceiling',exact=True).click()
        expect(leader.get_by_role('button',name='Save group ceiling',exact=True)).to_be_enabled()
        leader.get_by_role('button',name='Ask Concierge',exact=True).click()
        expect(leader.locator('.concierge [role=status] strong')).to_have_text('grounded',timeout=15000)
        leader.get_by_role('button',name='venue:v_1@1',exact=True).click()
        expect(leader.get_by_text('venue:v_1@1 · Synthetic authored source',exact=True)).to_be_visible()
        leader.get_by_label('Participant role').select_option('viewer')
        leader.get_by_role('button',name='Create invitation').click()
        leader.get_by_role('button',name='Revoke displayed invitation').wait_for()
        expect(leader.locator('.invite code')).not_to_have_text(code)
        leader.get_by_role('button',name='Revoke displayed invitation').click()
        expect(leader.get_by_role('button',name='Revoke displayed invitation')).to_have_count(0)
        leader.get_by_role('button',name='Lock room',exact=True).click()
        expect(planner.get_by_role('button',name='Add to itinerary').first).to_be_disabled()
        expect(leader.locator('.concierge [role=status] strong')).to_have_text('Earlier result')
        leader.get_by_role('button',name='Unlock room',exact=True).click()
        expect(planner.get_by_role('button',name='Add to itinerary').first).to_be_enabled()
        leader.get_by_role('button',name='Mute Planner',exact=True).click()
        expect(planner.get_by_label('Message')).to_be_disabled()
        leader.get_by_role('button',name='Unmute Planner',exact=True).click()
        expect(planner.get_by_label('Message')).to_be_enabled()
        leader.once('dialog',lambda dialog:dialog.accept())
        leader.get_by_role('button',name='Make Planner Leader',exact=True).click()
        expect(planner.get_by_role('heading',name='Room controls')).to_be_visible()
        expect(leader.get_by_role('heading',name='Room controls')).to_have_count(0)
        planner.once('dialog',lambda dialog:dialog.accept())
        planner.get_by_role('button',name='Remove Leader',exact=True).click()
        expect(leader.get_by_role('heading',name='Start a trip')).to_be_visible()
        # Playwright's sync driver has an active event loop on this thread.
        with ThreadPoolExecutor(max_workers=1) as worker:
            worker.submit(asyncio.run,revoke_test_session(emails[1])).result(timeout=10)
        expect(planner.get_by_role('heading',name='Welcome back')).to_be_visible(timeout=15000)
        expect(planner.get_by_role('alert')).to_contain_text('session has expired')
        leader.get_by_role('button',name='Sign out',exact=True).click()
        expect(leader.get_by_role('heading',name='Welcome back')).to_be_visible()
        print(f'Two browser sessions: grid drag/drop, real Concierge/citations, chat, expired-token refresh, reconnect, moderation and revoked-session sign-in succeeded; join to snapshot {snapshot_ms:.1f} ms')
        for context in contexts:
            context.close()
        browser.close()
finally:
    asyncio.run(cleanup())
