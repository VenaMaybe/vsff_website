"""Phone recorder lifecycle, native pinch capture and real JSON download."""
import json
from pathlib import Path
import tempfile
import time


def run_touch_recorder(cdp, session, base, fixture):
    ev = lambda script: cdp.evaluate(session, script)
    assert ev('!window.reviewTouchDiagnostics&&!document.querySelector("#touch-diagnostics")')
    cdp.call('Emulation.setDeviceMetricsOverride',dict(width=390,height=844,deviceScaleFactor=3,mobile=True),session)
    cdp.call('Emulation.setTouchEmulationEnabled',dict(enabled=True,maxTouchPoints=2),session)
    cdp.call('Page.navigate',{'url':base+f'/versions/{fixture["versions"][0]}/view?debug=touch'},session)
    cdp.wait(session,'!!document.querySelector("#touch-diagnostics")')
    assert ev('!reviewTouchDiagnostics.recording&&reviewTouchDiagnostics.entries.length===0')
    ev("window.recApp=document.querySelector('iframe').contentWindow.PDFViewerApplication;window.recPdf=recApp.pdfViewer;recPdf.currentScale=1;recPdf.currentPageNumber=100")
    cdp.wait(session,'recPdf.getPageView(99).renderingState===3')
    # Actual touch on the recorder Start button; no console required by users.
    def button(index):
        point=ev(f"(()=>{{const r=document.querySelectorAll('#touch-diagnostics button')[{index}].getBoundingClientRect();return {{x:r.left+r.width/2,y:r.top+r.height/2}};}})()")
        for kind,points in [('touchStart',[dict(**point,id=7)]),('touchEnd',[])]:
            cdp.call('Input.dispatchTouchEvent',dict(type=kind,touchPoints=points),session)
    button(0)
    assert ev('reviewTouchDiagnostics.recording')
    top=ev("document.querySelector('iframe').getBoundingClientRect().top")
    for start,end in [(100,220),(220,100)]:
        for i in range(10):
            span=start+(end-start)*i/9
            points=[dict(x=185-span/2,y=top+260,id=0),dict(x=185+span/2,y=top+260,id=1)]
            cdp.call('Input.dispatchTouchEvent',dict(type='touchStart' if i==0 else 'touchMove',touchPoints=points),session)
            time.sleep(.02)
        cdp.call('Input.dispatchTouchEvent',dict(type='touchEnd',touchPoints=[]),session)
    time.sleep(.1)
    button(1)
    assert ev('!reviewTouchDiagnostics.recording')
    captured=ev('reviewTouchDiagnostics.snapshot()')
    kinds={e['type'] for e in captured['entries']}
    assert {'touchmove','frame','geometry','scroll','scalechanging','recording-stop'} <= kinds,kinds
    assert any(e['type']=='geometry' and e['midpoint'] and any(p['page']==100 and p['pdfPoint'] for p in e['pages']) for e in captured['entries'])
    assert all(len(e['pages'])<=4 for e in captured['entries'] if e['type']=='geometry')
    count=len(captured['entries'])
    ev('recPdf.currentScale=1.2')
    time.sleep(.1)
    assert ev('reviewTouchDiagnostics.entries.length')==count
    with tempfile.TemporaryDirectory(prefix='pdf-touch-export-') as directory:
        context=cdp.call('Target.getTargetInfo',session=session)['targetInfo']['browserContextId']
        cdp.call('Browser.setDownloadBehavior',dict(behavior='allow',downloadPath=directory,browserContextId=context))
        button(2)
        path=Path(directory)/'pdf-review-touch-trace.json'
        deadline=time.monotonic()+10
        while not path.exists() and time.monotonic()<deadline:
            time.sleep(.1)
        assert path.exists(),'Download button did not export a file'
        exported=json.loads(path.read_text())
        assert exported['format']=='pdf-review-touch-v2' and exported['entries']==captured['entries']
        assert exported['pages']==128
    result=ev("""(()=>{const api=reviewTouchDiagnostics;api.start();
      for(let i=0;i<6100;i++)api.record('limit-test');
      const bounded=!api.recording&&api.entries.length===6000;
      api.stop();recPdf.currentScale=1.3;
      return bounded&&api.entries.length===6000&&!window.reviewTouchDiagnostics&&!document.querySelector('#touch-diagnostics');})()""")
    assert result
    print(f'PASS phone recorder: opt-in, touch Start/Stop, native pinch on page 100, frame/geometry/scroll capture, frozen export ({count} records), real JSON download, event limit and cleanup',flush=True)
