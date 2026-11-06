"""Same-line browser fragments paint once without changing immutable anchors."""
import time
import json
from tests.viewer_acceptance import PDF, SELECT, viewport, screenshot


def run_highlight_overlap(cdp,a,fixture):
    def ev(script):return cdp.evaluate(a,script)
    def wait(script):return cdp.wait(a,script)
    checks=ev("""(async()=>{
      const {visibleHighlightRectangles:visible}=await import('/static/review/anchor_geometry.js');
      // Actual problematic geometry, stripped of all comment/identity data.
      const adjacent=[[54.45,223.459991,81.610007,234.979999],[81.610016,223.459991,140.340015,234.979999]];
      const overlapping=[[105.67002,487.409995,108.22002,498.929993],
        [107.609985,486.809995,159.359985,499.529993],
        [108.22002,487.409995,158.740018,498.929993],
        [158.749988,487.409995,161.299988,498.929993]];
      const before=JSON.stringify([adjacent,overlapping]);
      const rotate=r=>[r[1],r[0],r[3],r[2]];
      return {
        adjacent:visible(adjacent),overlapping:visible(overlapping),
        vertical:visible(overlapping.map(rotate),90),
        gap:visible([[0,0,30,12],[35,0,60,12]]).length,
        lines:visible([[0,0,30,12],[0,12.2,30,24.2]]).length,
        shortLines:visible([[0,0,5,12],[0,12.2,5,24.2]]).length,
        superscript:visible([[0,0,30,12],[30,6,36,14]]).length,
        chain:visible([[0,0,30,12],[30,0,60,12],[60,0,90,12]]).length,
        unchanged:before===JSON.stringify([adjacent,overlapping])};
    })()""")
    assert len(checks['adjacent'])==len(checks['overlapping'])==len(checks['vertical'])==1,checks
    assert checks['adjacent'][0]==[54.45,223.459991,140.340015,234.979999],checks
    assert checks['overlapping'][0]==[105.67002,486.809995,161.299988,499.529993],checks
    assert all(checks[k]==2 for k in ['gap','lines','shortLines','superscript']),checks
    assert checks['chain']==1 and checks['unchanged'],checks
    viewport(cdp,a,1440,900)
    ev(PDF+'.currentScale=1')
    wait(PDF+'.getPageView(0).textLayer?.div?.querySelector("span")!=null')
    capture=ev("""(async()=>{
      const w=document.querySelector('iframe').contentWindow,d=w.document;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {visibleHighlightRectangles}=await import('/static/review/anchor_geometry.js');
      const layer=w.PDFViewerApplication.pdfViewer.getPageView(0).textLayer.div;
      const holder=d.createElement('div');
      holder.style.cssText='position:absolute;left:50px;top:50px;font:16px Arial;white-space:nowrap';
      for(const text of ['Adjacent ','text runs']){
        const span=d.createElement('span');span.textContent=text;
        span.style.cssText='position:static;font:inherit;transform:none';holder.append(span);
      }
      layer.append(holder);
      try {
        const range=d.createRange();range.setStart(holder.firstChild.firstChild,0);
        range.setEnd(holder.lastChild.firstChild,holder.lastChild.textContent.length);
        const selection=w.getSelection();selection.removeAllRanges();selection.addRange(range);
        const anchor=captureTextSelection(w,w.PDFViewerApplication),rectangles=anchor.segments[0].rectangles;
        return {raw:rectangles.length,painted:visibleHighlightRectangles(rectangles).length,
          text:anchor.selection_text};
      } finally {w.getSelection().removeAllRanges();holder.remove();}
    })()""")
    assert capture['raw']>=2 and capture['painted']==1 and capture['text']=='Adjacent text runs',capture
    ev(SELECT)
    saved=ev("""(async()=>{const w=document.querySelector('iframe').contentWindow;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const c=JSON.parse(document.querySelector('#anchor-config').textContent),anchor=captureTextSelection(w,w.PDFViewerApplication);
      const r=anchor.segments[0].rectangles[0];
      const inner=[r[0],r[1]+.625,r[2],r[3]-.625],separate=[r[0],r[1]-30,r[2]/2,r[3]-30];
      const middle=(r[0]+r[2])/2;
      anchor.segments[0].rectangles=[inner,
        [r[0],r[1]-.6,middle,r[3]+.6],
        [middle+.000009,r[1],r[2],r[3]],
        [...inner],separate];
      await createThread(c.threadsUrl,anchor,'Nested range rectangle regression');
      w.getSelection().removeAllRanges();return anchor.segments[0].rectangles;
    })()""")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight').length===2")
    # Historical geometry remains unchanged, including the duplicate and inner box.
    canonical=ev("fetch(JSON.parse(document.querySelector('#anchor-config').textContent).threadsUrl).then(r=>r.json()).then(d=>d.threads[0].targets[0].anchor)")
    assert canonical['segments'][0]['rectangles']==saved
    anchor_id=canonical['anchor_id']
    for scale in [.5,1,1.5,2]:
        ev(PDF+f'.currentScale={scale}')
        for rotation in [0,90]:
            ev(PDF+f'.pagesRotation={rotation}')
            time.sleep(.2)
            assert ev("document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight').length===2")
    ev(PDF+'.pagesRotation=0;'+PDF+'.currentScale=1')
    ev("document.querySelector('iframe').contentDocument.querySelector('.pdf-review-thread-highlight').click()")
    wait("document.querySelector('.thread-card.active')!==null")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight.is-active').length===2")
    ev("document.querySelector('iframe').contentDocument.querySelector('.pdf-review-thread-highlight').scrollIntoView({block:'center'})")
    time.sleep(.2)
    screenshot(cdp,a,'highlight-contained-rectangle')
    # Separate comments on the same text must remain separate clickable anchors.
    ev(SELECT)
    ev("""(async()=>{const w=document.querySelector('iframe').contentWindow;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const c=JSON.parse(document.querySelector('#anchor-config').textContent);
      await createThread(c.threadsUrl,captureTextSelection(w,w.PDFViewerApplication),'Separate overlapping conversation');w.getSelection().removeAllRanges();})()""")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight').length===3")
    ids=ev("[...new Set([...document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight')].map(e=>e.dataset.anchorId))]")
    assert len(ids)==2 and anchor_id in ids,ids
    # Add a third conversation covering only the left half, then use genuine
    # pointer input to exercise hit testing through overlapping DOM elements.
    ev(SELECT)
    ev("""(async()=>{const w=document.querySelector('iframe').contentWindow;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const c=JSON.parse(document.querySelector('#anchor-config').textContent),anchor=captureTextSelection(w,w.PDFViewerApplication);
      const r=anchor.segments[0].rectangles[0];r[2]=(r[0]+r[2])/2;
      await createThread(c.threadsUrl,anchor,'Third partial overlap');w.getSelection().removeAllRanges();})()""")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight').length===4")
    ev("document.querySelector('.viewer-title').click()")
    wait("document.querySelector('.thread-card.active')===null")
    def point(fraction=.25,disjoint=False):
        selector='.pdf-review-thread-highlight[data-anchor-id="'+anchor_id+'"]'
        ev("document.querySelector('iframe').contentDocument.querySelectorAll("+json.dumps(selector)+")["+('1' if disjoint else '0')+"].scrollIntoView({block:'center'})")
        time.sleep(.2)
        return ev("""(()=>{const f=document.querySelector('iframe'),d=f.contentDocument,
          r=d.querySelectorAll(SELECTOR)[INDEX].getBoundingClientRect(),b=f.getBoundingClientRect(),
          rotated=f.contentWindow.PDFViewerApplication.pdfViewer.pagesRotation%180!==0,
          x=r.left+r.width*(rotated ? .5 : FRACTION),y=r.top+r.height*(rotated ? FRACTION : .5);
          const hits=[...d.querySelectorAll('.pdf-review-thread-highlight')].reverse().filter(e=>{
            const r=e.getBoundingClientRect();return !e.hidden&&x>=r.left&&x<=r.right&&y>=r.top&&y<=r.bottom;});
          return {x:x+b.left,y:y+b.top,ids:[...new Set(hits.map(e=>e.dataset.threadId))],
            passThrough:!d.elementFromPoint(x,y)?.closest('.pdf-review-anchor-overlay')};})()""".replace('SELECTOR',json.dumps(selector)).replace('INDEX','1' if disjoint else '0').replace('FRACTION',str(fraction)))
    def click(p,expected):
        for kind in ['mousePressed','mouseReleased']:
            cdp.call('Input.dispatchMouseEvent',dict(type=kind,x=p['x'],y=p['y'],button='left',clickCount=1),a)
        wait("document.querySelector('.thread-card.active')?.dataset.threadId==="+json.dumps(expected))
        wait("[...document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight.is-active')].some(e=>e.dataset.threadId==="+json.dumps(expected)+")")
    p=point()
    assert len(p['ids'])==3 and p['passThrough'],p
    cdp.call('Input.dispatchMouseEvent',dict(type='mouseMoved',x=p['x'],y=p['y']),a)
    wait("document.querySelector('iframe').contentDocument.querySelector('.pdf-review-thread-highlight.is-hovered')!==null")
    wait("(()=>{const w=document.querySelector('iframe').contentWindow;return w.getComputedStyle(w.document.querySelector('.review-highlight-cursor')).cursor==='pointer';})()")
    # Cursor feedback belongs to the text hit target; highlights stay transparent
    # to pointer input so the later native-drag assertions still exercise it.
    assert ev("(()=>{const w=document.querySelector('iframe').contentWindow;return w.getComputedStyle(w.document.querySelector('.pdf-review-thread-highlight')).pointerEvents==='none';})()")
    cdp.call('Input.dispatchMouseEvent',dict(type='mouseMoved',x=20,y=80),a)
    wait("document.querySelector('iframe').contentDocument.querySelector('.review-highlight-cursor')===null")
    cursor_timing=ev("""(async()=>{
      const f=document.querySelector('iframe'),w=f.contentWindow,d=w.document,b=f.getBoundingClientRect();
      const x=POINT.x-b.left,y=POINT.y-b.top,target=d.elementFromPoint(x,y);
      const send=type=>target.dispatchEvent(new w.PointerEvent(type,{
        bubbles:true,pointerId:91,isPrimary:true,pointerType:'mouse',button:0,
        buttons:type==='pointerdown'?1:0,clientX:x,clientY:y}));
      const hand=()=>w.getComputedStyle(target).cursor==='pointer';
      send('pointerdown');const down=hand();
      await new Promise(r=>setTimeout(r,20));send('pointerup');const up=hand();
      await new Promise(r=>setTimeout(r,230));const quickClick=hand();
      send('pointerdown');await new Promise(r=>setTimeout(r,230));const hold=hand();
      send('pointerup');return {down,up,quickClick,hold};
    })()""".replace('POINT',json.dumps(p)))
    assert cursor_timing==dict(down=True,up=True,quickClick=True,hold=False),cursor_timing
    for index in range(4):click(p,p['ids'][index%3])
    assert ev("(()=>{const w=document.querySelector('iframe').contentWindow,node=w.document.querySelector('.review-highlight-cursor');return !!node&&w.getComputedStyle(node).cursor==='pointer';})()")
    # Clicking another part of the line cycles only through coverage there.
    p=point(.75)
    assert len(p['ids'])==2,p
    current=ev("document.querySelector('.thread-card.active').dataset.threadId")
    offset=p['ids'].index(current) if current in p['ids'] else -1
    for index in range(1,4):click(p,p['ids'][(offset+index)%2])
    p=point(disjoint=True)
    assert len(p['ids'])==1,p
    click(p,p['ids'][0]);click(p,p['ids'][0])
    for scale,rotation in [(1.5,0),(1,90)]:
        ev(PDF+f'.currentScale={scale};'+PDF+f'.pagesRotation={rotation}')
        time.sleep(.3)
        p=point()
        assert len(p['ids'])==3,p
        current=ev("document.querySelector('.thread-card.active').dataset.threadId")
        offset=p['ids'].index(current) if current in p['ids'] else -1
        for index in range(1,4):click(p,p['ids'][(offset+index)%3])
    # Touching edges across different conversations must never be joined.
    ev(PDF+'.pagesRotation=0;'+PDF+'.currentScale=1')
    time.sleep(.3)
    ev(SELECT)
    neighbors=ev("""(async()=>{
      const w=document.querySelector('iframe').contentWindow;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const c=JSON.parse(document.querySelector('#anchor-config').textContent);
      const original=captureTextSelection(w,w.PDFViewerApplication),r=original.segments[0].rectangles[0];
      const middle=(r[0]+r[2])/2,ids=[];
      for(const [left,right] of [[r[0],middle],[middle,r[2]]]){
        const anchor=structuredClone(original);
        anchor.segments[0].rectangles=[[left,r[1]-60,right,r[3]-60]];
        ids.push((await createThread(c.threadsUrl,anchor,'Independent touching neighbor')).thread_id);
      }
      w.getSelection().removeAllRanges();return ids;
    })()""")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight').length===6")
    independent=ev("""(()=>{
      const d=document.querySelector('iframe').contentDocument,ids=IDS;
      return ids.map(id=>{
        const nodes=[...d.querySelectorAll('.pdf-review-thread-highlight')].filter(e=>e.dataset.threadId===id);
        const r=nodes[0].getBoundingClientRect();
        return {count:nodes.length,left:r.left,right:r.right};
      });
    })()""".replace('IDS',json.dumps(neighbors)))
    assert [n['count'] for n in independent]==[1,1],independent
    assert abs(independent[0]['right']-independent[1]['left'])<.1,independent
    for thread_id in neighbors:
        ev("document.querySelector('iframe').contentDocument.querySelector('[data-thread-id=\""+thread_id+"\"].pdf-review-thread-highlight').click()")
        wait("document.querySelector('.thread-card.active')?.dataset.threadId==="+json.dumps(thread_id))
    # Genuine native selection, starting underneath several overlapping comments
    # and starting outside their paint before entering it. No dispatched selection
    # ranges or replacement selection algorithm is used by these gestures.
    def drag_selection(start,end,page=1,through=False):
        ev("document.querySelector('.viewer-title').click()")
        ev("document.querySelector('iframe').contentWindow.getSelection().removeAllRanges()")
        selector=f'.page[data-page-number="{page}"] .textLayer span'
        ev("document.querySelector('iframe').contentDocument.querySelector("+json.dumps(selector)+").scrollIntoView({block:'center'})")
        time.sleep(.2)
        points=ev("""(()=>{
          const f=document.querySelector('iframe'),w=f.contentWindow,d=w.document,
            span=d.querySelector(SELECTOR),text=span.firstChild,b=f.getBoundingClientRect();
          const point=offset=>{
            const r=d.createRange();r.setStart(text,Math.max(0,offset));r.collapse(true);
            const rect=r.getBoundingClientRect();
            return {x:b.left+rect.left+(offset<0?-6:.25),y:b.top+rect.top+rect.height/2};
          };
          return {start:point(START),end:point(END),expected:text.data.slice(Math.max(0,START),END)};
        })()""".replace('START',str(start)).replace('END',str(end)).replace('SELECTOR',json.dumps(selector)))
        p,q=points['start'],points['end']
        cdp.call('Input.dispatchMouseEvent',dict(type='mouseMoved',**p),a)
        cdp.call('Input.dispatchMouseEvent',dict(type='mousePressed',**p,button='left',clickCount=1),a)
        for step in range(1,9):
            cdp.call('Input.dispatchMouseEvent',dict(type='mouseMoved',
                x=p['x']+(q['x']-p['x'])*step/8,y=p['y']+(q['y']-p['y'])*step/8,
                buttons=1,button='left'),a)
        cdp.call('Input.dispatchMouseEvent',dict(type='mouseReleased',**q,button='left',clickCount=1),a)
        actual=ev("document.querySelector('iframe').contentWindow.getSelection().toString()")
        if not through:
            assert actual==points['expected'],dict(actual=actual,points=points)
        assert ev("document.querySelector('.thread-card.active')===null")
        payload=ev("""(async()=>{
          const w=document.querySelector('iframe').contentWindow;
          const {captureTextSelection}=await import('/static/review/anchor_selection.js');
          return captureTextSelection(w,w.PDFViewerApplication);
        })()""")
        assert payload['selection_text']==actual,payload
        if through:
            segment=payload['segments'][0]
            assert segment['page_number']==page and segment['text_start']<7 and segment['text_end']>18,segment
    drag_selection(3,20)
    # Page two has just a middle-of-line anchor, so the native drag can start
    # on unhighlighted text and extend across it into unhighlighted text again.
    ev(PDF+'.currentPageNumber=2')
    wait(PDF+'.getPageView(1).textLayer?.div?.querySelector("span")!=null')
    ev("""(async()=>{
      const w=document.querySelector('iframe').contentWindow,d=w.document;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const text=w.PDFViewerApplication.pdfViewer.getPageView(1).textLayer.div.querySelector('span').firstChild;
      const r=d.createRange();r.setStart(text,7);r.setEnd(text,18);
      w.getSelection().removeAllRanges();w.getSelection().addRange(r);
      const c=JSON.parse(document.querySelector('#anchor-config').textContent);
      await createThread(c.threadsUrl,captureTextSelection(w,w.PDFViewerApplication),'Middle of second page line');
      w.getSelection().removeAllRanges();
    })()""")
    wait("document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight').length===7")
    drag_selection(0,25,page=2,through=True)
    # A single click after selection still opens the expected overlapping thread.
    p=point()
    click(p,p['ids'][0])
    # Invisible highlights must not remain an invisible click target.
    ev("document.querySelector('.viewer-title').click();document.querySelector('iframe').contentWindow.getSelection().removeAllRanges()")
    ev("(()=>{const select=document.querySelector('#comments-visibility');select.value='hidden';select.dispatchEvent(new Event('change'));})()")
    wait("document.querySelector('iframe').contentDocument.documentElement.classList.contains('review-comments-hidden')")
    p=point()
    for kind in ['mousePressed','mouseReleased']:
        cdp.call('Input.dispatchMouseEvent',dict(type=kind,x=p['x'],y=p['y'],button='left',clickCount=1),a)
    assert ev("document.querySelector('.thread-card.active')===null")
    ev("(()=>{const select=document.querySelector('#comments-visibility');select.value='expanded';select.dispatchEvent(new Event('change'));})()")
    print('PASS fragment normalization, separate/overlapping comments and cycling, hover, native drag selection through highlights, immutable geometry, zoom and rotation',flush=True)
