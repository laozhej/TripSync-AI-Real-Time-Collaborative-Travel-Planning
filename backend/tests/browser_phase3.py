"""Real Chrome acceptance for Phase 3 UI against the disposable runner."""
import asyncio,json,os,secrets
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from browser_ui_audit import audit
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

suffix=secrets.token_hex(8)
emails=[f'phase3-{i}-{suffix}@example.invalid' for i in range(2)]
password='phase3 browser password'

async def promote():
    engine=create_async_engine(os.environ['DATABASE_URL'])
    try:
        async with engine.begin() as conn:await conn.execute(text('UPDATE users SET is_admin=true WHERE normalized_email=:email'),{'email':emails[0]})
    finally:await engine.dispose()

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    contexts=[browser.new_context(reduced_motion='reduce') for _ in emails];pages=[c.new_page() for c in contexts];errors=[]
    failures=[]
    for page,email in zip(pages,emails):
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('response',lambda r:failures.append((r.status,r.url.split('?')[0])) if r.status>=400 else None)
        page.goto(os.environ.get('BROWSER_BASE_URL','http://127.0.0.1:5173/'))
        page.get_by_role('button',name='Create account',exact=True).click()
        page.get_by_label('Display name').fill('Traveler '+str(emails.index(email)))
        page.get_by_label('Email',exact=True).fill(email);page.get_by_label('Password',exact=True).fill(password)
        page.locator('form').get_by_role('button',name='Create account',exact=True).click()
        page.get_by_role('heading',name='Start a trip').wait_for()
    leader,planner=pages
    with ThreadPoolExecutor(max_workers=1) as executor:executor.submit(lambda:asyncio.run(promote())).result()
    leader.get_by_role('button',name='Sign out').click()
    leader.get_by_label('Email',exact=True).fill(emails[0]);leader.get_by_label('Password',exact=True).fill(password)
    leader.locator('form').get_by_role('button',name='Sign in',exact=True).click()
    leader.get_by_role('heading',name='Admin dataset management').wait_for()
    leader.get_by_role('button',name='Create room').click();leader.locator('[data-snapshot-ready="true"]').wait_for()
    code=leader.locator('.invite code').inner_text()
    planner.get_by_label('Invitation code').fill(code);planner.get_by_role('button',name='Join room').click()
    planner.locator('[data-snapshot-ready="true"]').wait_for()
    leader.get_by_text('Budget and dietary preferences',exact=True).click()
    leader.get_by_label('My total trip ceiling (INR, optional)').fill('50000.00')
    leader.get_by_role('button',name='Save my preferences',exact=True).click()
    leader.get_by_role('button',name='Add to itinerary').nth(0).click()
    editor=leader.locator('details').filter(has=leader.locator('summary',has_text='Split cost:')).first
    editor.locator('summary').click();editor.get_by_label('Split method').select_option('weighted')
    editor.get_by_label('Weight for Traveler 0').fill('1');editor.get_by_label('Weight for Traveler 1').fill('2')
    editor.get_by_role('button',name='Save split').click()
    leader.get_by_role('button',name='Add to itinerary').nth(1).click()
    for page in pages:expect(page.get_by_role('button',name='Vote for',exact=False)).to_have_count(2,timeout=10000)
    # Both identities choose the same option; server deadline applies it in both browsers.
    chosen=planner.get_by_role('button',name='Vote for',exact=False).nth(1).inner_text()
    planner.get_by_role('button',name=chosen,exact=True).click()
    leader.get_by_role('button',name=chosen,exact=True).click()
    for page in pages:expect(page.get_by_text('Winner locked',exact=False)).to_be_visible(timeout=75000)
    leader.get_by_role('button',name='Show session analytics').click()
    expect(leader.get_by_text('Peak connected planners',exact=True)).to_be_visible()
    leader.get_by_role('button',name='Like ',exact=False).first.click()
    leader.get_by_role('button',name='Refresh recommendation model').click()
    try:expect(leader.get_by_text('Trained recommendation model',exact=True)).to_be_visible(timeout=10000)
    except Exception:
        print('HTTP failures:',failures,'page errors:',errors)
        raise
    leader.get_by_role('button',name='Back',exact=False).click()
    leader.get_by_role('button',name='Rejoin room',exact=True).click();leader.locator('[data-snapshot-ready="true"]').wait_for()
    bundle=json.loads(Path('data/destinations/bengaluru.json').read_text(encoding='utf-8'))
    bundle['destination']='Browser staging '+suffix
    invalid=json.loads(json.dumps(bundle));invalid['venues'][0]['pricePerPerson']='-1'
    leader.get_by_label('Destination JSON').set_input_files({'name':'invalid.json','mimeType':'application/json','buffer':json.dumps(invalid).encode()})
    leader.get_by_role('button',name='Validate and stage').click()
    expect(leader.get_by_role('alert')).to_contain_text('Invalid dataset fields')
    leader.get_by_label('Destination JSON').set_input_files({'name':'valid.json','mimeType':'application/json','buffer':json.dumps(bundle).encode()})
    leader.get_by_role('button',name='Validate and stage').click()
    leader.get_by_role('button',name='Activate version 1',exact=True).click()
    dialog=leader.get_by_role('dialog',name='Activate dataset version?')
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role('button',name='Cancel')).to_be_focused()
    audit(leader,'activation-dialog')
    leader.keyboard.press('Escape')
    expect(dialog).to_have_count(0)
    expect(leader.get_by_role('button',name='Activate version 1',exact=True)).to_be_focused()
    leader.get_by_role('button',name='Activate version 1',exact=True).click()
    dialog.get_by_role('button',name='Confirm activation',exact=True).click()
    expect(leader.get_by_text('Browser staging '+suffix+' · v1 · active',exact=True)).to_be_visible()
    # Inspect real server-fed states and capture responsive/theme variants.
    expect(planner.get_by_role('heading',name='Admin dataset management')).to_have_count(0)
    expect(leader.locator('#conflicts').get_by_text('Resolved conflicts',exact=False)).to_be_visible()
    expect(leader.locator('#votes').get_by_text('Your selection',exact=True).first).to_be_visible()
    expect(leader.locator('#votes').get_by_text('Winner',exact=True)).to_be_visible()
    leader.locator('#itinerary').get_by_role('button',name='Day 1',exact=False).click()
    expect(leader.locator('.dayGrid thead th')).to_have_count(2)
    leader.locator('#itinerary').get_by_role('button',name='All days',exact=False).click()
    Path('.local').mkdir(exist_ok=True)
    leader.set_viewport_size({'width':1440,'height':1000})
    leader.evaluate('window.scrollTo(0,0)')
    audit(leader,'phase3-room-light')
    leader.screenshot(path='.local/ui-room-light.png',animations='disabled')
    leader.get_by_role('button',name='Switch to dark theme').click()
    expect(leader.locator('html')).to_have_attribute('data-theme','dark')
    audit(leader,'phase3-room-dark')
    leader.screenshot(path='.local/ui-room-dark.png',animations='disabled')
    for width in (390,768,1024):
        leader.set_viewport_size({'width':width,'height':900})
        assert leader.evaluate('document.documentElement.scrollWidth <= window.innerWidth+1'),width
        leader.evaluate('window.scrollTo(0,0)')
        leader.screenshot(path=f'.local/ui-room-{width}.png',animations='disabled')
    leader.get_by_role('button',name='Switch to light theme').click()
    leader.set_viewport_size({'width':1440,'height':1000})
    leader.get_by_role('button',name='Finalize trip',exact=True).click()
    expect(leader.get_by_role('button',name='Finalize trip',exact=True)).to_have_count(0)
    leader.get_by_role('button',name='Back',exact=False).click()
    leader.get_by_role('button',name='View history',exact=True).click()
    leader.locator('[data-snapshot-ready="true"]').wait_for()
    expect(leader.get_by_label('Message',exact=True)).to_be_disabled()
    expect(leader.get_by_role('button',name='Add to itinerary').first).to_be_disabled()
    audit(leader,'phase3-finalized-mobile')
    assert not errors,errors
    Path('.local').mkdir(exist_ok=True)
    leader.screenshot(path='.local/phase3-browser.png',full_page=True)
    # Check narrow viewport for horizontal document overflow.
    leader.set_viewport_size({'width':390,'height':844})
    assert leader.evaluate('document.documentElement.scrollWidth <= window.innerWidth+1')
    print('Phase 3 Chrome: two participants, weighted split, system vote/ballots/deadline/winner, analytics, hybrid refresh, dashboard rejoin/history, Admin invalid/valid staging/activation, finalization; no page errors; 390px overflow check passed')
    browser.close()
