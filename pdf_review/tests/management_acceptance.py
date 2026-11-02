"""Focused management interaction checks; use browser_sanity.py --management-ui."""
import json
import time
from tests.viewer_acceptance import screenshot,viewport,key,PDF


def run_management(cdp,a,fixture,base):
    doc=fixture['document_id'];version=fixture['versions'][0]
    viewport(cdp,a,1440,900)
    url=cdp.evaluate(a,'location.href')
    def evaluate(script):
        cdp.wait(a,"!document.querySelector('[aria-busy=true]')")
        return cdp.evaluate(a,script)
    def wait(script):return cdp.wait(a,script)
    def open_sections():
        evaluate("document.querySelector('[data-sections]').click()")
        wait("document.querySelector('.sections-panel .sections-workspace')!==null")
    def open_settings():
        evaluate("document.querySelector('[data-review-settings]').click()")
        wait("document.querySelector('dialog .settings-form')!==null")
    open_settings()
    assert evaluate("document.querySelector('dialog').contains(document.activeElement)")
    screenshot(cdp,a,'management-settings-1440')
    # Invalid save stays open and preserves the selected values.
    evaluate("(()=>{const f=document.querySelector('.settings-form');const option=document.createElement('option');option.value='invalid';f.querySelector('[name=default_scope]').append(option);f.querySelector('[name=default_scope]').value='invalid';f.requestSubmit();})()")
    wait("document.querySelector('.dialog-error')?.textContent.length>0")
    assert evaluate("document.querySelector('[name=default_scope]').value==='invalid'")
    evaluate("document.querySelector('[name=default_scope]').value='mine';document.querySelector('.settings-form').requestSubmit()")
    wait("!document.querySelector('dialog[open]')")
    assert evaluate('location.href')==url
    open_settings();assert evaluate("document.querySelector('[name=default_scope]').value==='mine'")
    key(cdp,a,'Escape',27);wait("!document.querySelector('dialog[open]')")
    assert evaluate("document.activeElement===document.querySelector('#review-view-menu > summary')")
    open_sections()
    evaluate("[...document.querySelectorAll('.sections-panel button, dialog button')].find(b=>b.textContent==='+ Add section').click()")
    assert evaluate("document.activeElement===document.querySelector('#section-detail-form [name=name]')")
    screenshot(cdp,a,'management-add-section-1440')
    evaluate("(()=>{const n=document.querySelector('[name=name]');n.value='Chapter one';n.dispatchEvent(new Event('input'));const p=document.querySelector('[name=prompt]');p.value='What changed?';p.dispatchEvent(new Event('input'));document.querySelector('#section-detail-form').requestSubmit();})()")
    wait("document.querySelector('.section-master-item')?.textContent.includes('Chapter one')")
    first=evaluate("document.querySelector('.section-master-item').dataset.sectionId")
    evaluate("[...document.querySelectorAll('.sections-panel button, dialog button')].find(b=>b.textContent==='+ Add section').click();const n=document.querySelector('[name=name]');n.value='Chapter two';n.dispatchEvent(new Event('input'));document.querySelector('#section-detail-form').requestSubmit()")
    wait("document.querySelectorAll('.section-master-item').length===2")
    second=evaluate("document.querySelector('[aria-current=true]').dataset.sectionId")
    evaluate("document.querySelector('.section-master-item').focus()")
    key(cdp,a,'ArrowDown',40)
    assert evaluate("document.querySelector('[name=name]').value==='Chapter two'")
    evaluate("[...document.querySelectorAll('.sections-panel button, dialog button')].find(b=>b.textContent==='Move up').click()")
    wait("document.querySelector('.section-master-item').textContent.includes('Chapter two')")
    evaluate("(()=>{const n=document.querySelector('[name=name]');n.value='Interlude';n.dispatchEvent(new Event('input'));document.querySelector('#section-detail-form').requestSubmit();})()")
    wait("document.querySelector('.section-master-item').textContent.includes('Interlude')")
    viewport(cdp,a,1024,768);screenshot(cdp,a,'management-sections-detail-1024')
    evaluate("[...document.querySelectorAll('.sections-panel button, dialog button')].find(b=>b.textContent==='Delete').click()")
    wait("document.querySelector('.dialog-confirmation[open]')!==null")
    evaluate("[...document.querySelectorAll('.dialog-confirmation button')].find(b=>b.textContent==='Delete').click()")
    wait("document.querySelectorAll('.section-master-item').length===1")
    assert evaluate('location.href')==url
    # Outline preview is a secondary utility dialog and returns to the same workspace.
    evaluate("[...document.querySelectorAll('.sections-panel button, dialog button')].find(b=>b.textContent==='Import outline…').click()")
    wait("document.querySelectorAll('.outline-candidate').length===3")
    screenshot(cdp,a,'management-outline-1024')
    evaluate("document.querySelectorAll('.outline-candidate')[1].querySelector('input[type=checkbox]').checked=false;[...document.querySelectorAll('.sections-panel button, dialog button')].find(b=>b.textContent==='Create selected sections').click()")
    wait("document.querySelectorAll('.section-master-item').length===3")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.section-management-line').length===4")
    assert evaluate("!document.querySelector('dialog[open]') && !document.querySelector('.viewer-workspace').inert")
    evaluate(PDF+'.currentScale=.5')
    top=evaluate("document.querySelector('.sections-panel').getBoundingClientRect().top")
    evaluate(PDF+'.container.scrollTop=200')
    wait(PDF+'.container.scrollTop>=199')
    assert abs(evaluate("document.querySelector('.sections-panel').getBoundingClientRect().top")-top)<1
    evaluate(PDF+'.container.scrollTop=0')
    viewport(cdp,a,1440,900)
    screenshot(cdp,a,'sections-panel-lines-1440')
    viewport(cdp,a,1024,768)
    # Use the original unmapped section; archived/outline sections are independent.
    evaluate(f"document.querySelector('[data-section-id={json.dumps(first)}]').click()")
    evaluate("[...document.querySelectorAll('.sections-panel button, dialog button')].find(b=>b.textContent==='Edit boundaries in document').click()")
    wait("!document.querySelector('dialog[open]') && !document.querySelector('#section-editor').hidden")
    assert evaluate("document.querySelector('#section-choice').value")==first
    screenshot(cdp,a,'management-boundary-strip-1024')
    # Outline owns the existing ranges, so Cancel an unsaved preview rather than
    # attempting an overlapping write. Canonical boundaries stay unmapped.
    evaluate("(()=>{document.querySelector('#section-set-start').click();const p=document.querySelector('iframe').contentDocument.querySelector('.page'),b=p.getBoundingClientRect();p.dispatchEvent(new MouseEvent('click',{clientX:b.left+20,clientY:b.top+2,bubbles:true}));document.querySelector('#section-editor-cancel').click();})()")
    wait("document.querySelector('.sections-panel .sections-workspace')!==null")
    assert evaluate("document.querySelector('[aria-current=true]').dataset.sectionId")==first
    assert evaluate("document.querySelector('.placement-summary').textContent.includes('Unmapped')")
    # Done with no unsaved preview returns and preserves selection as well.
    evaluate("[...document.querySelectorAll('.sections-panel button, dialog button')].find(b=>b.textContent==='Edit boundaries in document').click()")
    wait("!document.querySelector('#section-editor').hidden")
    evaluate("document.querySelector('#section-editor-close').click()")
    wait("document.querySelector('.sections-panel .sections-workspace')!==null")
    assert evaluate("document.querySelector('[aria-current=true]').dataset.sectionId")==first
    # Done also commits a real changed placement using the existing validator.
    mapped=evaluate("document.querySelectorAll('.section-master-item')[1].dataset.sectionId")
    evaluate("document.querySelectorAll('.section-master-item')[1].click();[...document.querySelectorAll('.sections-panel button, dialog button')].find(b=>b.textContent==='Edit boundaries in document').click()")
    wait(f"!document.querySelector('#section-editor').hidden && document.querySelector('#section-choice').value==={json.dumps(mapped)} && !document.querySelector('#section-editor-close').disabled")
    preview=evaluate("(()=>{document.querySelector('#section-set-end').click();const p=document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer.getPageView(0),b=p.div.getBoundingClientRect(),y=p.viewport.convertToViewportPoint(306,450)[1]*p.div.clientHeight/p.viewport.height;p.div.dispatchEvent(new MouseEvent('click',{clientX:b.left+30,clientY:b.top+p.div.clientTop+y,bubbles:true}));return document.querySelector('#section-boundary-preview').textContent;})()")
    assert '450' in preview,preview
    evaluate("document.querySelector('#section-editor-close').click()")
    wait("document.querySelector('#section-editor').hidden && document.querySelector('.placement-summary')?.textContent.includes('43%')")
    assert evaluate("document.querySelector('[aria-current=true]').dataset.sectionId")==mapped
    assert evaluate("document.querySelector('.placement-summary').textContent.includes('43%')"),evaluate("document.querySelector('.placement-summary').textContent")
    viewport(cdp,a,768,1024);screenshot(cdp,a,'management-return-workspace-768')
    assert evaluate('location.href')==url
    assert evaluate("document.querySelector('.sections-panel').getBoundingClientRect().right<=innerWidth && document.querySelector('.sections-panel').getBoundingClientRect().bottom<=innerHeight")
    evaluate("document.querySelector('.sections-panel .dialog-header button').focus()")
    key(cdp,a,'Escape',27);wait("!document.querySelector('.sections-panel')")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.section-management-line').length===0")
    # Settings stays on the document page; Sections enters its PDF with the panel.
    cdp.call('Page.navigate',{'url':base+f'/documents/{doc}'},a)
    wait("document.querySelector('[data-sections]')!==null && document.documentElement.dataset.managementReady==='true'")
    document_url=evaluate('location.href');open_settings();key(cdp,a,'Escape',27)
    wait("!document.querySelector('dialog[open]')")
    wait("document.activeElement===document.querySelector('[data-review-settings]')")
    evaluate("document.querySelector('[data-sections]').click()")
    wait("location.pathname.includes('/versions/') && document.querySelector('.sections-panel .sections-workspace')!==null && document.querySelector('#realtime-status')?.textContent==='Live'")
    assert evaluate("!document.querySelector('dialog[open]')")
    print('PASS fixed non-modal Sections panel, inline settings/CRUD, all section lines, stationary panel during PDF scroll, outline import, boundary Done/Cancel, keyboard/focus and document entry',flush=True)
