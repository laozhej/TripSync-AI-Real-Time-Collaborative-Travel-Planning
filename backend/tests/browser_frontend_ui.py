"""Focused real-server frontend regression cases on a disposable database."""
import json,os,secrets
from pathlib import Path
from playwright.sync_api import expect,sync_playwright
from browser_ui_audit import audit

base=os.environ.get('BROWSER_BASE_URL','http://127.0.0.1:5173/')
suffix=secrets.token_hex(8)
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    contexts=[browser.new_context(reduced_motion='reduce') for _ in range(3)]
    errors=[];events=[]
    for context in contexts:
        context.add_init_script("""const Native=window.WebSocket;window.__testSockets=[];window.WebSocket=class extends Native{constructor(...args){super(...args);window.__testSockets.push(this)}};""")
    pages=[c.new_page() for c in contexts]
    for index,page in enumerate(pages):
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base)
        if index==0:
            audit(page,'sign-in-light')
            page.keyboard.press('Tab')
            expect(page.get_by_role('link',name='Skip to workspace')).to_be_focused()
        page.get_by_role('button',name='Create account',exact=True).click()
        page.get_by_label('Display name').fill(['Leader','Planner','Viewer'][index])
        page.get_by_label('Email',exact=True).fill(f'ui-{index}-{suffix}@example.invalid')
        page.get_by_label('Password',exact=True).fill('frontend browser password')
        page.locator('form').get_by_role('button',name='Create account',exact=True).click()
        page.get_by_role('heading',name='Start a trip').wait_for()
    leader,planner,viewer=pages
    audit(leader,'dashboard-empty-light')
    for page in pages:expect(page.get_by_role('heading',name='Admin dataset management')).to_have_count(0)
    def received(frame):
        try:events.append(json.loads(frame))
        except (ValueError,TypeError):pass
    leader.on('websocket',lambda ws:ws.on('framereceived',received))
    leader.get_by_role('button',name='Create room').click()
    leader.locator('[data-snapshot-ready=true]').wait_for()
    code=leader.locator('.invite code').inner_text()
    planner.get_by_label('Invitation code').fill(code);planner.get_by_role('button',name='Join room').click()
    planner.locator('[data-snapshot-ready=true]').wait_for()
    leader.get_by_label('Participant role').select_option('viewer')
    leader.get_by_role('button',name='Create invitation').click()
    expect(leader.locator('.invite code')).not_to_have_text(code)
    viewer.get_by_label('Invitation code').fill(leader.locator('.invite code').inner_text())
    viewer.get_by_role('button',name='Join room').click();viewer.locator('[data-snapshot-ready=true]').wait_for()
    expect(viewer.get_by_role('button',name='Add to itinerary').first).to_be_disabled()
    expect(viewer.get_by_role('heading',name='Room controls')).to_have_count(0)
    viewer.get_by_label('Message',exact=True).fill('Viewer can still chat.')
    viewer.get_by_role('button',name='Send message').click()
    expect(leader.get_by_text('Viewer can still chat.',exact=False)).to_be_visible()
    leader.get_by_role('button',name='Add to itinerary').nth(0).click()
    planner.locator('.gridCard').wait_for()
    original=next(e['payload']['item'] for e in events if e['event']=='trip.board.update' and e['payload'].get('operation')=='pin')
    planner.get_by_label('Start time (IST)').fill('13:00')
    planner.get_by_role('button',name='Move to selected time').click()
    expect(leader.locator('.gridCard').first).to_contain_text('13:00 IST')
    # Deliberately send the captured stale version; the UI must reconcile, never retry it.
    stale={'event':'trip.board.move','payload':{'commandId':secrets.token_hex(16),'correlationId':secrets.token_hex(16),'itemId':original['itemId'],'expectedPositionVersion':original['positionVersion'],'dayIndex':original['dayIndex'],'startTime':original['startTime'],'endTime':original['endTime']}}
    leader.evaluate('(command)=>window.__testSockets.at(-1).send(JSON.stringify(command))',stale)
    expect(leader.get_by_role('alert')).to_contain_text('Someone changed this item')
    expect(leader.locator('.gridCard').first).to_contain_text('13:00 IST')
    expect(viewer.locator('summary').filter(has_text='Split cost:')).to_have_count(0)
    leader.get_by_label('Start time (IST)').fill('13:30')
    leader.get_by_role('button',name='Add to itinerary').nth(1).click()
    expect(leader.locator('#conflicts').get_by_role('heading',name='Schedule overlap')).to_be_visible()
    leader.locator('#conflicts').screenshot(path='.local/ui-conflict-open.png',animations='disabled')
    leader.get_by_label('Start time (IST)').fill('14:30')
    leader.locator('.gridCard').filter(has_text='Synthetic City Museum').get_by_role('button',name='Move to selected time').click()
    expect(leader.locator('#conflicts').get_by_text('No open conflicts.',exact=True)).to_be_visible()
    leader.get_by_text('Budget and dietary preferences',exact=True).click()
    leader.get_by_label('My total trip ceiling (INR, optional)').fill('1.00')
    leader.get_by_role('button',name='Save my preferences',exact=True).click()
    expect(leader.locator('#conflicts').get_by_role('heading',name='Budget conflict')).to_be_visible()
    expect(leader.get_by_role('button',name='Save my preferences',exact=True)).to_be_enabled()
    leader.get_by_label('My total trip ceiling (INR, optional)').fill('50000.00')
    leader.get_by_role('button',name='Save my preferences',exact=True).click()
    try:expect(leader.locator('#conflicts').get_by_text('No open conflicts.',exact=True)).to_be_visible()
    except Exception:
        print('Rendered alerts:',leader.get_by_role('alert').all_text_contents())
        print('Rendered conflicts:',leader.locator('#conflicts').inner_text())
        leader.screenshot(path='.local/ui-budget-failure.png',full_page=True)
        raise
    audit(leader,'active-room-light')
    leader.screenshot(path='.local/ui-active-room.png',full_page=True,animations='disabled')
    leader.get_by_role('button',name='Switch to dark theme').click()
    audit(leader,'active-room-dark')
    leader.get_by_role('button',name='Back',exact=False).click()
    expect(leader.locator('html')).to_have_attribute('data-theme','dark')
    audit(leader,'dashboard-dark')
    leader.screenshot(path='.local/ui-dashboard-dark.png',full_page=True,animations='disabled')
    leader.get_by_role('button',name='Rejoin room',exact=True).click()
    leader.locator('[data-snapshot-ready=true]').wait_for()
    # Same-slot distinct candidates produce the real no-turnout cancellation state.
    leader.get_by_label('Start time (IST)').fill('13:00')
    leader.locator('.gridCard').filter(has_text='Synthetic City Museum').get_by_role('button',name='Move to selected time').click()
    expect(viewer.get_by_role('button',name='Vote for',exact=False)).to_have_count(2)
    for button in viewer.get_by_role('button',name='Vote for',exact=False).all():expect(button).to_be_disabled()
    expect(viewer.get_by_text('Your membership is not in its eligible voter list.',exact=False)).to_be_visible()
    audit(viewer,'viewer-voting-light')
    viewer.locator('#votes').screenshot(path='.local/ui-vote-open-viewer.png',animations='disabled')
    for page in pages:expect(page.get_by_text('Cancelled: no ballots',exact=True)).to_be_visible(timeout=75000)
    for width in (390,768,1024,1440):
        leader.set_viewport_size({'width':width,'height':900})
        assert leader.evaluate('document.documentElement.scrollWidth <= innerWidth+1'),width
    leader.locator('#votes').screenshot(path='.local/ui-vote-cancelled.png',animations='disabled')
    assert not errors,errors
    print('Frontend UI Chrome: Viewer restrictions/chat; stale move reconciliation; overlap and personal budget conflict resolution; real no-turnout cancellation; keyboard skip link; light/dark accessibility and responsive widths passed; no page errors')
    browser.close()
