"""Viewer redesign browser assertions, called by the disposable Chrome harness."""
import base64
import html
import json
from pathlib import Path
import time

ARTIFACTS = Path(__file__).parent / "visual-artifacts"
PDF = "document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer"
SELECT = """(() => {
 const w=document.querySelector('iframe').contentWindow;
 const view=w.PDFViewerApplication.pdfViewer;
 view.currentPageNumber=1;
 const text=view.getPageView(0).div.querySelector('.textLayer span').firstChild;
 const r=w.document.createRange(); r.selectNodeContents(text);
 w.getSelection().removeAllRanges(); w.getSelection().addRange(r);
})()"""


def change(cdp, session, selector, value):
    cdp.evaluate(session, f"document.querySelector({json.dumps(selector)}).value={json.dumps(str(value))}; document.querySelector({json.dumps(selector)}).dispatchEvent(new Event('change'))")


def viewport(cdp, session, width, height):
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False}, session)
    time.sleep(.18)


def screenshot(cdp, session, name):
    ARTIFACTS.mkdir(exist_ok=True)
    result = cdp.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False}, session)
    (ARTIFACTS / f"{name}.png").write_bytes(base64.b64decode(result["data"]))


def click(cdp, session, selector):
    cdp.evaluate(session, f"(() => {{const e=document.querySelector({json.dumps(selector)});const b=e.getBoundingClientRect();if(b.top<0||b.bottom>innerHeight)e.scrollIntoView({{block:'nearest',inline:'nearest'}});}})()")
    # Menu positioning and scrollIntoView settle on animation frames before a
    # real pointer click. Reading the previous frame's box can hit another row.
    cdp.evaluate(session, "new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
    point = cdp.evaluate(session, f"(() => {{const b=document.querySelector({json.dumps(selector)}).getBoundingClientRect(); return {{x:b.left+b.width/2,y:b.top+b.height/2}};}})()")
    for kind in ['mousePressed', 'mouseReleased']:
        cdp.call('Input.dispatchMouseEvent', {'type': kind, 'button': 'left', 'clickCount': 1, **point}, session)


def key(cdp, session, value, code, modifiers=0):
    for kind in ['keyDown', 'keyUp']:
        cdp.call('Input.dispatchKeyEvent', {'type': kind, 'key': value, 'windowsVirtualKeyCode': code, 'modifiers': modifiers}, session)


def menu_bounds(cdp, session):
    cdp.wait(session, """[...document.querySelectorAll('.toolbar-menu[open] > .toolbar-popover')].every(e=>{const b=e.getBoundingClientRect();return b.left>=0&&b.right<=innerWidth+1&&b.top>=0&&b.bottom<=innerHeight+1&&e.scrollWidth<=e.clientWidth+1;})""")


def inspection_sheets(cdp, session):
    """Browser-rendered galleries of synthetic screenshots for visual inspection."""
    files = sorted(p for p in ARTIFACTS.glob('refine-*.png') if not p.name.startswith('refine-contact-'))
    viewport(cdp, session, 1800, 1040)
    for index in range(0, len(files), 8):
        cards = ''.join('<figure><figcaption>'+html.escape(p.stem)+'</figcaption><img src="data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()+'"></figure>' for p in files[index:index+8])
        markup = '<style>body{margin:0;display:grid;grid-template-columns:repeat(4,1fr);background:#ddd;font:13px system-ui}figure{margin:4px;padding:4px;background:white}figcaption{height:20px}img{width:100%;height:472px;object-fit:contain;display:block}</style>'+cards
        cdp.call('Page.navigate', {'url':'data:text/html;base64,'+base64.b64encode(markup.encode()).decode()}, session)
        cdp.wait(session, "document.querySelectorAll('img').length>0 && [...document.images].every(i=>i.complete)")
        screenshot(cdp, session, f'refine-contact-{index//8+1:02d}')


def menu_search_checks(cdp, session):
    for width, height in [(1440, 900), (1280, 800), (1024, 768), (768, 1024), (390, 844)]:
        viewport(cdp, session, width, height)
        click(cdp, session, '#review-view-menu > summary')
        cdp.wait(session, "document.querySelector('#review-view-menu').open")
        menu_bounds(cdp, session)
        screenshot(cdp, session, f'refine-view-{width}')
        for id in ['review-scroll', 'review-spread']:
            click(cdp, session, f'#{id}-menu > summary')
            cdp.wait(session, f"document.querySelector('#{id}-menu').open")
            menu_bounds(cdp, session)
            assert cdp.evaluate(session, f"document.querySelector('#{id}-menu [aria-checked=true]')!==null")
            screenshot(cdp, session, f'refine-{id}-{width}')
            key(cdp, session, 'Escape', 27)
            assert not cdp.evaluate(session, f"document.querySelector('#{id}-menu').open")
            assert cdp.evaluate(session, "document.querySelector('#review-view-menu').open")
        key(cdp, session, 'Escape', 27)
        click(cdp, session, '#comments-menu > summary')
        menu_bounds(cdp, session)
        screenshot(cdp, session, f'refine-comments-{width}')
        key(cdp, session, 'Escape', 27)
        click(cdp, session, '.identity-menu > summary')
        menu_bounds(cdp, session)
        screenshot(cdp, session, f'refine-account-menu-{width}')
        click(cdp, session, '.viewer-title')
        assert cdp.evaluate(session, "!document.querySelector('.toolbar-menu[open]')")
        # Exercise parent shortcut and the existing native field and handlers.
        key(cdp, session, 'f', 70, 2)
        cdp.wait(session, "document.querySelector('iframe').contentWindow.PDFViewerApplication.findBar.opened")
        cdp.call('Input.insertText', {'text': 'Review'}, session)
        cdp.wait(session, "document.querySelector('iframe').contentDocument.querySelector('#findResultsCount').textContent.length>0 && document.querySelector('iframe').contentDocument.querySelector('#findInput').getAttribute('data-status')!=='pending'")
        assert cdp.evaluate(session, "document.querySelector('iframe').contentWindow.getComputedStyle(document.querySelector('iframe').contentDocument.querySelector('#findInput')).fontSize==='12px'")
        cdp.evaluate(session, "(() => {const d=document.querySelector('iframe').contentDocument; if(!d.querySelector('#findHighlightAll').checked)d.querySelector('#findHighlightAll').click();})()")
        cdp.wait(session, "document.querySelector('iframe').contentWindow.PDFViewerApplication.findController.state.highlightAll")
        screenshot(cdp, session, f'refine-search-{width}')
        args = cdp.evaluate(session, "document.querySelector('iframe').contentDocument.querySelector('#findResultsCount').getAttribute('data-l10n-args')")
        cdp.evaluate(session, "document.querySelector('iframe').contentDocument.querySelector('#findNextButton').click()")
        cdp.wait(session, "document.querySelector('iframe').contentDocument.querySelector('#findResultsCount').getAttribute('data-l10n-args')!==" + json.dumps(args))
        cdp.evaluate(session, "document.querySelector('iframe').contentDocument.querySelector('#findPreviousButton').click()")
        cdp.wait(session, "document.querySelector('iframe').contentDocument.querySelector('#findResultsCount').getAttribute('data-l10n-args')===" + json.dumps(args))
        key(cdp, session, 'Enter', 13)
        key(cdp, session, 'Enter', 13, 8)
        key(cdp, session, 'Escape', 27)
        assert cdp.evaluate(session, "!document.querySelector('iframe').contentWindow.PDFViewerApplication.findBar.opened")
    viewport(cdp, session, 1440, 900)
    # Arrow navigation opens a submenu, chooses native mode and updates checkmarks.
    click(cdp, session, '#review-view-menu > summary')
    cdp.evaluate(session, "document.querySelector('#review-scroll-menu > summary').focus()")
    key(cdp, session, 'ArrowRight', 39)
    key(cdp, session, 'ArrowDown', 40)
    key(cdp, session, 'Enter', 13)
    cdp.wait(session, PDF + '.scrollMode===0')
    assert cdp.evaluate(session, "document.querySelector('[data-menu-input=review-scroll][data-menu-value=\"0\"]').getAttribute('aria-checked')==='true'")
    print('PASS canonical menus/submenus, viewport bounds, checkmarks, keyboard/outside close and native search interactions', flush=True)


def toolbar_fits(cdp, session):
    assert cdp.evaluate(session, """(() => {
      const bar=document.querySelector('.viewer-shell-bar');
      return bar.scrollWidth<=innerWidth && [...bar.querySelectorAll(':scope > *')].every(e=>{
        const b=e.getBoundingClientRect();return b.left>=0 && b.right<=innerWidth+1;
      });
    })()"""), "Toolbar clips/overflows"


def empty_checks(cdp, session):
    viewport(cdp, session, 1440, 900)
    cdp.wait(session, "document.querySelector('iframe').contentDocument.querySelector('.textLayer span')!==null")
    assert cdp.evaluate(session, "document.querySelectorAll('.thread-card').length===0")
    assert cdp.evaluate(session, "document.querySelector('iframe').contentDocument.documentElement.style.getPropertyValue('--review-rail-right')==='0px'")
    assert cdp.evaluate(session, "document.querySelector('.anchor-debug-section').hidden")
    assert cdp.evaluate(session, """(() => {
      const w=document.querySelector('iframe').contentWindow;
      return w.PDFViewerApplication.pdfViewer.annotationEditorMode===-1 &&
        [...w.document.querySelectorAll('#editorModeButtons, .editorParamsToolbar')].every(e=>w.getComputedStyle(e).display==='none');
    })()"""), "Native PDF editors exposed"
    # Real app controls delegate to PDF.js, including native search internals.
    cdp.evaluate(session, "document.querySelector('[data-pdf-control=next]').click()")
    cdp.wait(session, PDF + ".currentPageNumber===2")
    change(cdp, session, '#review-page-number', 1)
    cdp.wait(session, PDF + ".currentPageNumber===1")
    cdp.evaluate(session, "document.querySelector('[data-pdf-control=zoomInButton]').click()")
    change(cdp, session, '#review-scale', '1')
    cdp.wait(session, PDF + ".currentScale===1")
    cdp.evaluate(session, "document.querySelector('[data-pdf-control=viewFindButton]').click(); const d=document.querySelector('iframe').contentDocument;d.querySelector('#findInput').value='Review';d.querySelector('#findInput').dispatchEvent(new Event('input',{bubbles:true}))")
    cdp.wait(session, "document.querySelector('iframe').contentDocument.querySelector('#findResultsCount').textContent.length>0")
    cdp.evaluate(session, "document.querySelector('iframe').contentWindow.PDFViewerApplication.findBar.close()")
    for mode in range(4):
        change(cdp, session, '#review-scroll', mode)
        cdp.wait(session, PDF + f'.scrollMode==={mode}')
    change(cdp, session, '#review-scroll', 0)
    cdp.evaluate(session, "document.querySelector('[data-pdf-control=pageRotateCw]').click()")
    cdp.wait(session, PDF + '.pagesRotation===90')
    cdp.evaluate(session, "document.querySelector('[data-pdf-control=pageRotateCcw]').click()")
    cdp.wait(session, PDF + '.pagesRotation===0')
    for mode in range(3):
        change(cdp, session, '#review-spread', mode)
        cdp.wait(session, PDF + f'.spreadMode==={mode}')
    change(cdp, session, '#review-spread', 0)
    for scale, rotation in [(.5, 0), (1, 0), (1.5, 0), (2, 0), (1, 90)]:
        cdp.evaluate(session, PDF + f'.currentScale={scale};' + PDF + f'.pagesRotation={rotation}')
        cdp.wait(session, f"Boolean({PDF}.getPageView(0).textLayer?.div?.querySelector('span')) && {PDF}.getPageView(0).renderingState===3")
        print('Checking contextual selection',scale,rotation,flush=True)
        cdp.evaluate(session, SELECT)
        cdp.wait(session, "!document.querySelector('#comment-selection-button').hidden")
        assert cdp.evaluate(session, """(() => {const b=document.querySelector('#comment-selection-button').getBoundingClientRect(); return b.left>=0 && b.right<=innerWidth && b.top>=0 && b.bottom<=innerHeight;})()"""), 'Contextual control outside viewport'
        cdp.evaluate(session, "document.querySelector('#comment-selection-button').click()")
        cdp.wait(session, "!document.querySelector('#selection-comment-composer').hidden")
        cdp.evaluate(session, "document.querySelector('#cancel-selection-comment').click(); document.querySelector('iframe').contentWindow.getSelection().removeAllRanges()")
        cdp.wait(session, "document.querySelector('#comment-selection-button').hidden")
    cdp.evaluate(session, PDF + '.pagesRotation=0;' + PDF + '.currentScale=.75')
    cdp.wait(session, f"Boolean({PDF}.getPageView(0).textLayer?.div?.querySelector('span')) && {PDF}.getPageView(0).renderingState===3")
    cdp.evaluate(session, SELECT)
    cdp.wait(session, "!document.querySelector('#comment-selection-button').hidden")
    cdp.evaluate(session, "document.querySelector('iframe').contentDocument.dispatchEvent(new KeyboardEvent('keydown',{key:'m',ctrlKey:true,altKey:true,bubbles:true}))")
    cdp.wait(session, "!document.querySelector('#selection-comment-composer').hidden")
    screenshot(cdp, session, 'contextual-composer')
    cdp.evaluate(session, "document.querySelector('#selection-comment-body').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    assert cdp.evaluate(session, "document.querySelector('#selection-comment-composer').hidden && document.querySelectorAll('.thread-card').length===0")
    cdp.evaluate(session, "document.querySelector('iframe').contentWindow.getSelection().removeAllRanges()")
    time.sleep(.12)
    cdp.evaluate(session, SELECT)
    cdp.wait(session, "!document.querySelector('#comment-selection-button').hidden")
    cdp.evaluate(session, "document.querySelector('iframe').contentDocument.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
    assert cdp.evaluate(session, "document.querySelector('#comment-selection-button').hidden")
    # App UI selection must never produce a PDF selection control.
    cdp.evaluate(session, "const r=document.createRange();r.selectNodeContents(document.querySelector('.viewer-title'));getSelection().removeAllRanges();getSelection().addRange(r);document.querySelector('iframe').contentWindow.getSelection().removeAllRanges()")
    time.sleep(.15)
    assert cdp.evaluate(session, "document.querySelector('#comment-selection-button').hidden")
    for width, height in [(1440, 900), (1280, 800), (1024, 768), (768, 1024), (390, 844)]:
        viewport(cdp, session, width, height)
        toolbar_fits(cdp, session)
        cdp.evaluate(session, 'getSelection().removeAllRanges()')
        screenshot(cdp, session, f'empty-{width}')
    viewport(cdp, session, 1440, 900)
    assert cdp.evaluate(session, "document.querySelector('.viewer-shell-bar').offsetHeight<50"), 'Desktop toolbar did not shrink after mobile resize'
    assert cdp.evaluate(session, "document.querySelector('iframe').contentWindow.getComputedStyle(document.querySelector('iframe').contentDocument.querySelector('#toolbarViewer')).visibility==='hidden'")
    cdp.evaluate(session, PDF + '.currentScale=1;getSelection().removeAllRanges()')
    menu_search_checks(cdp, session)
    print('PASS unified viewer controls, search, scroll/spread modes, selection/rotation/zoom, cancel, Escape, empty responsive screenshots', flush=True)


def populated_checks(cdp, session, fixture, base):
    cdp.call("Network.setCookie", {"name": "pdf_review_session", "value": fixture['cookies'][0], "url": base, "httpOnly": True, "sameSite": "Lax"}, session)
    cdp.call('Page.navigate', {'url': base + f"/versions/{fixture['versions'][0]}/view"}, session)
    cdp.wait(session, "document.querySelector('#realtime-status')?.textContent==='Live' && document.querySelector('.thread-card')!==null")
    viewport(cdp, session, 1440, 900)
    change(cdp, session, '#review-scale', '0.5')
    cdp.wait(session, "document.querySelector('#thread-list').dataset.layout==='right-rail'")
    cdp.wait(session, f"{PDF}.getPageView(0).renderingState===3 && !{PDF}.getPageView(0).textLayer.div.hidden && {PDF}.getPageView(0).textLayer.div.querySelector('span').getBoundingClientRect().width>0")
    # Seed nearby threads through the real authorized/CSRF API and canonical anchors.
    cdp.evaluate(session, """(async()=>{
      const c=JSON.parse(document.querySelector('#anchor-config').textContent);
      const {createThread}=await import('/static/review/thread_api.js');
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const w=document.querySelector('iframe').contentWindow;
      const d=w.PDFViewerApplication.pdfViewer.getPageView(0).div;
      const r=w.document.createRange();r.selectNodeContents(d.querySelector('.textLayer span').firstChild);
      w.getSelection().removeAllRanges();w.getSelection().addRange(r);
      const anchor=captureTextSelection(w,w.PDFViewerApplication);
      for(let i=0;i<6;i++)await createThread(c.threadsUrl,anchor,'Synthetic nearby review '+i+'. Check wording and document order.');
    })()""")
    cdp.wait(session, "document.querySelectorAll('.thread-card').length>=8")
    # Both pages must share the same right-hand rail in a spread.
    cdp.evaluate(session, PDF + '.currentPageNumber=2')
    cdp.wait(session, f"Boolean({PDF}.getPageView(1).textLayer?.div?.querySelector('span'))")
    cdp.evaluate(session, """(async()=>{
      const w=document.querySelector('iframe').contentWindow;
      const r=w.document.createRange();r.selectNodeContents(w.PDFViewerApplication.pdfViewer.getPageView(1).div.querySelector('.textLayer span').firstChild);
      w.getSelection().removeAllRanges();w.getSelection().addRange(r);
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const c=JSON.parse(document.querySelector('#anchor-config').textContent);
      await createThread(c.threadsUrl,captureTextSelection(w,w.PDFViewerApplication),'Synthetic page two outer rail.');
      w.getSelection().removeAllRanges();
    })()""")
    cdp.wait(session, "document.querySelectorAll('.thread-card').length>=9")
    cdp.evaluate(session, PDF + '.currentPageNumber=1')
    cdp.wait(session, """(() => {const cards=[...document.querySelectorAll('.thread-card')].sort((a,b)=>a.offsetTop-b.offsetTop);return cards.every((c,i)=>i===0 || c.offsetTop>=cards[i-1].offsetTop+cards[i-1].offsetHeight+5);})()""")
    for value in ['minimized', 'hidden', 'expanded']:
        change(cdp, session, '#comments-visibility', value)
        time.sleep(.12)
        if value=='hidden':
            assert cdp.evaluate(session, "document.querySelector('#thread-list').hidden && document.querySelector('iframe').contentDocument.documentElement.style.getPropertyValue('--review-rail-right')==='0px'")
        if value=='minimized':
            assert cdp.evaluate(session, "document.querySelector('.thread-marker:not([hidden])')!==null")
            assert cdp.evaluate(session, "document.querySelector('iframe').contentDocument.documentElement.style.getPropertyValue('--review-rail-right')==='48px'")
            assert cdp.evaluate(session, """(() => {
              const markers=[...document.querySelectorAll('.thread-marker:not([hidden])')].sort((a,b)=>a.offsetTop-b.offsetTop);
              return markers.every((m,i)=>m.offsetWidth<=36&&m.offsetHeight<=32&&(!i||m.offsetTop>=markers[i-1].offsetTop+markers[i-1].offsetHeight+2));
            })()""")
            cdp.evaluate(session, "document.querySelector('.thread-marker:not([hidden])').click()")
            cdp.wait(session, "document.querySelector('.thread-card.active:not([hidden])')!==null")
            assert cdp.evaluate(session, "document.querySelector('#comments-visibility').value==='minimized' && document.querySelector('iframe').contentDocument.documentElement.style.getPropertyValue('--review-rail-right')==='48px'")
            screenshot(cdp, session, 'refine-minimized-active')
            cdp.evaluate(session, "document.querySelector('.thread-card.active .thread-card-header .text-action').click()")
            cdp.wait(session, "!document.querySelector('.thread-card.active')")
            cdp.wait(session, "document.querySelectorAll('.thread-marker:not([hidden])').length===document.querySelectorAll('.thread-card').length")
            screenshot(cdp, session, 'refine-markers-only')
    for width, height in [(1440, 900), (1280, 800), (1024, 768), (768, 1024), (390, 844)]:
        viewport(cdp, session, width, height)
        toolbar_fits(cdp, session)
        cdp.evaluate(session, "document.querySelector('.thread-card').click()")
        cdp.wait(session, """(() => {const c=document.querySelector('.thread-card.active')?.getBoundingClientRect();const p=document.querySelector('.review-panel').getBoundingClientRect();return c && c.top>=p.top && c.top<p.bottom-40;})()""")
        screenshot(cdp, session, f'many-{width}')
        for mode in ['minimized', 'hidden', 'expanded']:
            change(cdp, session, '#comments-visibility', mode)
            time.sleep(.12)
            screenshot(cdp, session, f'refine-{mode}-{width}')
        for spread in [1, 2]:
            change(cdp, session, '#review-spread', spread)
            time.sleep(.15)
            screenshot(cdp, session, f'refine-spread-{spread}-{width}')
        change(cdp, session, '#review-spread', 0)
    viewport(cdp, session, 1900, 1000)
    change(cdp, session, '#review-scale', '0.5')
    change(cdp, session, '#review-spread', 1)
    cdp.wait(session, "document.querySelector('#thread-list').dataset.layout==='right-rail'")
    cdp.wait(session, """(() => {
      const d=document.querySelector('iframe').contentDocument;
      const f=document.querySelector('iframe').getBoundingClientRect();
      return [...document.querySelectorAll('.thread-card')].every(card=>{
        const page=card.getAttribute('aria-label').includes('page 2')?2:1;
        const b=d.querySelector('.page[data-page-number="'+page+'"]').getBoundingClientRect();
        const c=card.getBoundingClientRect();
        const stage=d.querySelector('#viewerContainer').getBoundingClientRect();
        const row=d.querySelector('.page[data-page-number="'+page+'"]').closest('.spread');
        const pages=row?[...row.querySelectorAll('.page,.dummyPage')]:[d.querySelector('.page[data-page-number="'+page+'"]')];
        const edge=Math.max(...pages.map(p=>p.getBoundingClientRect().right));
        return Math.abs(c.left-f.left-edge-6)<2 && c.right<f.left+stage.right-10;
      });
    })()""")
    screenshot(cdp, session, 'spread-right-1900')
    # A wheel gesture over a card scrolls the same native document container.
    point = cdp.evaluate(session, """(() => {
      const c=[...document.querySelectorAll('.thread-card')].map(e=>e.getBoundingClientRect()).find(b=>b.top>60&&b.bottom<innerHeight);
      const s=document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer.container;
      window.beforeCardWheel=s.scrollTop;
      return {x:c.left+c.width/2,y:c.top+20};
    })()""")
    cdp.call('Input.dispatchMouseEvent', {'type':'mouseWheel', 'deltaX':0, 'deltaY':80, **point}, session)
    cdp.wait(session, PDF + '.container.scrollTop>window.beforeCardWheel')
    # Every page's comments stay to the right of its complete spread.
    for scroll in [0, 3]:
        change(cdp, session, '#review-scroll', scroll)
        for spread in [0, 1, 2]:
            change(cdp, session, '#review-spread', spread)
            for mode in ['expanded', 'minimized', 'hidden']:
                change(cdp, session, '#comments-visibility', mode)
                time.sleep(.08)
                assert cdp.evaluate(session, "!document.querySelector('iframe').contentDocument.documentElement.style.getPropertyValue('--review-rail-left')")
                assert cdp.evaluate(session, "!document.querySelector('.review-panel').classList.contains('drawer')")
    change(cdp, session, '#review-scroll', 0)
    change(cdp, session, '#comments-visibility', 'expanded')
    change(cdp, session, '#review-spread', 0)
    viewport(cdp, session, 1440, 900)
    for scale, rotation in [(0.5, 0), (1, 0), (1.5, 0), (2, 0), (1, 90)]:
        cdp.evaluate(session, PDF + f'.currentScale={scale};' + PDF + f'.pagesRotation={rotation}')
        cdp.wait(session, f"{PDF}.getPageView(0).renderingState===3")
        assert cdp.evaluate(session, "!document.querySelector('.review-panel').classList.contains('drawer')")
        screenshot(cdp, session, f'populated-scale-{scale}-rotation-{rotation}')
        if scale == 2:
            cdp.evaluate(session, PDF + '.container.scrollLeft=0')
            time.sleep(.12)
            cdp.evaluate(session, "window.beforeHorizontal=document.querySelector('.thread-card').getBoundingClientRect().left;" + PDF + '.container.scrollLeft=120')
            cdp.wait(session, "Math.abs(document.querySelector('.thread-card').getBoundingClientRect().left-window.beforeHorizontal+120)<2")
            assert cdp.evaluate(session, "document.querySelector('.review-panel').style.clipPath.includes('15px')")
    # Preserve native PDF.js's transparent page border and row/spread spacing.
    for scale in [.5, 1, 1.5, 2]:
        cdp.evaluate(session, PDF + f'.pagesRotation=0;' + PDF + f'.currentScale={scale}')
        for scroll in [0, 3]:
            change(cdp, session, '#review-scroll', scroll)
            for spread in [0, 1, 2]:
                change(cdp, session, '#review-spread', spread)
                assert cdp.evaluate(session, """(() => {
                  const w=document.querySelector('iframe').contentWindow;
                  const p=w.document.querySelector('.page'); const s=w.getComputedStyle(p);
                  return s.marginBottom==='-8px' && s.borderTopWidth==='9px' && s.borderTopColor==='rgba(0, 0, 0, 0)' && (!p.closest('.spread') || s.marginLeft==='-3.5px');
                })()""")
    print('PASS collision-free nearby threads, visibility modes, active navigation, responsive/spread screenshots and right-only rails', flush=True)


def single_thread_checks(cdp, session):
    assert cdp.evaluate(session, "document.querySelectorAll('.thread-card').length===1")
    original = cdp.evaluate(session, f"[innerWidth,innerHeight,{PDF}.currentScale]")
    change(cdp, session, '#review-scale', '0.5')
    cdp.evaluate(session, "document.querySelector('.thread-card').click()")
    for width, height in [(1440, 900), (1280, 800), (1024, 768), (768, 1024), (390, 844)]:
        viewport(cdp, session, width, height)
        toolbar_fits(cdp, session)
        screenshot(cdp, session, f'one-{width}')
    viewport(cdp, session, original[0], original[1])
    cdp.evaluate(session, PDF + f'.currentScale={original[2]}')
    cdp.wait(session, PDF + '.getPageView(0).renderingState===3')


def shared_page_checks(cdp, a, b, fixture, base):
    surfaces = [('dashboard', '/', 'Documents'),
                ('document', f"/documents/{fixture['document_id']}", 'Browser sanity'),
                ('import', f"/documents/{fixture['owned']}", 'C1 owner fixture'),
                ('account', '/account', 'Owned by me'),
                ('access', f"/documents/{fixture['owned']}/access", 'Manage access'),
                ('history', f"/documents/{fixture['document_id']}/migrations", 'Carry feedback')]
    for width, height in [(1440, 900), (1280, 800), (1024, 768), (768, 1024), (390, 844)]:
        viewport(cdp, b, width, height)
        for name, path, text in surfaces:
            cdp.evaluate(b, 'window.viewerQaLeaving=true')
            cdp.call('Page.navigate', {'url': base + path}, b)
            cdp.wait(b, f"!window.viewerQaLeaving && document.readyState==='complete' && document.body.innerText.includes({json.dumps(text)})")
            assert cdp.evaluate(b, "document.documentElement.scrollWidth<=innerWidth && document.querySelector('.app-toolbar .identity-menu')!==null"), (name,width)
            if name == 'document':
                assert cdp.evaluate(b, """[...document.querySelectorAll('.version-card')].every(card=>{
                  const a=card.querySelector('.version-actions > a').getBoundingClientRect(), c=card.getBoundingClientRect();
                  return Math.abs(c.right-a.right-13)<2 && Math.abs(a.top-c.top-13)<2;
                })""")
            if name == 'import':
                assert cdp.evaluate(b, "getComputedStyle(document.querySelector('input[type=file]'),'::file-selector-button').borderRightWidth==='1px'")
            screenshot(cdp, b, f'refine-page-{name}-{width}')
        cdp.call('Network.setCookie', {'name':'pdf_review_session','value':fixture['admin_cookie'],'url':base,'httpOnly':True,'sameSite':'Lax'}, a)
        viewport(cdp, a, width, height)
        cdp.evaluate(a, 'window.viewerQaLeaving=true')
        cdp.call('Page.navigate', {'url':base+'/admin'}, a)
        cdp.wait(a, "!window.viewerQaLeaving && document.readyState==='complete' && document.body.innerText.includes('Private beta administration')")
        cdp.evaluate(a, 'scrollTo(0,0)')
        screenshot(cdp, a, f'refine-page-admin-{width}')
        assert cdp.evaluate(a, 'document.documentElement.scrollWidth<=innerWidth'), cdp.evaluate(a, "[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,10).map(e=>[e.tagName,e.className,e.getBoundingClientRect().width])")
        if width in [1440, 390]:
            click(cdp, a, '.admin-entry-actions > .toolbar-menu > summary')
            cdp.wait(a, "document.querySelector('.admin-entry-actions > .toolbar-menu').open")
            click(cdp, a, '.admin-entry-actions .submenu > summary')
            cdp.wait(a, "document.querySelector('.admin-entry-actions .submenu').open")
            menu_bounds(cdp, a)
            screenshot(cdp, a, f'refine-admin-confirmation-{width}')
            cdp.evaluate(a, "document.querySelector('.admin-entry-actions .submenu button[value=remove]').click()")
            assert cdp.evaluate(a, "document.querySelector('.admin-entry-actions .submenu').open && !document.querySelector('.admin-entry-actions .submenu form').checkValidity()")
            key(cdp, a, 'Escape', 27)
            key(cdp, a, 'Escape', 27)
    cdp.call('Network.deleteCookies', {'name':'pdf_review_session','url':base}, a)
    cdp.call('Page.navigate', {'url':base+'/auth/login'}, a)
    cdp.wait(a, "document.body.innerText.includes('Sign in to PDF Review')")
    screenshot(cdp, a, 'refine-page-login-390')
    print('PASS shared shell and compact dashboard/document/account/access/admin/history screenshots at five viewport sizes', flush=True)


def comment_interaction_checks(cdp, session):
    viewport(cdp, session, 1440, 900)
    change(cdp, session, '#comments-visibility', 'expanded')
    change(cdp, session, '#review-scroll', 0)
    change(cdp, session, '#review-spread', 0)
    change(cdp, session, '#review-scale', '0.5')
    cdp.evaluate(session, PDF + '.currentPageNumber=1;' + PDF + '.container.scrollTop=0;' + PDF + '.container.scrollLeft=0')
    cdp.wait(session, f"{PDF}.getPageView(0).renderingState===3")
    time.sleep(.2)
    snapshot = """(() => {const p=document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer;const b=p.getPageView(0).div.getBoundingClientRect();return [p.container.scrollTop,p.container.scrollLeft,b.top,b.left,b.width];})()"""
    before = cdp.evaluate(session, snapshot)
    cdp.evaluate(session, """(() => {
      const card=[...document.querySelectorAll('.thread-card')].find(c=>c.textContent.includes('Synthetic nearby review 5'));
      window.focusTestThread=card.dataset.threadId;
      const d=document.querySelector('iframe').contentDocument;
      [...d.querySelectorAll('.pdf-review-thread-highlight')].find(h=>h.dataset.threadId===window.focusTestThread).click();
    })()""")
    cdp.wait(session, "document.querySelector('.thread-card.active')?.dataset.threadId===window.focusTestThread")
    cdp.wait(session, """(() => {
      const c=document.querySelector('.thread-card.active').getBoundingClientRect();
      const f=document.querySelector('iframe').getBoundingClientRect();
      const h=[...document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight')].find(h=>h.dataset.threadId===window.focusTestThread).getBoundingClientRect();
      return Math.abs((c.top+c.bottom)/2-f.top-(h.top+h.bottom)/2)<3;
    })()""")
    assert cdp.evaluate(session, snapshot) == before, 'Opening dense comment moved PDF'
    assert cdp.evaluate(session, "getComputedStyle(document.querySelector('.thread-card.active')).boxShadow!=='none' && getComputedStyle(document.querySelector('.thread-card:not(.active)')).backgroundColor==='rgb(233, 236, 234)'")
    screenshot(cdp, session, 'refine-dense-selected-stationary')
    for target in ['document.body', "document.querySelector('iframe').contentDocument.body"]:
        cdp.evaluate(session, target + ".dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
        cdp.wait(session, "!document.querySelector('.thread-card.active')")
    # Enter and the alternate shortcut both open a selection composer; typing in
    # that composer keeps normal Enter/newline behavior.
    for event in ["{key:'Enter',bubbles:true}", "{key:'m',ctrlKey:true,altKey:true,bubbles:true}"]:
        cdp.evaluate(session, SELECT)
        cdp.wait(session, "!document.querySelector('#comment-selection-button').hidden")
        before = cdp.evaluate(session, snapshot)
        cdp.evaluate(session, "document.querySelector('iframe').contentDocument.dispatchEvent(new KeyboardEvent('keydown'," + event + "))")
        cdp.wait(session, "!document.querySelector('#selection-comment-composer').hidden")
        assert cdp.evaluate(session, snapshot) == before, 'Opening composer moved PDF'
        cdp.evaluate(session, "document.querySelector('#selection-comment-body').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
        assert cdp.evaluate(session, "!document.querySelector('#selection-comment-composer').hidden")
        key(cdp, session, 'Escape', 27)
        cdp.wait(session, "document.querySelector('#selection-comment-composer').hidden")
    cdp.evaluate(session, SELECT)
    cdp.wait(session, "!document.querySelector('#comment-selection-button').hidden")
    before = cdp.evaluate(session, snapshot)
    count = cdp.evaluate(session, "document.querySelectorAll('.thread-card').length")
    cdp.evaluate(session, "document.querySelector('iframe').contentDocument.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));document.querySelector('#selection-comment-body').value='Stationary dense insertion';document.querySelector('#selection-comment-form').requestSubmit()")
    cdp.wait(session, f"document.querySelectorAll('.thread-card').length==={count+1} && document.querySelector('#selection-comment-composer').hidden")
    time.sleep(.2)
    assert cdp.evaluate(session, snapshot) == before, 'Inserting dense comment moved PDF'
    change(cdp, session, '#comments-visibility', 'minimized')
    cdp.evaluate(session, "document.querySelector('.thread-marker').click()")
    cdp.wait(session, """(() => {const c=document.querySelector('.thread-card.active'); const m=[...document.querySelectorAll('.thread-marker')].find(m=>m.dataset.threadId===c?.dataset.threadId);return c&&!c.hidden&&!m.hidden&&c.getBoundingClientRect().left>=m.getBoundingClientRect().right+5;})()""")
    screenshot(cdp, session, 'refine-minimized-expand-right')
    viewport(cdp, session, 390, 844)
    cdp.wait(session, "document.querySelector('#comments-visibility').value==='mobile'")
    cdp.evaluate(session, PDF + '.container.scrollLeft=0;' + PDF + '.container.scrollTop=0')
    before = cdp.evaluate(session, snapshot)
    cdp.evaluate(session, """(() => {const d=document.querySelector('iframe').contentDocument;[...d.querySelectorAll('.pdf-review-thread-highlight')].find(h=>h.dataset.threadId===window.focusTestThread).click();})()""")
    cdp.wait(session, """(() => {const c=document.querySelector('.thread-card.active')?.getBoundingClientRect();const f=document.querySelector('iframe').getBoundingClientRect();const h=[...document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight')].find(h=>h.dataset.threadId===window.focusTestThread).getBoundingClientRect();return c&&c.left>=8&&c.right<=innerWidth-8&&Math.abs(c.top-f.top-h.bottom-8)<3;})()""")
    assert cdp.evaluate(session, snapshot) == before, 'Mobile popup moved PDF'
    screenshot(cdp, session, 'refine-mobile-highlight-popup')
    key(cdp, session, 'Escape', 27)
    cdp.wait(session, "!document.querySelector('.thread-card.active') && [...document.querySelectorAll('.thread-card')].every(c=>c.hidden)")
    viewport(cdp, session, 1440, 900)
    cdp.wait(session, "document.querySelector('#comments-visibility').value==='minimized'")
    print('PASS stationary dense selection/insertion, Enter/alternate shortcut, Escape, selected styling, right expansion and automatic Mobile popup', flush=True)


def comment_ui_checks(cdp, session):
    """Focused checks for comment animation, mobile anchoring and the header."""
    viewport(cdp, session, 390, 844)
    change(cdp, session, '#review-scale', '1')
    cdp.wait(session, f"{PDF}.getPageView(0).renderingState===3 && !{PDF}.getPageView(0).textLayer.div.hidden")
    cdp.evaluate(session, SELECT)
    cdp.wait(session, "!document.querySelector('#comment-selection-button').hidden")
    cdp.evaluate(session, "document.querySelector('iframe').contentDocument.body.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));document.querySelector('#selection-comment-body').value='Mobile popup visual fixture';document.querySelector('#selection-comment-form').requestSubmit()")
    cdp.wait(session, "document.querySelector('.thread-card.active')!==null && document.querySelector('#selection-comment-composer').hidden")
    viewport(cdp, session, 1440, 900)
    change(cdp, session, '#comments-visibility', 'expanded')
    cdp.evaluate(session, SELECT)
    cdp.evaluate(session, """(async()=>{
      const c=JSON.parse(document.querySelector('#anchor-config').textContent);
      const w=document.querySelector('iframe').contentWindow;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const anchor=captureTextSelection(w,w.PDFViewerApplication);
      for(let i=0;i<3;i++) await createThread(c.threadsUrl,anchor,'Sliding neighbor '+i);
      w.getSelection().removeAllRanges();
    })()""")
    cdp.wait(session, "document.querySelectorAll('.thread-card').length===4")
    time.sleep(.2)
    assert cdp.evaluate(session, """(async()=>{
      const pdf=document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer;
      const before=pdf.container.scrollTop;
      const target=[...document.querySelectorAll('.thread-card')].find(c=>c.textContent.includes('Sliding neighbor 2'));
      [...document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight')].find(h=>h.dataset.threadId===target.dataset.threadId).click();
      await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
      return [...document.querySelectorAll('.thread-card:not(.active)')].some(c=>c.getAnimations().some(a=>a.playState==='running')) && pdf.container.scrollTop===before;
    })()"""), 'Neighboring comments should animate without scrolling the PDF'
    time.sleep(.2)
    viewport(cdp, session, 390, 844)
    cdp.wait(session, "document.querySelector('#comments-visibility').value==='mobile'")
    assert cdp.evaluate(session, "document.querySelector('.thread-card.active').offsetWidth===280")
    screenshot(cdp, session, 'refine-mobile-narrow-comment')
    for offset in [0, 200, 500]:
        cdp.evaluate(session, PDF + f'.container.scrollTop={offset}')
        cdp.wait(session, """(() => {
          const f=document.querySelector('iframe').getBoundingClientRect();
          const h=document.querySelector('iframe').contentDocument.querySelector('.pdf-review-thread-highlight').getBoundingClientRect();
          const c=document.querySelector('.thread-card.active').getBoundingClientRect();
          return Math.abs(c.top-f.top-h.bottom-8)<2;
        })()""")
    cdp.wait(session, "document.querySelector('.thread-card.active').getBoundingClientRect().top<document.querySelector('iframe').getBoundingClientRect().top")
    screenshot(cdp, session, 'refine-mobile-comment-scrolls-offscreen')
    for width in [280, 320, 390, 480, 700]:
        viewport(cdp, session, width, 844)
        assert cdp.evaluate(session, """(() => {
          const nodes=[document.querySelector('.viewer-shell-bar > a'),document.querySelector('.viewer-title'),document.querySelector('#review-view-menu'),document.querySelector('#comments-menu'),document.querySelector('.collaboration-menu'),document.querySelector('.viewer-shell-bar .identity-menu')];
          const boxes=nodes.map(n=>n.getBoundingClientRect());
          const center=boxes[0].top+boxes[0].height/2;
          return boxes.every(b=>Math.abs(b.top+b.height/2-center)<2&&b.left>=0&&b.right<=innerWidth) && document.querySelector('.document-controls').getBoundingClientRect().top>=Math.max(...boxes.map(b=>b.bottom));
        })()"""), f'Header wrapped at {width}px'
        screenshot(cdp, session, f'refine-mobile-single-header-{width}')
    cdp.call('Emulation.setEmulatedMedia', {'features':[{'name':'prefers-reduced-motion','value':'reduce'}]}, session)
    assert cdp.evaluate(session, "getComputedStyle(document.querySelector('.thread-card.active')).animationName==='none'")
    cdp.call('Emulation.setEmulatedMedia', {'features':[]}, session)
    print('PASS fast comment rearrangement/reduced motion, narrower mobile popup, exact highlight anchoring offscreen and single header row at 280/320/390/480/700px', flush=True)
