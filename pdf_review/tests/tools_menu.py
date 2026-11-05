"""Focused Tools menu checks using disposable viewer fixtures."""
import json
from tests.viewer_acceptance import viewport, click, key, screenshot
from tests.beta_c2_acceptance import navigate


def run_tools(cdp, a, b, fixture, base):
    def ev(script): return cdp.evaluate(a, script)
    def wait(script): return cdp.wait(a, script)
    viewport(cdp, a, 1440, 1000)
    assert ev("[...document.querySelectorAll('#review-tools-menu [data-left-card]')].map(x=>x.dataset.leftCard).join(',')==='search,filters,reading,analytics,properties,settings,sections'")
    assert ev("!document.querySelector('#review-view-menu [data-review-settings],#review-view-menu [data-sections],#comments-menu [data-comment-filters]')")
    for tool, panel in [('properties', '.page-properties-card'), ('search', '.search-panel'), ('filters', '.comment-filter-panel'), ('settings', '.settings-panel'), ('sections', '.sections-panel')]:
        selector=f'#review-tools-menu [data-left-card={tool}]'
        assert ev(f"document.querySelector({json.dumps(selector)}).getAttribute('aria-checked')==='false'")
        if not ev("document.querySelector('#review-tools-menu').open"):
            click(cdp, a, '#review-tools-menu > summary')
        click(cdp, a, selector)
        wait(f"document.querySelector({json.dumps(panel)})?.contains(document.activeElement)")
        if tool == 'settings':
            wait("document.querySelector('.settings-panel form select')!==null")
        assert ev("document.querySelector('#review-tools-menu').open")
        assert ev(f"document.querySelector({json.dumps(selector)}).getAttribute('aria-checked')==='true'")
        assert ev(f"getComputedStyle(document.querySelector({json.dumps(selector)}),'::after').content.includes('✓')")
        ev(f"window.testToolCard=document.querySelector({json.dumps(panel)})")
        click(cdp, a, '#review-view-menu > summary')
        click(cdp, a, '#review-tools-menu > summary')
        click(cdp, a, selector)
        wait(f"document.querySelector({json.dumps(panel)})?.contains(document.activeElement)")
        assert ev(f"document.querySelectorAll({json.dumps(panel)}).length===1&&document.querySelector({json.dumps(panel)})===testToolCard")
        assert ev("document.querySelector('#review-tools-menu').open")
        click(cdp, a, selector)
        wait(f"document.querySelector({json.dumps(selector)}).getAttribute('aria-checked')==='false'")
        assert ev("document.querySelector('#review-tools-menu').open")
        click(cdp, a, selector)
        wait(f"document.querySelector({json.dumps(panel)})?.contains(document.activeElement)")
        click(cdp, a, panel+' .dialog-header button:last-child')
        wait(f"document.querySelector({json.dumps(selector)}).getAttribute('aria-checked')==='false'")
        assert ev("!document.querySelector('#review-tools-menu').open")
        ev("delete window.testToolCard")
    # Close all includes pinned tools, clears every check, and keeps the menu open.
    click(cdp,a,'#review-tools-menu > summary')
    for tool in ['search','filters','settings','sections']:
        click(cdp,a,f'#review-tools-menu [data-left-card={tool}]')
        wait(f"document.querySelector('[data-left-card={tool}]').getAttribute('aria-checked')==='true'")
    ev("document.querySelector('.search-panel .left-card-pin').click()")
    click(cdp,a,'[data-close-all-tools]')
    wait("document.querySelectorAll('.left-card').length===0")
    assert ev("document.querySelector('#review-tools-menu').open&&[...document.querySelectorAll('[data-left-card]')].every(x=>x.getAttribute('aria-checked')==='false')")
    click(cdp,a,'#review-tools-menu > summary')
    # Native search shortcut and close also update the same checkmark.
    key(cdp, a, 'f', 70, 2)
    wait("document.querySelector('[data-left-card=search]').getAttribute('aria-checked')==='true'")
    key(cdp, a, 'Escape', 27)
    wait("document.querySelector('[data-left-card=search]').getAttribute('aria-checked')==='false'")
    # Existing keyboard menu navigation and mobile popup positioning are reused.
    viewport(cdp, a, 390, 844)
    ev("document.querySelector('#review-tools-menu > summary').focus()")
    key(cdp, a, 'ArrowDown', 40)
    wait("document.activeElement===document.querySelector('#review-tools-menu [data-close-all-tools]')")
    key(cdp, a, 'End', 35)
    assert ev("document.activeElement===document.querySelector('#review-tools-menu [data-left-card=sections]')")
    assert ev("(()=>{const r=document.querySelector('#review-tools-menu > .toolbar-popover').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight;})()")
    screenshot(cdp,a,'tools-menu-mobile')
    key(cdp, a, 'Escape', 27)
    assert ev("!document.querySelector('#review-tools-menu').open")
    # A reviewer receives only search/filter entries from the server template.
    doc=fixture['document_id']
    payload=json.dumps({'csrf_token':ev("document.querySelector('meta[name=csrf-token]').content"),'user_id':fixture['users'][1]['user_id'],'role':'reviewer','action':'grant'})
    ev(f"(async()=>{{const r=await fetch('/documents/{doc}/access',{{method:'POST',body:new URLSearchParams({payload})}});if(!r.ok)throw new Error('Fixture role change failed')}})()")
    navigate(cdp,b,base+f"/versions/{fixture['versions'][0]}/view",True)
    assert cdp.evaluate(b,"[...document.querySelectorAll('#review-tools-menu [data-left-card]')].map(x=>x.dataset.leftCard).join(',')==='search,filters,reading,analytics,properties'&&!document.querySelector('[data-review-settings],[data-sections]')")
    print('PASS Tools menu reuse, reopen without duplicates, live checkmarks, native search, keyboard/mobile menus and owner-only actions',flush=True)
