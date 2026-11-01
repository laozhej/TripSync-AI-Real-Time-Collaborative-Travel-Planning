import os,secrets
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from browser_ui_audit import audit
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe')
 context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
 page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(os.environ.get('BROWSER_BASE_URL','http://127.0.0.1:5173/'))
 page.get_by_role('button',name='Create account',exact=True).click()
 page.get_by_label('Display name').fill('Trip Leader')
 page.get_by_label('Email',exact=True).fill('draft-'+secrets.token_hex(8)+'@example.invalid')
 page.get_by_label('Password',exact=True).fill('draft visual test password')
 page.locator('form').get_by_role('button',name='Create account',exact=True).click()
 page.get_by_role('button',name='Create room',exact=True).click()
 page.locator('[data-snapshot-ready=true]').wait_for()
 expect(page.get_by_role('heading',name='Plan together. Travel better.',exact=True)).to_be_visible()
 audit(page,'draft-overview-light')
 page.screenshot(path='.local/draft-overview-light.png',animations='disabled')
 page.get_by_role('button',name='Itinerary canvas',exact=True).click()
 page.get_by_role('button',name='Add to itinerary').first.click()
 page.locator('.gridCard').wait_for()
 page.get_by_role('button',name='Trip overview',exact=True).click()
 expect(page.locator('.overviewActivity')).to_have_count(1)
 for label,heading in [('Group decisions','Timed votes'),('Budget & splits','Group budget'),('Conflicts','Schedule & budget conflicts'),('Recommendations','Recommended for your group'),('AI Concierge','AI Concierge'),('Room chat','Room chat'),('Travelers','Travelers'),('Session analytics','Session summary'),('Room controls','Room controls')]:
  page.get_by_role('button',name=label,exact=True).click()
  expect(page.get_by_role('heading',name=heading,exact=True,level=2)).to_be_visible()
  expect(page.get_by_role('button',name=label,exact=True)).to_have_attribute('aria-current','page')
 page.get_by_role('button',name='Trip overview',exact=True).click()
 page.screenshot(path='.local/draft-overview-populated.png',animations='disabled')
 page.get_by_role('button',name='Switch to dark theme').click()
 audit(page,'draft-overview-dark')
 page.screenshot(path='.local/draft-overview-dark.png',animations='disabled')
 for width in (390,768,1024,1440):
  page.set_viewport_size({'width':width,'height':900})
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'),width
  if width==390:
   page.get_by_role('button',name='Open workspace navigation').click()
   page.get_by_role('button',name='Group decisions',exact=True).click()
   expect(page.get_by_role('heading',name='Timed votes',exact=True)).to_be_visible()
   expect(page.get_by_role('button',name='Open workspace navigation')).to_have_attribute('aria-expanded','false')
   page.get_by_role('button',name='Open workspace navigation').click()
   page.get_by_role('button',name='Trip overview',exact=True).click()
   audit(page,'draft-mobile-overview')
   page.screenshot(path='.local/draft-overview-mobile.png',animations='disabled')
 assert not errors,errors
 print('Draft visual browser: sidebar navigation, populated overview, separate pages, live board preservation, dark/light themes, mobile drawer and 390/768/1024/1440 overflow checks passed; no page errors')
 browser.close()
