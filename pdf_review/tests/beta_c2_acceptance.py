"""C2 browser geometry/privacy/UX acceptance; disposable fixture server only."""
import base64
import html
import json
from pathlib import Path
import time

from tests.viewer_acceptance import change,viewport,screenshot,PDF,ARTIFACTS,SELECT


def request(cdp,session,url,method='GET',payload=None):
    script='''(async()=>{const response=await fetch(URL,{method:METHOD,headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name=csrf-token]').content},BODY});const text=await response.text();let data;try{data=JSON.parse(text)}catch{data=text};return {status:response.status,data};})()'''
    script=script.replace('URL',json.dumps(url)).replace('METHOD',json.dumps(method)).replace('BODY','body:'+json.dumps(json.dumps(payload)) if payload is not None else '')
    return cdp.evaluate(session,script)


def navigate(cdp,session,url,viewer=False):
    cdp.call('Page.navigate',{'url':url},session)
    cdp.wait(session,"document.readyState==='complete'")
    if viewer:cdp.wait(session,"document.querySelector('#realtime-status')?.textContent==='Live'")


def run_c2(cdp,a,b,fixture,base):
    doc=fixture['document_id'];version=fixture['versions'][0];other=fixture['versions'][1]
    viewport(cdp,a,1440,900);viewport(cdp,b,1280,800)
    # Give B an ordinary reviewer role. The other account remains the owner.
    cdp.evaluate(a,f'''(async()=>{{const data=new URLSearchParams({{csrf_token:document.querySelector('meta[name=csrf-token]').content,user_id:{json.dumps(fixture['users'][1]['user_id'])},role:'reviewer',action:'grant'}});const r=await fetch('/documents/{doc}/access',{{method:'POST',body:data}});if(!r.ok)throw new Error('Fixture role change failed')}})()''')
    # Existing controls persist without reload and initialize once per document.
    change(cdp,b,'#review-spread',1);change(cdp,b,'#comments-visibility','minimized')
    cdp.wait(b,f"fetch('/api/documents/{doc}/viewer-preferences').then(r=>r.json()).then(d=>d.preferences.spread===1&&d.preferences.display==='minimized')")
    navigate(cdp,b,base+f'/versions/{version}/view',True)
    assert cdp.evaluate(b,"document.querySelector('#review-spread').value==='1' && document.querySelector('#comments-visibility').value==='minimized'")
    change(cdp,b,'#review-spread',0);change(cdp,b,'#comments-visibility','expanded')
    cdp.evaluate(b,PDF+'.currentScale=.75')
    # CRUD/workspace interaction is covered by --management-ui; seed geometry here.
    request(cdp,a,f'/api/documents/{doc}/sections','POST',{'name':'Precise section','prompt':'Did this decision feel believable?'})
    cdp.evaluate(a,"document.querySelector('[data-sections]').click()")
    cdp.wait(a,"document.querySelector('.sections-workspace')!==null")
    screenshot(cdp,a,'c2-sections-management')
    cdp.evaluate(a,"document.querySelector('.sections-panel .dialog-header button:last-child').click()")
    context=request(cdp,b,f'/api/versions/{version}/review-context')['data'];sid=context['sections'][0]['section_id']
    assert context['sections'][0]['placement'] is None
    navigate(cdp,a,base+f'/versions/{version}/view?sections=edit',True)
    cdp.evaluate(a,PDF+'.currentScale=.75')
    cdp.wait(a,"document.querySelector('.sections-panel [name=start_page]')!==null")
    screenshot(cdp,a,'c2-section-edit-mode')
    # Canonical geometry seed; interactive page entry/drag is covered by --management-ui.
    box=cdp.evaluate(a,PDF+'.getPageView(0).viewport.viewBox')
    assert request(cdp,a,f'/api/versions/{version}/sections/{sid}/placement','POST',{
        'start_page':1,'start_y':None,'start_view_box':box,'end_page':1,'end_y':400,'end_view_box':box,
        'page_count':cdp.evaluate(a,PDF+'.pagesCount'),'expected_revision':0})['status']==200
    cdp.evaluate(a,"document.querySelector('.sections-panel .dialog-header button:last-child').click()")
    cdp.wait(b,"document.querySelector('.section-feedback-card')!==null")
    # Section feedback uses the existing right rail and shared safe comment forms.
    cdp.evaluate(b,"document.querySelector('.section-feedback-card .reply-control').click();document.querySelector('.section-feedback-card textarea').value='Section response from Beta';document.querySelector('.section-feedback-card .thread-reply-form').requestSubmit()")
    cdp.wait(a,"document.body.textContent.includes('Section response from Beta')")
    screenshot(cdp,a,'c2-section-prompt-feedback')
    # Normal thread roots retain their own author color.
    cdp.evaluate(a,SELECT)
    cdp.wait(a,"!document.querySelector('#comment-selection-button').disabled")
    cdp.evaluate(a,"document.querySelector('#comment-selection-button').click();document.querySelector('#selection-comment-body').value='Owner text thread';document.querySelector('#selection-comment-form').requestSubmit()")
    cdp.wait(a,"document.body.textContent.includes('Owner text thread')")
    cdp.wait(b,"document.body.textContent.includes('Owner text thread')")
    screenshot(cdp,b,'c2-shared-review')
    cdp.evaluate(b,"document.querySelector('#comments-menu').open=true;document.querySelector('#comments-menu details').open=true")
    screenshot(cdp,b,'c2-people-filter')
    cdp.evaluate(b,"document.querySelector('#comments-menu').open=false;document.querySelector('[data-menu-input=review-scope][data-menu-value=mine]').click()")
    cdp.wait(b,"!document.body.textContent.includes('Owner text thread') && document.body.textContent.includes('Section response from Beta')")
    change(cdp,b,'#review-scope','all')
    # Build a second exact-page boundary section without overlapping the first.
    second=request(cdp,a,f'/api/documents/{doc}/sections','POST',{'name':'Page end section'})['data']['section_id']
    placement=dict(start_page=1,start_y=390,end_page=1,end_y=None,start_view_box=[0,0,612,792],end_view_box=[0,0,612,792],page_count=2,expected_revision=0)
    assert request(cdp,a,f'/api/versions/{version}/sections/{second}/placement','POST',placement)['status']==200
    # With Sections closed there are no PDF boundary rails, ticks or labels.
    cdp.wait(a,"document.querySelector('iframe').contentDocument.querySelectorAll('.section-structure-marker').length===0")
    for zoom in [.5,1,1.5,2]:
        cdp.evaluate(a,PDF+f'.currentScale={zoom}');time.sleep(.25)
        assert cdp.evaluate(a,"document.querySelector('iframe').contentDocument.querySelectorAll('.section-structure-marker').length===0")
    for rotation in [90,0]:
        cdp.evaluate(a,PDF+f'.pagesRotation={rotation}');time.sleep(.25)
        assert cdp.evaluate(a,"document.querySelector('iframe').contentDocument.querySelectorAll('.section-structure-marker').length===0")
    cdp.evaluate(a,PDF+'.currentScale=.5')
    for spread in [0,1,2]:
        change(cdp,a,'#review-spread',spread);time.sleep(.25)
        assert cdp.evaluate(a,"document.querySelector('iframe').contentDocument.querySelectorAll('.section-structure-marker').length===0")
    third=request(cdp,a,f'/api/documents/{doc}/sections','POST',{'name':'Spread end section'})['data']['section_id']
    placement.update(start_page=2,start_y=None,end_page=2,end_y=None)
    assert request(cdp,a,f'/api/versions/{version}/sections/{third}/placement','POST',placement)['status']==200
    change(cdp,a,'#review-spread',1);time.sleep(.4)
    assert cdp.evaluate(a,"""(()=>{const d=document.querySelector('iframe').contentDocument;
      const right=Math.max(...[...d.querySelectorAll('.page')].map(p=>p.getBoundingClientRect().right));
      return [...document.querySelectorAll('.section-feedback-card:not([hidden])')].every(c=>c.getBoundingClientRect().left>=right);})()"""),'Section feedback left the right rail'
    # Feedback remains available even though boundary overlays are hidden.
    for mode in ['expanded','minimized','hidden']:
        change(cdp,a,'#comments-visibility',mode);time.sleep(.25)
        assert cdp.evaluate(a,"document.querySelector('iframe').contentDocument.querySelectorAll('.section-structure-marker').length===0")
        if mode=='hidden':assert cdp.evaluate(a,"document.querySelector('#thread-list').hidden")
        if mode=='minimized':assert cdp.evaluate(a,"document.querySelector('.section-feedback-marker:not([hidden])')!==null")
    change(cdp,a,'#comments-visibility','expanded')
    # Active spread presence paints at most two pages for a participant.
    change(cdp,b,'#review-spread',0);time.sleep(.7)
    cdp.wait(a,"document.querySelector('iframe').contentDocument.querySelectorAll('.review-page-presence').length===1")
    screenshot(cdp,a,'c2-presence-one-page')
    change(cdp,b,'#review-spread',1);time.sleep(.7)
    try:
        cdp.wait(a,"document.querySelector('iframe').contentDocument.querySelectorAll('.review-page-presence').length===2")
    except AssertionError:
        raise AssertionError(cdp.evaluate(b,"(()=>{const v=document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer;const p=v.getPageView(v.currentPageNumber-1).div;return {mode:v.spreadMode,page:v.currentPageNumber,pages:[...p.closest('.spread').querySelectorAll(':scope > .page')].map(p=>p.dataset.pageNumber),presence:document.querySelector('#review-presence').textContent};})()"))
    screenshot(cdp,a,'c2-presence-two-pages')
    context=cdp.call('Target.createBrowserContext')['browserContextId']
    target=cdp.call('Target.createTarget',{'url':'about:blank','browserContextId':context})['targetId']
    third_session=cdp.call('Target.attachToTarget',{'targetId':target,'flatten':True})['sessionId']
    cdp.call('Runtime.enable',session=third_session);cdp.call('Network.enable',session=third_session)
    cdp.call('Network.setCookie',{'name':'pdf_review_session','value':fixture['admin_cookie'],'url':base,'httpOnly':True,'sameSite':'Lax'},third_session)
    navigate(cdp,third_session,base+'/account')
    cdp.wait(third_session,"document.querySelector('meta[name=csrf-token]')!==null")
    admin_id=request(cdp,third_session,'/api/reviewers')['data']['current_reviewer']['user_id']
    cdp.evaluate(a,f'''(async()=>{{const data=new URLSearchParams({{csrf_token:document.querySelector('meta[name=csrf-token]').content,user_id:{json.dumps(admin_id)},role:'viewer',action:'grant'}});await fetch('/documents/{doc}/access',{{method:'POST',body:data}})}})()''')
    navigate(cdp,third_session,base+f'/versions/{version}/view',True)
    cdp.wait(a,"document.querySelector('iframe').contentDocument.querySelectorAll('.review-page-presence').length===3")
    screenshot(cdp,a,'c2-presence-multiple-avatars')
    # A second tab for the same person still paints one aggregate spread.
    assert cdp.evaluate(a,"[...document.querySelector('iframe').contentDocument.querySelectorAll('.review-page-presence')].every(e=>e.textContent.trim().length>0)")
    # Owner policy change while both browsers are connected removes forbidden content.
    navigate(cdp,a,base+f'/documents/{doc}')
    assert cdp.evaluate(a,"!document.querySelector('[data-review-settings],[data-sections]')")
    navigate(cdp,a,base+f'/versions/{version}/view',True)
    cdp.wait(a,"document.querySelector('[data-review-settings]')!==null")
    cdp.evaluate(a,"document.querySelector('[data-review-settings]').click()")
    cdp.wait(a,"document.querySelector('[name=visibility_policy]')!==null")
    screenshot(cdp,a,'c2-owner-settings')
    cdp.evaluate(a,"document.querySelector('[name=visibility_policy]').value='isolated';document.querySelector('.settings-form').requestSubmit()")
    cdp.wait(b,"document.querySelector('#comments-menu').textContent.includes('Isolated review') && !document.body.textContent.includes('Owner text thread')")
    assert request(cdp,b,f'/api/versions/{version}/threads')['data']['threads']==[]
    screenshot(cdp,b,'c2-isolated-review')
    # Palette UI and immediate presentation refresh.
    navigate(cdp,a,base+'/account');cdp.wait(a,"document.querySelectorAll('.review-swatch').length===10")
    screenshot(cdp,a,'c2-review-palette')
    cdp.evaluate(a,"document.querySelectorAll('[name=review_color]')[5].checked=true;document.querySelector('.review-palette').requestSubmit()")
    cdp.wait(a,"document.querySelectorAll('.review-swatch').length===10")
    # New version starts unmapped; outline preview makes no silent writes.
    navigate(cdp,a,base+f'/versions/{other}/view?sections=edit',True)
    assert all(s['placement'] is None for s in request(cdp,a,f'/api/versions/{other}/review-context')['data']['sections'])
    cdp.evaluate(a,"document.querySelector('[data-sections]').click()")
    cdp.wait(a,"document.querySelector('.sections-workspace')!==null")
    cdp.evaluate(a,"[...document.querySelectorAll('.sections-panel button, dialog button')].find(b=>b.textContent==='Import outline...').click()")
    cdp.wait(a,"document.querySelectorAll('.outline-candidate').length===3")
    assert cdp.evaluate(a,"[...document.querySelectorAll('.outline-candidate input[type=checkbox]')].filter(i=>i.checked).length===2")
    screenshot(cdp,a,'c2-outline-preview')
    cdp.evaluate(a,"const rows=document.querySelectorAll('.outline-candidate');rows[0].querySelectorAll('input')[1].value='Edited outline section';document.querySelector('dialog[open] form').requestSubmit()")
    cdp.wait(a,"document.querySelector('.sections-workspace')!==null")
    cdp.wait(a,f"fetch('/api/versions/{other}/review-context').then(r=>r.json()).then(d=>d.sections.filter(s=>s.placement).length===2)")
    cdp.evaluate(a,"document.querySelector('.sections-panel .dialog-header button:last-child').click()")
    assert len([s for s in request(cdp,a,f'/api/versions/{other}/review-context')['data']['sections'] if s['placement']])==2
    # Responsive review and structure at every requested viewport.
    for width,height in [(1440,900),(1280,800),(1024,768),(768,1024),(390,844)]:
        viewport(cdp,a,width,height);time.sleep(.25);screenshot(cdp,a,f'c2-responsive-{width}')
        for mode in ['expanded','minimized','hidden']:
            change(cdp,a,'#comments-visibility',mode);time.sleep(.2);screenshot(cdp,a,f'c2-{mode}-{width}')
        for control,name,selector in [('data-review-settings','settings','[name=visibility_policy]'),
                ('data-sections','sections','.sections-workspace'),(None,'palette','.review-palette')]:
            navigate(cdp,a,base+(f'/versions/{version}/view' if control else '/account'),bool(control))
            if control:
                cdp.wait(a,f'document.querySelector("[{control}]")!==null')
                cdp.evaluate(a,f'document.querySelector("[{control}]").click()')
            cdp.wait(a,f'document.querySelector({json.dumps(selector)})!==null')
            assert cdp.evaluate(a,'document.documentElement.scrollWidth<=innerWidth+1'),f'{name} overflow at {width}'
            screenshot(cdp,a,f'c2-{name}-{width}')
        navigate(cdp,a,base+f'/versions/{other}/view?sections=edit',True)
    cdp.call('Target.closeTarget',{'targetId':target})
    galleries(cdp,a)
    print('PASS C2 viewer preferences, owner sections, visual boundary capture, feedback, shared/isolated review, palette, outline confirmation, zoom/rotation/spreads, right rail, presence and responsive screenshots',flush=True)


def galleries(cdp,session):
    files=sorted(p for p in ARTIFACTS.glob('c2-*.png') if not p.name.startswith('c2-gallery-'))
    viewport(cdp,session,1600,1000)
    for index in range(0,len(files),6):
        cards=''.join('<figure><figcaption>'+html.escape(p.stem)+'</figcaption><img src="data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()+'"></figure>' for p in files[index:index+6])
        markup='<style>body{margin:0;display:grid;grid-template-columns:repeat(3,1fr);background:#ddd;font:12px system-ui}figure{margin:4px;padding:4px;background:white}img{width:100%;height:442px;object-fit:contain}</style>'+cards
        cdp.call('Page.navigate',{'url':'data:text/html;base64,'+base64.b64encode(markup.encode()).decode()},session)
        cdp.wait(session,"document.images.length>0 && [...document.images].every(i=>i.complete)")
        screenshot(cdp,session,f'c2-gallery-{index//6+1}')
