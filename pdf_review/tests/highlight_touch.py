"""Touch regression cases use real DOM hit testing and the production recognizer."""
import time


def check_touch(cdp, session, point):
    ev=lambda script:cdp.evaluate(session,script)
    # Native touch input: generated compatibility clicks must not cycle twice or
    # reach the viewer's outside-click handler and immediately close the thread.
    cdp.call('Emulation.setTouchEmulationEnabled',{'enabled':True,'maxTouchPoints':2},session)
    for _ in range(3):
        current=ev("document.querySelector('.thread-card.active')?.dataset.threadId")
        index=point['ids'].index(current) if current in point['ids'] else -1
        expected=point['ids'][(index+1)%len(point['ids'])]
        cdp.call('Input.dispatchTouchEvent',dict(type='touchStart',touchPoints=[dict(x=point['x'],y=point['y'],id=1)]),session)
        cdp.call('Input.dispatchTouchEvent',dict(type='touchEnd',touchPoints=[]),session)
        time.sleep(.15)
        assert ev("document.querySelector('.thread-card.active')?.dataset.threadId") == expected
    cdp.call('Emulation.setTouchEmulationEnabled',{'enabled':False},session)
    result=ev("""(async()=>{
      const {AnchorOverlay}=await import('/static/review/anchor_overlay.js');
      const frame=document.createElement('iframe');
      frame.style.cssText='position:fixed;left:0;top:0;width:300px;height:300px;z-index:99999';document.body.append(frame);
      try{
        const w=frame.contentWindow,d=w.document;d.body.style.margin='0';
        d.body.innerHTML='<div class="page" style="position:relative;width:200px;height:100px"><span style="display:block;width:200px;height:100px">some selectable words</span><div class="pdf-review-anchor-overlay" style="position:absolute;inset:0;pointer-events:none"></div></div><div id="scroll" style="height:20px;overflow:auto"><div style="height:200px"></div></div>';
        const scroller=d.querySelector('#scroll'),layer=d.querySelector('.pdf-review-anchor-overlay');
        const instance=new AnchorOverlay(w,{pdfViewer:{container:scroller},eventBus:{on(){}}});
        const regions=['a','b'].map((id,i)=>{
          const node=d.createElement('div');node.dataset.threadId=id;layer.append(node);
          return {node,left:.1+i*.2,right:.6+i*.2,top:.2,bottom:.4};
        });instance.hitRegions.set(layer,regions);
        const opened=[];instance.onThreadSelect=id=>{opened.push(id);instance.selectedThreadId=id;};
        let target=d.querySelector('span');
        const send=(type,extras={})=>target.dispatchEvent(new w.PointerEvent(type,{bubbles:true,cancelable:true,
          pointerId:1,isPrimary:true,pointerType:'touch',button:0,buttons:type==='pointerdown'?1:0,clientX:80,clientY:30,...extras}));
        const click=(detail=1)=>target.dispatchEvent(new w.MouseEvent('click',{bubbles:true,cancelable:true,button:0,detail,clientX:80,clientY:30}));
        const expect=(count,label)=>{if(opened.length!==count)throw Error(label+': '+JSON.stringify(opened));};
        send('pointerdown');send('pointerup');expect(1,'Tap without click');click();expect(1,'Duplicate compatibility click');
        send('pointerdown');send('pointerup');click(2);expect(2,'Rapid repeat tap');
        send('pointerdown');scroller.scrollTop=.5;send('pointerup');expect(3,'Fractional scroll settling');scroller.scrollTop=0;
        send('pointerdown',{clientY:17});send('pointerup',{clientY:17});expect(4,'Narrow highlight near miss');
        send('pointerdown');send('pointermove',{clientX:110,buttons:1});send('pointerup');click();expect(4,'Selection drag');
        send('pointerdown');send('pointercancel');send('pointerup');click();expect(4,'Cancelled pan');
        send('pointerdown');scroller.scrollTop=10;send('pointerup');click();expect(4,'Actual scrolling');scroller.scrollTop=0;
        send('pointerdown');send('pointerdown',{pointerId:2,isPrimary:false});send('pointerup');click();expect(4,'Multi-touch');
        send('pointerdown');await new Promise(r=>setTimeout(r,470));send('pointerup');click();expect(4,'Long press');
        send('pointerdown');const range=d.createRange();range.selectNodeContents(target);w.getSelection().addRange(range);
        send('pointerup');click();expect(4,'New native text selection');w.getSelection().removeAllRanges();
        send('pointerdown');const replacement=target.cloneNode(true);target.replaceWith(replacement);target=replacement;
        send('pointerup');expect(5,'Replaced text target');
        send('pointerdown');w.dispatchEvent(new w.Event('blur'));send('pointerup');click();expect(5,'Lost focus');
        d.documentElement.classList.add('review-comments-hidden');send('pointerdown');send('pointerup');click();expect(5,'Hidden comments');
        d.documentElement.classList.remove('review-comments-hidden');
        send('pointerdown');scroller.scrollTop=2;send('pointerup');click();expect(6,'Stationary tap with native settling');scroller.scrollTop=0;
        send('pointerdown');instance.application.pdfViewer.currentScale=2;send('pointerup');click();expect(6,'Scale changed during tap');
        send('pointerdown');scroller.scrollTop=20;scroller.dispatchEvent(new w.Event('scroll'));scroller.scrollTop=0;
        send('pointerup');click();expect(6,'Scroll moved away and returned');
        send('pointerdown',{clientX:25});send('pointerup',{clientX:155});click();expect(6,'Release over different thread');
        send('pointerdown');regions.forEach((r,i)=>r.node.dataset.threadId='replacement'+i);
        send('pointerup');click();expect(6,'Same point with changed thread identity');
        return opened;
      }finally{frame.remove();}
    })()""")
    assert result==['a','b','a','b','a','b'],result
    print('PASS native touch taps, single activation, rapid repeats, narrow hits, replaced targets; pan/pinch/long-press/selection cancellation',flush=True)
