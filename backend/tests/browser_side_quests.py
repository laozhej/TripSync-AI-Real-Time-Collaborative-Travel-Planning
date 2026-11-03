"""Exercise destination creation, personal activity sync and separate-room navigation."""
import os
import secrets

from playwright.sync_api import expect, sync_playwright

base = os.environ['BROWSER_BASE_URL']
suffix = secrets.token_hex(8)
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    contexts = [browser.new_context(reduced_motion='reduce') for _ in range(2)]
    pages = [context.new_page() for context in contexts]
    errors = []
    for index, page in enumerate(pages):
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base, wait_until='networkidle')
        page.get_by_role('button', name='Create account', exact=True).click()
        page.get_by_label('Display name').fill(['Leader', 'Planner'][index])
        page.get_by_label('Email', exact=True).fill(f'sidequest-{index}-{suffix}@example.invalid')
        page.get_by_label('Password', exact=True).fill('side quest browser test password')
        page.locator('form').get_by_role('button', name='Create account', exact=True).click()
        page.get_by_role('heading', name='Start a trip').wait_for()
        expect(page.get_by_label('Destination', exact=True)).to_have_value('Bengaluru, India')
    leader, planner = pages
    leader.get_by_role('button', name='Create room', exact=True).click()
    leader.locator('[data-snapshot-ready=true]').wait_for()
    leader.get_by_role('button', name='Itinerary canvas', exact=True).click()
    code = leader.locator('.invite code').inner_text()
    planner.get_by_label('Invitation code').fill(code)
    planner.get_by_role('button', name='Join room', exact=True).click()
    planner.locator('[data-snapshot-ready=true]').wait_for()
    planner.get_by_role('button', name='Itinerary canvas', exact=True).click()
    planner.get_by_label('Personal activity name').fill('Visit a friend')
    planner.get_by_label('Cost per person (INR)', exact=True).fill('125.05')
    planner.get_by_role('button', name='Add personal activity', exact=True).click()
    for page in pages:
        card = page.locator('.gridCard').filter(has_text='Visit a friend')
        expect(card).to_be_visible()
        expect(card).to_contain_text('Personal activity')
    planner.get_by_label('Start time (IST)').fill('14:00')
    planner.get_by_role('button', name='Move to selected time', exact=True).click()
    expect(leader.locator('.gridCard')).to_contain_text('14:00 IST')
    leader.get_by_role('link', name='Start a separate trip', exact=True).click()
    expect(leader.get_by_role('heading', name='Start a trip')).to_be_visible()
    leader.get_by_label('Destination', exact=True).select_option('Goa, India')
    leader.get_by_role('button', name='Create room', exact=True).click()
    leader.locator('[data-snapshot-ready=true]').wait_for()
    leader.get_by_role('button', name='Itinerary canvas', exact=True).click()
    expect(leader.get_by_role('heading', name='Harbour Test Kitchen', exact=True)).to_be_visible()
    expect(leader.locator('.gridCard')).to_have_count(0)
    leader.get_by_role('button', name='Add to itinerary', exact=True).first.click()
    expect(leader.locator('.gridCard')).to_have_count(1)
    expect(planner.locator('.gridCard')).to_have_count(1)
    expect(planner.locator('.gridCard')).to_contain_text('Visit a friend')
    leader.reload(wait_until='networkidle')
    trip = leader.locator('.tripCard').filter(has=leader.get_by_role('heading', name='Bengaluru, India', exact=True))
    trip.get_by_role('button', name='Rejoin room', exact=True).click()
    leader.locator('[data-snapshot-ready=true]').wait_for()
    leader.get_by_role('button', name='Itinerary canvas', exact=True).click()
    expect(leader.locator('.gridCard')).to_contain_text('Visit a friend')
    expect(leader.locator('.gridCard')).to_contain_text('14:00 IST')
    assert not errors, errors
    print('PASS: Bengaluru default, Goa creation/catalog, personal activity sync/move, separate-room isolation and reload/rejoin')
    print('Chrome', browser.version)
    browser.close()
