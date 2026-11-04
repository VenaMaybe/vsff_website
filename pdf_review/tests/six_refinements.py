"""Synthetic browser regression for the six viewer refinements."""
import json
import time
from tests.viewer_acceptance import PDF, SELECT, viewport, screenshot, change, key
from tests.beta_c2_acceptance import request


def run_six(cdp, a, b, fixture, base):
    def ev(script): return cdp.evaluate(a, script)
    def wait(script): return cdp.wait(a, script)
    viewport(cdp, a, 1440, 1000)
    ev(PDF+'.currentScale=.5')
    # A real text thread carries its root author's color through selection.
    ev(SELECT)
    wait("!document.querySelector('#comment-selection-button').disabled")
    ev("document.querySelector('#comment-selection-button').click()")
    assert ev("document.activeElement===document.querySelector('#selection-comment-body')"),ev("({width:innerWidth,coarse:matchMedia('(any-pointer:coarse)').matches,primaryCoarse:matchMedia('(pointer:coarse)').matches,active:document.activeElement.outerHTML.slice(0,250)})")
    ev("document.querySelector('#selection-comment-body').value='Six refinements comment';document.querySelector('#selection-comment-form').requestSubmit()")
    wait("document.querySelector('#thread-list .thread-card')!==null")
    assert ev("(()=>{const c=document.querySelector('#thread-list .thread-card.active'),p=document.createElement('i');p.style.borderLeftColor='color-mix(in srgb,'+c.style.getPropertyValue('--review-color')+' 78%,white)';document.body.append(p);const ok=getComputedStyle(p).borderLeftColor===getComputedStyle(c).borderLeftColor;p.remove();return ok;})()")
    ev("document.querySelector('[data-sections]').click()")
    wait("document.querySelector('.sections-workspace')!==null")
    # Every mode change must position the left rail against the actual PDF edge.
    for mode in ['hidden', 'expanded', 'minimized', 'expanded']:
        change(cdp, a, '#comments-visibility', mode)
        wait("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(true))))")
        assert ev("(()=>{const c=document.querySelector('.sections-panel').getBoundingClientRect(),f=document.querySelector('iframe').getBoundingClientRect(),p="+PDF+".getPageView(0).div.getBoundingClientRect();return Math.abs(c.right+12-f.left-p.left)<2;})()")
    # Search adopts the native controls and keeps PDF.js's matching/navigation.
    ev("document.querySelector('[data-pdf-control=viewFindButton]').click()")
    wait("document.querySelector('.search-panel #findInput')!==null")
    ev("document.querySelector('#findInput').value='Review';document.querySelector('#findInput').dispatchEvent(new Event('input',{bubbles:true}))")
    wait("document.querySelector('#findResultsCount').textContent.includes('of')")
    assert ev("document.querySelector('.search-panel .left-card-pin')!==null&&!document.querySelector('iframe').contentDocument.querySelector('#findbar')")
    assert ev("(()=>{const grid=document.querySelector('.review-find-options'),rows=[...grid.querySelectorAll('.toggleButton')];if(grid.tagName!=='DIV'||rows.length!==4)return false;const r=rows.map(x=>x.getBoundingClientRect());return Math.abs(r[0].top-r[1].top)<1&&Math.abs(r[2].top-r[3].top)<1&&r[2].top>r[0].bottom&&rows.every(row=>{const a=row.querySelector('input').getBoundingClientRect(),b=row.querySelector('label').getBoundingClientRect();return Math.abs((a.top+a.bottom-b.top-b.bottom)/2)<1;});})()")
    # Dragging a utility card past the document start clamps it; neighbors pack down.
    ev(PDF+'.container.scrollTop=0');time.sleep(.2)
    h=ev("(()=>{const r=document.querySelector('.search-panel .dialog-header').getBoundingClientRect();return {x:r.left+50,y:r.top+12};})()")
    cdp.call('Input.dispatchMouseEvent',{'type':'mousePressed','x':h['x'],'y':h['y'],'button':'left','clickCount':1},a)
    cdp.call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':h['x'],'y':0,'buttons':1},a)
    cdp.call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':h['x'],'y':0,'button':'left','clickCount':1},a)
    time.sleep(.25)
    bounded="(()=>{const f=document.querySelector('iframe').getBoundingClientRect(),top="+PDF+".getPageView(0).div.getBoundingClientRect().top+f.top;return [...document.querySelectorAll('.left-card')].every(c=>c.getBoundingClientRect().top>=top-.5&&c.scrollHeight<=c.clientHeight+1);})()"
    assert ev(bounded),ev("(()=>{const f=document.querySelector('iframe').getBoundingClientRect();return {page:"+PDF+".getPageView(0).div.getBoundingClientRect().top+f.top,cards:[...document.querySelectorAll('.left-card')].map(c=>({cls:c.className,top:c.getBoundingClientRect().top,height:c.clientHeight,scroll:c.scrollHeight,style:c.style.cssText,transform:getComputedStyle(c).transform,parent:c.parentElement.getBoundingClientRect().top,animation:c.getAnimations().length}))};})()")
    ev("document.querySelector('.search-panel .left-card-pin').click()")
    time.sleep(.2);assert ev(bounded)
    ev("document.querySelector('.search-panel .left-card-pin').click()")
    time.sleep(.2);assert ev(bounded)
    screenshot(cdp,a,'search-options-grid')
    ev("document.querySelector('#findNextButton').click()")
    screenshot(cdp, a, 'six-search-left-card')
    key(cdp, a, 'Escape', 27)
    wait("!document.querySelector('.search-panel')")
    key(cdp, a, 'f', 70, 2)
    wait("document.querySelector('.search-panel #findInput')!==null")
    ev("document.querySelector('.search-panel .dialog-header button:last-child').click()")
    assert ev("!document.querySelector('iframe').contentWindow.PDFViewerApplication.findBar.opened")
    # The reviewer checklist lives in the reusable left card.
    ev("document.querySelector('[data-comment-filters]').click()")
    wait("document.querySelector('.comment-filter-panel')!==null")
    ev("document.querySelector('.comment-filter-panel input[value=people]').click()")
    wait("document.querySelector('.filter-reviewers input')!==null")
    ev("document.querySelector('.filter-reviewers input').click()")
    wait("document.querySelector('#thread-list .thread-card')===null")
    ev("document.querySelector('.comment-filter-panel input[value=all]').click()")
    wait("document.querySelector('#thread-list .thread-card')!==null")
    assert ev("document.querySelector('.comment-filter-panel input[value=all]').checked")
    screenshot(cdp,a,'six-comment-filter-card')
    ev("document.querySelector('.comment-filter-panel .dialog-header button:last-child').click()")
    # Section thoughts use the section end as their bottom anchor, even selected.
    doc, version = fixture['document_id'], fixture['versions'][0]
    sid=request(cdp,a,f'/api/documents/{doc}/sections','POST',{'name':'Bottom-aligned thoughts'})['data']['section_id']
    box=ev(PDF+'.getPageView(1).viewport.viewBox')
    request(cdp,a,f'/api/versions/{version}/sections/{sid}/placement','POST',{
        'start_page':1,'start_y':None,'start_view_box':box,'end_page':2,'end_y':300,'end_view_box':box,'page_count':2,'expected_revision':0})
    wait("document.querySelector('.section-feedback-card')!==null")
    ev("document.querySelector('.section-feedback-card').click()")
    time.sleep(.25)
    assert ev("(()=>{const c=document.querySelector('.section-feedback-card').getBoundingClientRect(),f=document.querySelector('iframe').getBoundingClientRect(),p="+PDF+".getPageView(1),r=p.div.getBoundingClientRect(),y=p.viewport.convertToViewportPoint(0,300)[1]*p.div.clientHeight/p.viewport.height;return Math.abs(c.bottom-f.top-r.top-p.div.clientTop-y)<2;})()")
    ev("document.querySelector('.sections-panel .dialog-header button:last-child').click()")
    # Mobile tools stay beside the PDF and are reachable by document scrolling.
    cdp.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True},a)
    ev("document.querySelector('[data-pdf-control=viewFindButton]').click()")
    wait("document.querySelector('.search-panel #findInput')!==null")
    time.sleep(.2)
    assert ev("document.querySelector('.search-panel').scrollHeight<=document.querySelector('.search-panel').clientHeight+1")
    aligned="(()=>{const c=document.querySelector('.search-panel').getBoundingClientRect(),f=document.querySelector('iframe').getBoundingClientRect();return Math.min(...[..."+PDF+".viewer.querySelectorAll('.page')].map(p=>Math.abs(c.right+12-f.left-p.getBoundingClientRect().left)))<2;})()"
    wait(aligned)
    # Let pending origin maintenance settle, then pan left to reach the rail.
    time.sleep(.4)
    ev("(()=>{const c=document.querySelector('.search-panel').getBoundingClientRect(),f=document.querySelector('iframe').getBoundingClientRect();"+PDF+".container.scrollLeft+=c.left-f.left-8;})()")
    time.sleep(.3)
    assert ev(aligned)
    bounds=ev("(()=>{const r=document.querySelector('.search-panel').getBoundingClientRect();return {left:r.left,right:r.right,width:innerWidth};})()")
    assert bounds['left']>=0 and bounds['right']<=bounds['width'],bounds
    screenshot(cdp,a,'six-mobile-search-card')
    # Touch selection keeps its text/handles and exposes a separate comment action.
    cdp.call('Emulation.setTouchEmulationEnabled',{'enabled':True,'maxTouchPoints':2},a)
    ev(SELECT)
    wait("!document.querySelector('#comment-selection-button').hidden")
    assert ev("matchMedia('(pointer:coarse)').matches")
    assert ev("(()=>{const w=document.querySelector('iframe').contentWindow,b=document.querySelector('#comment-selection-button').getBoundingClientRect();const selected=w.getSelection().toString();const menu=new w.MouseEvent('contextmenu',{bubbles:true,cancelable:true});w.getSelection().anchorNode.parentElement.dispatchEvent(menu);return selected.length>0&&w.getSelection().toString()===selected&&menu.defaultPrevented&&b.width>80&&b.height>=44&&b.right<=innerWidth&&b.bottom<=innerHeight&&b.top>innerHeight-100;})()")
    assert ev("(()=>{const input=document.querySelector('#findInput'),menu=new MouseEvent('contextmenu',{bubbles:true,cancelable:true});input.dispatchEvent(menu);return !menu.defaultPrevented;})()")
    normal_selection_action=ev("({left:document.querySelector('#comment-selection-button').style.left,top:document.querySelector('#comment-selection-button').style.top})")
    ev("document.querySelector('#comment-selection-button').click()")
    wait("!document.querySelector('#selection-comment-composer').hidden")
    docked="(()=>{const r=document.querySelector('#selection-comment-composer').getBoundingClientRect(),f=document.querySelector('iframe').getBoundingClientRect(),v=visualViewport;return Math.abs(r.right-Math.min(f.right,v.offsetLeft+v.width)+12)<2&&Math.abs(r.bottom-Math.min(f.bottom,v.offsetTop+v.height)+16)<2&&r.top>=f.top;})()"
    wait(docked)
    assert ev("document.activeElement!==document.querySelector('#selection-comment-body')")
    # Reopening must not force focus either, and must preserve the existing draft.
    ev("document.querySelector('#selection-comment-body').value='Existing draft';document.querySelector('#comment-selection-button').click()")
    assert ev("document.activeElement!==document.querySelector('#selection-comment-body')&&document.querySelector('#selection-comment-body').value==='Existing draft'")
    assert ev("parseFloat(getComputedStyle(document.querySelector('#selection-comment-body')).fontSize)>=16")
    # Tapping the card label/quote must not activate the editor.
    point=ev("(()=>{const r=document.querySelector('.composer-label').getBoundingClientRect();return {x:r.left+10,y:r.top+r.height/2};})()")
    for kind in ['touchStart', 'touchEnd']:
        cdp.call('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[point] if kind=='touchStart' else []},a)
    assert ev("document.activeElement!==document.querySelector('#selection-comment-body')")
    # A first touch must request keyboard focus without Safari's reveal scroll.
    ev("window.testFocusOptions=null;window.testEditorFocus=document.querySelector('#selection-comment-body').focus;document.querySelector('#selection-comment-body').focus=function(options){window.testFocusOptions=options;return testEditorFocus.call(this,options)}")
    point=ev("(()=>{const r=document.querySelector('#selection-comment-body').getBoundingClientRect();return {x:r.left+20,y:r.top+20};})()")
    for kind in ['touchStart', 'touchEnd']:
        cdp.call('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[point] if kind=='touchStart' else []},a)
    assert ev("document.activeElement===document.querySelector('#selection-comment-body')")
    assert ev("window.testFocusOptions?.preventScroll===true")
    assert ev("(()=>{const e=document.querySelector('#selection-comment-body'),p=new PointerEvent('pointerdown',{bubbles:true,cancelable:true,pointerType:'touch',isPrimary:true});return e.dispatchEvent(p)&&!p.defaultPrevented;})()")
    ev("document.querySelector('#selection-comment-body').focus=testEditorFocus;delete window.testEditorFocus;delete window.testFocusOptions")
    assert ev("document.querySelector('#selection-comment-quote').textContent.includes('Review sentence')")
    wait(docked)
    ev(PDF+'.container.scrollTop+=100')
    wait(docked)
    # A smaller visible area models keyboard/viewport resizing without losing the draft.
    ev("document.querySelector('#selection-comment-body').value='Draft survives viewport resize'")
    editor_height=ev("document.querySelector('#selection-comment-body').getBoundingClientRect().height")
    composer_height=ev("document.querySelector('#selection-comment-composer').getBoundingClientRect().height")
    assert abs(editor_height-72)<1
    assert ev("(()=>{const e=document.querySelector('#selection-comment-body'),s=getComputedStyle(e),scale=e.getBoundingClientRect().width/e.offsetWidth;return Math.abs(parseFloat(s.fontSize)*scale-13)<.1;})()")
    cdp.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':500,'deviceScaleFactor':1,'mobile':True},a)
    wait(docked)
    assert ev("document.querySelector('#selection-comment-body').value==='Draft survives viewport resize'")
    assert abs(ev("document.querySelector('#selection-comment-body').getBoundingClientRect().height")-editor_height)<1
    assert abs(ev("document.querySelector('#selection-comment-composer').getBoundingClientRect().height")-composer_height)<1
    assert ev("(()=>{const a=document.querySelector('.selection-editor-field').getBoundingClientRect(),b=document.querySelector('.composer-actions').getBoundingClientRect();return a.bottom<=b.top;})()")
    # Model Safari's independent visual viewport pan, rather than shrinking both
    # layout + visual viewports together (which cannot reproduce the old bug).
    ev("window.testNativeViewport=visualViewport;window.testViewportDescriptor=Object.getOwnPropertyDescriptor(window,'visualViewport');Object.defineProperty(window,'visualViewport',{configurable:true,value:{offsetLeft:0,offsetTop:430,width:390,height:320}});testNativeViewport.dispatchEvent(new Event('resize'))")
    wait("(()=>{const r=document.querySelector('#selection-comment-composer').getBoundingClientRect();return r.top>=442&&Math.abs(r.bottom-734)<2;})()")
    assert abs(ev("document.querySelector('#selection-comment-composer').getBoundingClientRect().height")-composer_height)<1
    assert ev("(()=>{const c=document.querySelector('#selection-comment-composer'),r=c.getBoundingClientRect(),e=document.querySelector('#selection-comment-body').getBoundingClientRect(),b=c.querySelector('[type=submit]').getBoundingClientRect();return c.parentElement===document.body&&getComputedStyle(c).position==='fixed'&&e.top>=r.top&&b.bottom<=r.bottom&&c.scrollHeight<=c.clientHeight+1&&document.activeElement===document.querySelector('#selection-comment-body');})()")
    ev("Object.defineProperty(window,'visualViewport',testViewportDescriptor);testNativeViewport.dispatchEvent(new Event('resize'));delete window.testNativeViewport;delete window.testViewportDescriptor")
    wait(docked)
    ev("document.querySelector('#cancel-selection-comment').click()")
    assert ev("!document.querySelector('#comment-selection-button').hidden")
    action_position="({left:document.querySelector('#comment-selection-button').style.left,top:document.querySelector('#comment-selection-button').style.top})"
    assert ev(action_position)==normal_selection_action
    ev("visualViewport.dispatchEvent(new Event('resize'));visualViewport.dispatchEvent(new Event('scroll'))")
    assert ev(action_position)==normal_selection_action
    cdp.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True},a)
    wait("(()=>{const b=document.querySelector('#comment-selection-button').getBoundingClientRect();return Math.abs(b.bottom-Math.min(document.querySelector('iframe').getBoundingClientRect().bottom,visualViewport.offsetTop+visualViewport.height)+16)<2;})()")
    assert ev("document.querySelector('#selection-comment-composer').parentElement.classList.contains('review-panel')")
    assert ev("parseFloat(getComputedStyle(document.querySelector('#review-page-number')).fontSize)>=16")
    ev("document.querySelector('#review-page-number').focus();document.querySelector('#review-page-number').value='2'")
    key(cdp,a,'Enter',13)
    wait(PDF+'.currentPageNumber===2')
    assert ev("document.activeElement!==document.querySelector('#review-page-number')")
    print('PASS mobile PDF callout cancellation, selection preservation, separate 44px Add comment action and composer',flush=True)
    print('PASS author-color selection, live left-rail alignment, search/filter cards, reviewer checklist, bottom-aligned section thoughts and mobile search',flush=True)
