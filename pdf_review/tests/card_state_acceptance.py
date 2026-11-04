"""Left utility layout persistence and compact section feedback browser checks."""
import json
import time
from tests.viewer_acceptance import viewport, PDF, screenshot
from tests.beta_c2_acceptance import request


def run_card_state(cdp, a, b, fixture, base):
    def ev(script): return cdp.evaluate(a, script)
    def wait(script): return cdp.wait(a, script)
    def reload(session=a):
        cdp.evaluate(session,'window.layoutReloading=true')
        cdp.call('Page.reload',{},session)
        cdp.wait(session,"!window.layoutReloading&&document.querySelector('#realtime-status')?.textContent==='Live'")
    viewport(cdp,a,1440,1000)
    doc,version=fixture['document_id'],fixture['versions'][0]
    config=ev("JSON.parse(document.querySelector('#anchor-config').textContent)")
    storage=f"pdf-review:left-cards:v1:{config['currentUserId']}:{version}"
    for page,(name,prompt) in enumerate([('Default prompt',''),('Custom prompt','What surprised you?')],1):
        sid=request(cdp,a,f'/api/documents/{doc}/sections','POST',{'name':name,'prompt':prompt})['data']['section_id']
        box=ev(PDF+f'.getPageView({page-1}).viewport.viewBox')
        assert request(cdp,a,f'/api/versions/{version}/sections/{sid}/placement','POST',{
            'start_page':page,'end_page':page,'start_y':None,'end_y':None,'start_view_box':box,'end_view_box':box,'page_count':2,'expected_revision':0})['status']==200
    wait("document.querySelectorAll('.section-feedback-card').length===2")
    labels=ev("[...document.querySelectorAll('.section-feedback-card .thread-card-location')].filter(e=>e.closest('.thread-card-header')).map(e=>e.textContent)")
    assert 'Default prompt \u00b7 Overall thoughts' in labels,labels
    assert 'Custom prompt \u00b7 What surprised you?' in labels,labels
    assert ev("![...document.querySelectorAll('.section-feedback-card')].some(c=>c.querySelector('.section-prompt')||c.textContent.includes('Leave section thoughts'))")
    assert ev("[...document.querySelectorAll('.section-feedback-card .reply-control')].every(b=>b.textContent==='Add response')")
    assert ev("[...document.querySelectorAll('#comments-menu button')].find(b=>b.textContent==='Reset to document defaults').previousElementSibling.tagName==='HR'")
    ev("document.querySelector('[data-sections]').click()")
    wait("document.querySelector('.sections-workspace')!==null")
    ev("document.querySelector('[data-pdf-control=viewFindButton]').click()")
    wait("document.querySelector('.search-panel')!==null")
    time.sleep(.25)
    # Move search using real input so its displaced position, not only opening Y, is saved.
    h=ev("(()=>{const r=document.querySelector('.search-panel .dialog-header').getBoundingClientRect();return {x:r.left+50,y:r.top+12};})()")
    for kind,y,extra in [('mousePressed',h['y'],{'button':'left','clickCount':1}),('mouseMoved',h['y']+45,{'buttons':1}),('mouseReleased',h['y']+45,{'button':'left','clickCount':1})]:
        cdp.call('Input.dispatchMouseEvent',dict(type=kind,x=h['x'],y=y,**extra),a)
    ev("document.querySelector('[data-review-settings]').click()")
    wait("document.querySelector('.settings-form')!==null")
    ev("document.querySelector('.settings-panel .left-card-pin').click();document.querySelector('#findInput').value='do-not-cache-search'")
    time.sleep(.4)
    state=ev('JSON.parse(localStorage.getItem('+json.dumps(storage)+'))')
    assert len(state)==3,state
    assert {r['key'] for r in state}=={'sections','settings','search'}
    assert next(r for r in state if r['key']=='settings')['pinned']
    assert all(set(r)=={'key','page','fraction','pinned'} for r in state)
    assert 'do-not-cache-search' not in ev('localStorage.getItem('+json.dumps(storage)+')')
    reload()
    wait("document.querySelectorAll('.left-card').length===3")
    assert ev("document.querySelector('.settings-panel').dataset.pinned==='true'&&document.querySelectorAll('.left-card[data-pinned=true]').length===1")
    assert ev("document.querySelector('#findInput').value===''")
    # Compare normalized document positions rather than tying saved Y to one zoom.
    for record in state:
        if record['pinned']: continue
        actual=ev("(()=>{const c=document.querySelector('."+{'sections':'sections','settings':'settings','search':'search'}[record['key']]+"-panel'),f=document.querySelector('iframe').getBoundingClientRect(),p="+PDF+f".getPageView({record['page']-1}).div.getBoundingClientRect();return (c.getBoundingClientRect().top-f.top-p.top)/p.height;"+"})()")
        assert abs(actual-record['fraction'])<.003,(record,actual)
    screenshot(cdp,a,'restored-left-cards')
    # Closed tools stay closed; the remaining tool survives a later reload.
    ev("document.querySelector('.search-panel .dialog-header button:last-child').click();document.querySelector('.settings-panel .dialog-header button:last-child').click()")
    reload()
    assert ev("document.querySelectorAll('.left-card').length===1&&document.querySelector('.sections-panel')!==null")
    # No other account or PDF version inherits this layout.
    reload(b)
    assert cdp.evaluate(b,"document.querySelectorAll('.left-card').length===0")
    cdp.call('Page.navigate',{'url':base+f"/versions/{fixture['versions'][1]}/view"},a)
    wait("document.querySelector('#realtime-status')?.textContent==='Live'&&JSON.parse(document.querySelector('#anchor-config').textContent).versionId!=="+json.dumps(version))
    assert ev("document.querySelectorAll('.left-card').length===0")
    cdp.call('Page.navigate',{'url':base+f'/versions/{version}/view'},a)
    wait("document.querySelector('.sections-panel')!==null&&document.querySelector('#realtime-status')?.textContent==='Live'")
    cdp.call('Page.enable',{},a)
    script=cdp.call('Page.addScriptToEvaluateOnNewDocument',{'source':'localStorage.setItem('+json.dumps(storage)+',"invalid-json")'},a)['identifier']
    reload()
    cdp.call('Page.removeScriptToEvaluateOnNewDocument',{'identifier':script},a)
    assert ev("document.querySelectorAll('.left-card').length===0"),ev("({url:location.href,cards:[...document.querySelectorAll('.left-card h2')].map(e=>e.textContent),storage:{...localStorage}})")
    print('PASS compact section prompt/default headers, menu separator, saved open/closed tools, pin/position restore, no content caching, account/version isolation and corrupt-state recovery',flush=True)
