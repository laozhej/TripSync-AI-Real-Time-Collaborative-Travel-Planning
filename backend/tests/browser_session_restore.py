"""Real Chrome regression: valid refresh cookies restore authentication on reload."""
import asyncio
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright, expect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

email = 'reload-'+secrets.token_hex(12)+'@example.invalid'


async def revoke():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    try:
        async with engine.begin() as conn:
            await conn.execute(text('''UPDATE auth_sessions SET revoked_at=now() WHERE user_id IN
                (SELECT id FROM users WHERE normalized_email=:email)'''), {'email': email})
    finally:
        await engine.dispose()


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    context = browser.new_context()
    context.add_init_script('''window.__loginWasRendered = false;
        new MutationObserver(() => {
            if ([...document.querySelectorAll('h2')].some(h => h.textContent === 'Welcome back'))
                window.__loginWasRendered = true;
        }).observe(document, {childList:true, subtree:true});''')
    page = context.new_page()
    refreshes, errors = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: refreshes.append(request.method) if request.url.endswith('/api/v1/auth/refresh') else None)
    base = os.environ['BROWSER_BASE_URL']
    page.goto(base)
    expect(page.get_by_role('heading', name='Welcome back', exact=True)).to_be_visible()
    page.get_by_role('button', name='Create account', exact=True).click()
    page.get_by_label('Display name', exact=True).fill('Reload traveler')
    page.get_by_label('Email', exact=True).fill(email)
    page.get_by_label('Password', exact=True).fill('reload regression password')
    page.locator('form').get_by_role('button', name='Create account', exact=True).click()
    expect(page.get_by_role('heading', name='Start a trip', exact=True)).to_be_visible()
    # The shared restore helper must also preserve an existing request's 401
    # refresh-and-retry behavior. Only the first response is injected.
    attempts = []
    def expired_once(route):
        attempts.append(True)
        if len(attempts) == 1:
            route.fulfill(status=401, content_type='application/json', body='{"detail":"Expired test access"}')
        else:
            route.continue_()
    page.route('**/api/v1/trips', expired_once)
    before = len(refreshes)
    page.get_by_role('button', name='Create room', exact=True).click()
    page.locator('[data-snapshot-ready="true"]').wait_for()
    assert len(attempts) == 2 and len(refreshes) == before+1
    page.unroute('**/api/v1/trips', expired_once)
    for _ in range(2):
        before = len(refreshes)
        page.reload()
        expect(page.get_by_role('heading', name='Start a trip', exact=True)).to_be_visible()
        expect(page.get_by_role('button', name='Sign out', exact=True)).to_be_visible()
        assert len(refreshes) == before+1, 'Reload must rotate the refresh cookie exactly once'
        assert not page.evaluate('window.__loginWasRendered'), 'Valid restoration must not flash the login form'
    page.get_by_role('button', name='Sign out', exact=True).click()
    page.reload()
    expect(page.get_by_role('heading', name='Welcome back', exact=True)).to_be_visible()
    page.get_by_label('Email', exact=True).fill(email)
    page.get_by_label('Password', exact=True).fill('reload regression password')
    page.locator('form').get_by_role('button', name='Sign in', exact=True).click()
    expect(page.get_by_role('heading', name='Start a trip', exact=True)).to_be_visible()
    with ThreadPoolExecutor(max_workers=1) as worker:
        worker.submit(asyncio.run, revoke()).result(timeout=10)
    page.reload()
    expect(page.get_by_role('heading', name='Welcome back', exact=True)).to_be_visible()
    assert not errors, errors
    print('PASS: anonymous startup, existing 401 refresh/retry, two authenticated reloads with exactly one rotation and no login flash, logout/reload, and revoked-session reload; no page errors')
    browser.close()
