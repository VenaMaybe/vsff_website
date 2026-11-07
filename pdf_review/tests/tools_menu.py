"""Focused Tools menu checks using disposable viewer fixtures."""
import json
from tests.viewer_acceptance import viewport, click, key, screenshot
from tests.beta_c2_acceptance import navigate


def run_tools(cdp, a, b, fixture, base):
    def ev(script): return cdp.evaluate(a, script)
    def wait(script): return cdp.wait(a, script)
    viewport(cdp, a, 1440, 1000)
    # Exercise the real shortcut before Search has ever opened. Immediate pinning
    # must not replace the entrance with travel from its provisional center.
    entrances=ev("""(async()=>{
      const original=Element.prototype.animate;let trace=[];const result=[];
      Element.prototype.animate=function(frames,options){
        if(this.matches('.search-panel'))trace.push({frames,options});
        return original.call(this,frames,options);
      };
      const pause=()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
      try {
        for(let i=0;i<2;i++){
          trace=[];
          document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'f',ctrlKey:true,bubbles:true,cancelable:true}));
          await pause();
          const card=document.querySelector('.search-panel');
          result.push({trace:[...trace],pinned:card.dataset.pinned});
          card.querySelector('.dialog-header button:last-child').click();
        }
      }finally{Element.prototype.animate=original;}
      return result;
    })()""")
    assert entrances[0]==entrances[1] and entrances[0]['pinned']=='true',entrances
    assert entrances[0]['trace']==[dict(frames=[dict(translate='0 4px',opacity=0),dict(translate='0 0',opacity=1)],options=dict(duration=160,easing='ease-out'))],entrances
    # Leave ordinary menu launches at their usual unpinned state.
    ev("document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'f',ctrlKey:true,bubbles:true,cancelable:true}));document.querySelector('.search-panel .left-card-pin').click();document.querySelector('.search-panel .dialog-header button:last-child').click()")
    assert ev("!document.querySelector('#review-view-menu [data-pdf-control=cursorSelectTool],#review-view-menu [data-pdf-control=cursorHandTool]')")
    click(cdp,a,'#review-tools-menu > summary')
    click(cdp,a,'.tools-icon-grid [data-pdf-control=cursorHandTool]')
    wait("document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfCursorTools.activeTool===1&&document.querySelector('[data-pdf-control=cursorHandTool]').getAttribute('aria-pressed')==='true'")
    ev("document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfCursorTools.switchTool(0)")
    wait("document.querySelector('[data-pdf-control=cursorSelectTool]').getAttribute('aria-pressed')==='true'&&document.querySelector('[data-pdf-control=cursorHandTool]').getAttribute('aria-pressed')==='false'")
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
    # The Tools card reuses the same control markup and delegated actions.
    ev("window.originalToolsContent=document.querySelector('#review-tools-menu > .toolbar-popover')")
    point=ev("(()=>{const r=document.querySelector('#review-tools-menu > summary').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()")
    for count in [1,2]:
        for kind in ['mousePressed','mouseReleased']:
            cdp.call('Input.dispatchMouseEvent',{'type':kind,'button':'left','clickCount':count,**point},a)
    wait("document.querySelectorAll('.tools-panel').length===1&&!document.querySelector('#review-tools-menu').open")
    assert ev("document.querySelector('#review-tools-menu > .toolbar-popover')===originalToolsContent&&document.querySelectorAll('.tools-panel .tools-icon-grid').length===1")
    ev("document.querySelector('.tools-panel .left-card-pin').click()")
    assert ev("document.querySelector('.tools-panel').dataset.pinned==='true'")
    ev("document.querySelector('.tools-panel .dialog-header button:last-child').click()")
    wait("!document.querySelector('.tools-panel')&&document.querySelector('#review-tools-menu > .toolbar-popover')===originalToolsContent")
    # The shortcut works from document focus and a keyboard-focused dropdown row,
    # not just the Tools summary. Repeated openings reuse the same card.
    ev("document.querySelector('iframe').contentWindow.focus();document.querySelector('iframe').contentDocument.body.focus()")
    key(cdp,a,'Enter',13,8)
    wait("document.querySelector('.tools-panel')!==null")
    ev("document.querySelector('.tools-panel .dialog-header button:last-child').click();document.querySelector('#review-tools-menu').open=true;document.querySelector('#review-tools-menu [data-left-card=filters]').focus()")
    key(cdp,a,'Enter',13,8)
    wait("document.querySelector('.tools-panel')!==null&&!document.querySelector('#review-tools-menu').open")
    assert ev("document.querySelectorAll('.tools-panel').length===1&&!document.querySelector('.comment-filter-panel')")
    ev("document.querySelector('.tools-panel .dialog-header button:last-child').click()")
    ev("document.querySelector('#review-tools-menu > summary').focus()")
    key(cdp,a,'Enter',13,8)
    wait("document.querySelector('.tools-panel')!==null")
    ev("document.querySelector('.tools-panel [data-pdf-control=cursorHandTool]').click()")
    wait("document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfCursorTools.activeTool===1")
    # Tools launches keep both keyboard focus and packing priority in Tools,
    # including Search's native autofocus and Settings' delayed form loading.
    for tool, panel in [('search','.search-panel'), ('filters','.comment-filter-panel'),
                        ('reading','.reading-spine-card'), ('analytics','.reader-analytics-card'),
                        ('properties','.page-properties-card'), ('settings','.settings-panel'),
                        ('sections','.sections-panel')]:
        selector=f'.tools-panel [data-left-card={tool}]'
        ev(f"document.querySelector({json.dumps(selector)}).focus();document.querySelector({json.dumps(selector)}).click()")
        wait(f"document.querySelector({json.dumps(panel)})!==null")
        if tool=='settings':
            wait("document.querySelector('.settings-panel form select')!==null")
        assert ev(f"document.querySelector({json.dumps(selector)})===document.activeElement&&document.querySelector('.tools-panel').classList.contains('active')&&!document.querySelector({json.dumps(panel)}).classList.contains('active')"), (tool, ev("({focus:document.activeElement.outerHTML,active:[...document.querySelectorAll('.left-card.active')].map(e=>e.className)})"))
        # Selecting an already-open tool closes it and leaves Tools focused.
        ev(f"document.querySelector({json.dumps(selector)}).click()")
        wait(f"document.querySelector({json.dumps(panel)})===null")
        assert ev(f"document.querySelector({json.dumps(selector)}).getAttribute('aria-checked')==='false'&&document.querySelector({json.dumps(selector)})===document.activeElement&&document.querySelector('.tools-panel').classList.contains('active')")
        ev(f"document.querySelector({json.dumps(selector)}).click()")
        wait(f"document.querySelector({json.dumps(panel)})!==null&&document.querySelector({json.dumps(selector)}).getAttribute('aria-checked')==='true'")
    # Header Tools remains independently usable while the Tools card stays open.
    click(cdp,a,'#review-tools-menu > summary')
    wait("document.querySelector('#review-tools-menu').open&&document.querySelector('.tools-panel')!==null")
    click(cdp,a,'#review-tools-menu [data-pdf-control=cursorSelectTool]')
    wait("document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfCursorTools.activeTool===0")
    assert ev("[...document.querySelectorAll('[data-pdf-control=cursorSelectTool]')].every(x=>x.getAttribute('aria-pressed')==='true')")
    click(cdp,a,'#review-tools-menu [data-left-card=search]')
    wait("document.querySelector('.search-panel')?.contains(document.activeElement)")
    assert ev("document.querySelector('#review-tools-menu').open&&document.querySelector('.tools-panel')!==null&&[...document.querySelectorAll('[data-left-card=search]')].every(x=>x.getAttribute('aria-checked')==='true')")
    # Card action closes the same Search instance opened/focused by the header.
    ev("document.querySelector('.tools-panel [data-left-card=search]').focus();document.querySelector('.tools-panel [data-left-card=search]').click()")
    wait("!document.querySelector('.search-panel')")
    assert ev("[...document.querySelectorAll('[data-left-card=search]')].every(x=>x.getAttribute('aria-checked')==='false')")
    ev("document.querySelector('.tools-panel [data-close-all-tools]').click()")
    wait("document.querySelectorAll('.left-card').length===0&&document.querySelector('#review-tools-menu > .toolbar-popover')!==null")
    ev("document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfCursorTools.switchTool(0)")
    # Existing keyboard menu navigation and mobile popup positioning are reused.
    # Ctrl/Cmd+F pins the one Search card from either document context.
    for context,modifier in [('document','ctrlKey'),("document.querySelector('iframe').contentDocument",'metaKey')]:
        ev(context+".body.dispatchEvent(new KeyboardEvent('keydown',{key:'f',"+modifier+":true,bubbles:true,cancelable:true}))")
        wait("document.querySelector('.search-panel')?.dataset.pinned==='true'")
        assert ev("document.querySelectorAll('.search-panel').length===1&&document.querySelector('.search-panel').contains(document.activeElement)")
        ev("document.querySelector('.search-panel .left-card-pin').click()")
        assert ev("document.querySelector('.search-panel').dataset.pinned==='false'")
    ev("document.querySelector('.search-panel .dialog-header button:last-child').click()")
    viewport(cdp, a, 390, 844)
    ev("document.querySelector('#review-tools-menu > summary').focus()")
    key(cdp, a, 'ArrowDown', 40)
    wait("document.activeElement===document.querySelector('.tools-icon-grid [data-pdf-control=viewsManagerToggleButton]')")
    key(cdp,a,'ArrowRight',39)
    assert ev("document.activeElement===document.querySelector('.tools-icon-grid [data-left-card=search]')")
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
