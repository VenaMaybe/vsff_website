"""Explicit PDF pinch regression, including Safari-style gesture events."""
import time
from tests.viewer_acceptance import PDF, viewport


def run_mobile_pinch(cdp,a):
    def ev(script):return cdp.evaluate(a,script)
    def wait(script):return cdp.wait(a,script)
    cdp.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':3,'mobile':True},a)
    cdp.call('Emulation.setTouchEmulationEnabled',{'enabled':True,'maxTouchPoints':3},a)
    ev(PDF+'.currentScale=1;'+PDF+'.container.scrollLeft=0;'+PDF+'.container.scrollTop=100')
    time.sleep(.3)
    initial=ev('visualViewport.scale')
    # Real browser touches: put fingers down sequentially and pinch both ways.
    def real(start,end):
        cdp.call('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':120,'y':350,'id':0}]},a)
        for index in range(8):
            distance=start+(end-start)*index/7
            points=[{'x':195-distance/2,'y':350,'id':0},{'x':195+distance/2,'y':350,'id':1}]
            cdp.call('Input.dispatchTouchEvent',{'type':'touchStart' if index==0 else 'touchMove','touchPoints':points},a)
            time.sleep(.025)
        cdp.call('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]},a)
    before=ev(PDF+'.currentScale');real(120,180)
    assert ev(PDF+'.currentScale')>before*1.3
    before=ev(PDF+'.currentScale');real(180,110)
    assert ev(PDF+'.currentScale')<before*.8
    assert abs(ev('visualViewport.scale')-initial)<.01
    # Use client positions when screen coordinates are unchanged. Gentle pinches
    # should work without the native recognizer's large confirmation threshold.
    ev("""window.pinchTouch=(type,coordinates,reverse=false)=>{const w=document.querySelector('iframe').contentWindow,target=w.PDFViewerApplication.pdfViewer.container;
      let touches=coordinates.map(([identifier,clientX,clientY])=>new w.Touch({identifier,target,clientX,clientY,screenX:0,screenY:0}));
      if(reverse)touches.reverse();const e=new w.TouchEvent(type,{touches,targetTouches:touches,changedTouches:touches,bubbles:true,cancelable:true});
      target.dispatchEvent(e);return e.defaultPrevented;};
      window.pinchGesture=(type,scale=1,host=false)=>{const f=document.querySelector('iframe'),w=f.contentWindow,target=host?f:w.PDFViewerApplication.pdfViewer.container;
        const e=new (host?Event:w.Event)(type,{bubbles:true,cancelable:true});
        Object.defineProperties(e,{scale:{value:scale},clientX:{value:195},clientY:{value:350}});target.dispatchEvent(e);return e.defaultPrevented;};""")
    ev(PDF+'.currentScale=1')
    assert ev("pinchTouch('touchstart',[[0,145,350],[1,245,350]])")
    ev("pinchTouch('touchmove',[[0,144,350],[1,246,350]],true)")
    assert abs(ev(PDF+'.currentScale')-1.02)<.011
    # Safari's additional gesture stream must not apply the same scale twice.
    assert ev("pinchGesture('gesturestart')")
    assert ev("pinchGesture('gesturechange',1.5)")
    assert abs(ev(PDF+'.currentScale')-1.02)<.011
    ev("pinchTouch('touchmove',[[0,120,350],[1,270,350]])")
    assert abs(ev(PDF+'.currentScale')-1.5)<.02
    ev("pinchTouch('touchcancel',[]);pinchGesture('gestureend')")
    # Safari may send touchstart then motion only through GestureEvents.
    ev(PDF+'.currentScale=1')
    ev("pinchTouch('touchstart',[[0,145,350],[1,245,350]]);pinchGesture('gesturestart');pinchGesture('gesturechange',1.25)")
    assert abs(ev(PDF+'.currentScale')-1.25)<.02
    ev("pinchTouch('touchmove',[[0,120,350],[1,270,350]])")
    assert abs(ev(PDF+'.currentScale')-1.25)<.02
    ev("pinchGesture('gesturechange',.9)")
    assert abs(ev(PDF+'.currentScale')-.9)<.02
    ev("pinchTouch('touchend',[]);pinchGesture('gestureend')")
    # Safari gesture-only fallback, including a gesture delivered to the host iframe.
    for host in ['false','true']:
        ev(PDF+'.currentScale=1')
        assert ev(f"pinchGesture('gesturestart',1,{host})")
        assert ev(f"pinchGesture('gesturechange',1.4,{host})")
        assert abs(ev(PDF+'.currentScale')-1.4)<.02
        ev(f"pinchGesture('gesturechange',.8,{host});pinchGesture('gestureend',1,{host})")
        assert abs(ev(PDF+'.currentScale')-.8)<.02
    # A single finger is left to native scrolling, with no zoom prevention.
    ev(PDF+'.currentScale=1')
    assert not ev("pinchTouch('touchstart',[[0,190,500]])")
    assert not ev("pinchTouch('touchmove',[[0,190,400]])")
    ev("pinchTouch('touchend',[])")
    ev(PDF+'.container.scrollTop=200')
    start=ev(PDF+'.container.scrollTop')
    for index in range(7):
        cdp.call('Input.dispatchTouchEvent',{'type':'touchStart' if index==0 else 'touchMove','touchPoints':[{'x':190,'y':550-index*20,'id':0}]},a)
        time.sleep(.025)
    cdp.call('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]},a)
    wait(PDF+f'.container.scrollTop>{start+30}')
    assert abs(ev(PDF+'.currentScale')-1)<.01
    assert abs(ev('visualViewport.scale')-initial)<.01
    print('PASS genuine pinch in/out, gentle client-coordinate pinch, reordered touches, Safari gesture fallback/host delivery, no duplicate zoom, cancellation and native one-finger scroll; physical iPhone not available',flush=True)
