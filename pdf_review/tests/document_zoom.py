"""One focused browser run: native zoom, independent UI bounds and mobile input."""
import time
from tests.viewer_acceptance import PDF, SELECT, viewport, change


def mixed_pdf(marker):
    sizes=[(612,792),(792,612),(500,900),(900,500),(612,792),(792,612),(500,900),(900,500)]
    font=3+len(sizes)*2
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',
        ('<< /Type /Pages /Kids ['+' '.join(f'{3+i*2} 0 R' for i in range(len(sizes)))+f'] /Count {len(sizes)} >>').encode()]
    for i,(width,height) in enumerate(sizes):
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Resources << /Font << /F1 {font} 0 R >> >> /Contents {4+i*2} 0 R >>'.encode())
        stream=f'BT /F1 16 Tf 60 400 Td (Review sentence {marker} page {i+1}.) Tj ET'.encode()
        objects.append(b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream')
    objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    data=b'%PDF-1.4\n';offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(data));data+=f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(data);data+=f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode()
    data+=b''.join(f'{offset:010} 00000 n \n'.encode() for offset in offsets[1:])
    return data+f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


def run_zoom(cdp,a,b,fixture,base,mobile_only=False):
    ev=lambda script:cdp.evaluate(a,script)
    wait=lambda script:cdp.wait(a,script)
    viewport(cdp,a,1440,950)
    ev(PDF+'.currentScale=1');ev(SELECT)
    wait("!document.querySelector('#comment-selection-button').disabled")
    ev("document.querySelector('#comment-selection-button').click();document.querySelector('#selection-comment-body').value='Zoom fixture';document.querySelector('#selection-comment-form').requestSubmit()")
    wait("document.querySelector('.thread-card')!==null")
    ev("""window.zoomApp=document.querySelector('iframe').contentWindow.PDFViewerApplication;
      window.zoomPdf=zoomApp.pdfViewer;
      window.zoomPoint=(page,x,y)=>{const p=zoomPdf.getPageView(page-1),r=p.div.getBoundingClientRect();
        return p.viewport.convertToPdfPoint((x-r.left-p.div.clientLeft)*p.viewport.width/p.div.clientWidth,
          (y-r.top-p.div.clientTop)*p.viewport.height/p.div.clientHeight);};
      window.zoomPrepare=(page,x,y)=>{zoomPdf.currentPageNumber=page;zoomPdf.currentScale=2.8;
        const r=zoomPdf.getPageView(page-1).div.getBoundingClientRect(),s=zoomPdf.container;
        s.scrollLeft+=r.left+r.width*.5-x;s.scrollTop+=r.top+r.height*.5-y;};""")
    worst=0;cases=0
    def settle():
        time.sleep(.12)
        ev('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    def zoom(page,x,y,factor):
        nonlocal worst,cases
        before=ev(f'zoomPoint({page},{x},{y})')
        ev(f'zoomApp.updateZoom(null,{factor},[{x},{y}])')
        settle()
        after=ev(f'zoomPoint({page},{x},{y})');scale=ev('zoomPdf.currentScale')
        drift=max(abs(u-v) for u,v in zip(before,after))*scale*4/3
        worst=max(worst,drift);cases+=1
        assert drift<6,('native focal drift',page,x,y,factor,drift,before,after,ev('({origin:zoomApp.reviewStage.origin,left:zoomPdf.container.scrollLeft,top:zoomPdf.container.scrollTop})'))
    for right,left in ([] if mobile_only else [(False,False),(True,False),(False,True),(True,True)]):
        if ev("!!document.querySelector('.comment-filter-panel')"):
            ev("document.querySelector('.comment-filter-panel .dialog-header button:last-child').click()")
        change(cdp,a,'#comments-visibility','expanded' if right else 'hidden')
        if left:
            ev("document.querySelector('[data-comment-filters]').click()")
            # Different width/height: the stage uses measured bounds, not a gutter constant.
            ev("document.querySelector('.comment-filter-panel').style.width='410px';document.querySelector('.comment-filter-panel').style.minHeight='750px'")
        for mode,spread,page,x,y in [(0,0,1,650,320),(0,1,4,850,380),(0,2,5,600,300),(1,0,3,800,350),(2,1,6,700,400)]:
            ev(f'zoomPdf.scrollMode={mode};zoomPdf.spreadMode={spread}')
            settle();ev(f'zoomPrepare({page},{x},{y})');settle()
            for factor in [1.06,1.06,1/1.06,1/1.06]:zoom(page,x,y,factor)
        # Changes to card bounds do not translate pages under a stationary pointer.
        ev('zoomPdf.scrollMode=0;zoomPdf.spreadMode=0;zoomPrepare(1,700,350)');settle()
        before=ev('zoomPoint(1,700,350)')
        if left:
            ev("document.querySelector('.comment-filter-panel').style.width='535px';document.querySelector('.comment-filter-panel').style.minHeight='970px'")
        else:
            ev("document.querySelector('[data-comment-filters]').click()")
        settle();after=ev('zoomPoint(1,700,350)')
        assert max(abs(u-v) for u,v in zip(before,after))*ev('zoomPdf.currentScale')*4/3<2,('card resize/open',before,after)
        for _ in range(2):
            ev("document.querySelector('.comment-filter-panel .left-card-pin').click()")
            settle();after=ev('zoomPoint(1,700,350)')
            assert max(abs(u-v) for u,v in zip(before,after))*ev('zoomPdf.currentScale')*4/3<2,('pin/unpin',before,after)
        ev("document.querySelector('.comment-filter-panel .dialog-header button:last-child').click()")
        settle();after=ev('zoomPoint(1,700,350)')
        assert max(abs(u-v) for u,v in zip(before,after))*ev('zoomPdf.currentScale')*4/3<2,('card close',before,after)
        ev("document.documentElement.style.setProperty('--comment-width','340px')")
        settle();after=ev('zoomPoint(1,700,350)')
        assert max(abs(u-v) for u,v in zip(before,after))*ev('zoomPdf.currentScale')*4/3<2,('right width',before,after)
        ev("document.documentElement.style.removeProperty('--comment-width')")
    # Measured arbitrary bounds support future columns/layers, not only current cards.
    time.sleep(.2)  # Origin reclamation intentionally waits for native scrolling to idle.
    before=ev('zoomPoint(1,700,350)')
    card_before=ev("document.querySelector('.thread-card').getBoundingClientRect().toJSON()")
    card_immediate=ev("zoomApp.reviewStage.setBounds('future-columns',[{left:-900,right:4200,top:-600,bottom:14000}]);zoomApp.reviewStage.commit();document.querySelector('.thread-card').getBoundingClientRect().toJSON()")
    assert abs(card_before['left']-card_immediate['left'])<2 and abs(card_before['top']-card_immediate['top'])<2,('atomic overlay rebase',card_before,card_immediate)
    settle();after=ev('zoomPoint(1,700,350)')
    assert max(abs(u-v) for u,v in zip(before,after))*ev('zoomPdf.currentScale')*4/3<2
    assert ev('zoomPdf.container.scrollWidth>=4200&&zoomPdf.container.scrollHeight>=14000')
    ev("zoomApp.reviewStage.setBounds('future-columns',[])")
    settle()
    # Exercise the actual trackpad wheel entry point, including iframe offset.
    ev('zoomPdf.scrollMode=0;zoomPdf.spreadMode=0;zoomPrepare(1,700,350)');settle()
    frame=ev("document.querySelector('iframe').getBoundingClientRect().toJSON()")
    for delta in [-4,-4,-4,4,4,4]:
        before=ev('zoomPoint(1,700,350)')
        cdp.call('Input.dispatchMouseEvent',{'type':'mouseWheel','x':700+frame['left'],'y':350+frame['top'],
            'deltaX':0,'deltaY':delta,'modifiers':2},a)
        settle();after=ev('zoomPoint(1,700,350)')
        drift=max(abs(u-v) for u,v in zip(before,after))*ev('zoomPdf.currentScale')*4/3
        assert drift<6,('trackpad wheel',delta,drift)
    # A tall card must not change page centering by introducing a vertical bar
    # when the PDF itself fits entirely inside the viewport.
    ev('zoomPdf.scrollMode=3;zoomPdf.currentPageNumber=1;zoomPdf.currentScale=.3;zoomPdf.container.scrollTop=0;zoomPdf.container.scrollLeft=0')
    settle();before=ev('zoomPoint(1,700,200)')
    ev("document.querySelector('[data-comment-filters]').click();document.querySelector('.comment-filter-panel').style.minHeight='1400px'")
    settle();after=ev('zoomPoint(1,700,200)')
    assert max(abs(u-v) for u,v in zip(before,after))*.3*4/3<2,('scrollbar appearance',before,after)
    ev("document.querySelector('.comment-filter-panel .dialog-header button:last-child').click()")
    assert ev('!!zoomApp._touchManager')
    print(f'PASS {cases} native zoom steps, all four rail states, mixed 8-page PDF, odd/even spreads, vertical/horizontal/wrapped layouts, dynamic bounds; max drift {worst:.2f} CSS px',flush=True)
    # Real two-touch browser input, also without waiting for redraw between reversals.
    cdp.call('Emulation.setDeviceMetricsOverride',{'width':375,'height':667,'deviceScaleFactor':2,'mobile':True},a)
    cdp.call('Emulation.setTouchEmulationEnabled',{'enabled':True,'maxTouchPoints':2},a)
    change(cdp,a,'#comments-visibility','mobile')
    ev('zoomPdf.scrollMode=0;zoomPdf.spreadMode=0;zoomPdf.currentScale=1;zoomPdf.currentPageNumber=3;zoomPdf.container.scrollLeft=200;zoomPdf.container.scrollTop+=180')
    time.sleep(.3)
    wait('zoomPdf.getPageView(2).textLayer?.div.querySelector("span")!==null')
    ev("""(async()=>{const w=document.querySelector('iframe').contentWindow;
      const range=w.document.createRange();range.selectNodeContents(zoomPdf.getPageView(2).textLayer.div.querySelector('span'));
      w.getSelection().removeAllRanges();w.getSelection().addRange(range);
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const config=JSON.parse(document.querySelector('#anchor-config').textContent);
      await createThread(config.threadsUrl,captureTextSelection(w,zoomApp),'Live mobile highlight');
      w.getSelection().removeAllRanges();})()""")
    wait("zoomPdf.getPageView(2).div.querySelector('.pdf-review-thread-highlight')!==null")
    ev("""(async()=>{const config=JSON.parse(document.querySelector('#anchor-config').textContent);
      const data=await(await fetch(config.threadsUrl)).json();
      window.liveRectangle=data.threads.find(t=>t.targets[0].anchor.segments[0].page_number===3).targets[0].anchor.segments[0].rectangles[0];
      window.liveHighlight=zoomPdf.getPageView(2).div.querySelector('.pdf-review-thread-highlight');
      window.liveHighlightError=()=>{const p=zoomPdf.getPageView(2),v=p.viewport,r=liveRectangle;
        const current=p.div.querySelector('.pdf-review-thread-highlight');
        if(liveHighlight.isConnected&&liveHighlight!==current)throw new Error('App replaced a connected touch target');
        liveHighlight=current;
        const [x1,y1]=v.convertToViewportPoint(r[0],r[1]),[x2,y2]=v.convertToViewportPoint(r[2],r[3]);
        const b=liveHighlight.getBoundingClientRect(),page=p.div.getBoundingClientRect();
        return Math.max(Math.abs(b.left-page.left-p.div.clientLeft-Math.min(x1,x2)*p.div.clientWidth/v.width),
          Math.abs(b.top-page.top-p.div.clientTop-Math.min(y1,y2)*p.div.clientHeight/v.height),
          Math.abs(b.width-Math.abs(x2-x1)*p.div.clientWidth/v.width),
          Math.abs(b.height-Math.abs(y2-y1)*p.div.clientHeight/v.height));};})()""")
    live_error=0
    def point():return ev('zoomPoint(3,185,260)')
    def pinch(start,end,detach=False):
        nonlocal live_error
        frame=ev("document.querySelector('iframe').getBoundingClientRect().toJSON()")
        if detach:
            ev(f"window.detachedTouchTarget=document.querySelector('iframe').contentDocument.createElement('div');detachedTouchTarget.style.cssText='position:fixed;z-index:999;left:{185-start/2-15}px;top:240px;width:30px;height:40px';zoomPdf.container.append(detachedTouchTarget)")
        first={'x':185-start/2+frame['left'],'y':260+frame['top'],'id':0}
        cdp.call('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[first]},a)
        for i in range(13):
            span=start+(end-start)*i/12
            points=[{'x':185-span/2+frame['left'],'y':260+frame['top'],'id':0},{'x':185+span/2+frame['left'],'y':260+frame['top'],'id':1}]
            cdp.call('Input.dispatchTouchEvent',{'type':'touchStart' if i==0 else 'touchMove','touchPoints':points},a)
            if detach and i==0:ev('detachedTouchTarget.remove()')
            time.sleep(.02)
            error=ev('liveHighlightError()');live_error=max(live_error,error)
            assert error<1.5,('live highlight drift during contact',i,error)
            assert ev("liveHighlight.isConnected&&liveHighlight===zoomPdf.getPageView(2).div.querySelector('.pdf-review-thread-highlight')")
        cdp.call('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]},a)
    touch_worst=0
    for start,end in [(100,260),(260,100),(100,240),(240,100)]:
        before=point();scale=ev('zoomPdf.currentScale');site=ev('visualViewport.scale')
        pinch(start,end)
        now=ev('zoomPdf.currentScale');after=point()
        assert now>scale*1.1 if end>start else now<scale*.9,(start,end,scale,now)
        drift=max(abs(u-v) for u,v in zip(before,after))*now*4/3
        touch_worst=max(touch_worst,drift)
        assert drift<9,('touch focal drift',drift,before,after)
        assert abs(ev('visualViewport.scale')-site)<.01
    time.sleep(.7)
    after=point()
    drift=max(abs(u-v) for u,v in zip(before,after))*ev('zoomPdf.currentScale')*4/3
    touch_worst=max(touch_worst,drift)
    assert drift<9,('settled touch focal drift',drift,before,after)
    assert not ev('zoomApp.reviewPdfTouchActive')
    before=point();scale=ev('zoomPdf.currentScale')
    pinch(100,240,detach=True)
    assert ev('zoomPdf.currentScale')>scale*1.1
    after=point()
    assert max(abs(u-v) for u,v in zip(before,after))*ev('zoomPdf.currentScale')*4/3<9,('detached target',before,after)
    time.sleep(.3)
    ev("zoomApp.reviewStage.setBounds('pan-space',[{left:0,right:500,top:-500,bottom:14000}])")
    time.sleep(.3)
    top=ev('zoomPdf.container.scrollTop')
    ev("""window.panScrollWrites=0;const w=document.querySelector('iframe').contentWindow;
      for(const name of ['scrollTop','scrollLeft']) {const d=Object.getOwnPropertyDescriptor(w.Element.prototype,name);
      Object.defineProperty(zoomPdf.container,name,{configurable:true,get(){return d.get.call(this)},set(value){panScrollWrites++;d.set.call(this,value)}});}
      window.panScale=zoomPdf.currentScale;""")
    frame=ev("document.querySelector('iframe').getBoundingClientRect().toJSON()")
    for i in range(7):
        cdp.call('Input.dispatchTouchEvent',{'type':'touchStart' if i==0 else 'touchMove','touchPoints':[{'x':185,'y':frame['top']+400-i*20,'id':0}]},a)
        if i==0:ev("zoomApp.reviewStage.setBounds('pan-space',[])")
        time.sleep(.025)
    time.sleep(.06)
    pan_distance=ev('zoomPdf.container.scrollTop')-top
    assert 85<pan_distance<130,('one-finger displacement for 120px drag',pan_distance)
    assert ev('panScrollWrites===0'),('app writes during one-finger pan',ev('panScrollWrites'))
    assert ev('zoomPdf.currentScale===panScale')
    cdp.call('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]},a)
    ev("delete zoomPdf.container.scrollTop;delete zoomPdf.container.scrollLeft")
    wait(f'zoomPdf.container.scrollTop>{top+30}')
    result=ev("""(()=>{const w=document.querySelector('iframe').contentWindow;
      const pdf=new w.Event('gesturechange',{bubbles:true,cancelable:true});zoomPdf.container.dispatchEvent(pdf);
      const chrome=new Event('gesturechange',{bubbles:true,cancelable:true});document.querySelector('.viewer-title').dispatchEvent(chrome);
      return {pdf:pdf.defaultPrevented,chrome:chrome.defaultPrevented};})()""")
    assert result==dict(pdf=True,chrome=False),result
    print(f'PASS live highlights during contact ({live_error:.2f}px max), pinch/reversal, detached targets; one-finger 120px drag moved {pan_distance:.2f}px with no app scroll writes; touch drift {touch_worst:.2f}px; physical iPhone Safari UNVERIFIED',flush=True)
