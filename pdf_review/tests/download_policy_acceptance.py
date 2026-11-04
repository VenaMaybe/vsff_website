"""Download/print UI policy checks in disposable authenticated browsers."""
import json
from tests.viewer_acceptance import PDF, viewport, screenshot


def run_download_policy(cdp,a,b,fixture,base):
    def ev(script,session=a): return cdp.evaluate(session,script)
    def wait(script,session=a): return cdp.wait(session,script)
    doc=fixture['document_id']
    viewport(cdp,a,1440,1000)
    def save(value):
        ev("document.querySelector('[data-review-settings]').click()")
        wait("document.querySelector('[name=downloads_allowed]')!==null")
        ev("document.querySelector('[name=downloads_allowed]').value="+json.dumps(str(value))+";document.querySelector('.settings-form').requestSubmit()")
        wait("document.querySelector('.settings-panel')===null")
    assert ev("!document.querySelector('[data-pdf-control=downloadButton]').hidden")
    save(0)
    for session in [a,b]:
        wait("document.body.dataset.downloadsAllowed==='false'",session)
        assert ev("[...document.querySelectorAll('[data-pdf-control=downloadButton],[data-pdf-control=printButton]')].every(b=>b.hidden&&b.disabled&&getComputedStyle(b).display==='none')",session)
        assert ev("[...document.querySelector('iframe').contentDocument.querySelectorAll('#downloadButton,#secondaryDownload,#printButton,#secondaryPrint,#attachmentsViewMenu')].every(b=>getComputedStyle(b).display==='none')",session)
        for target in ['document',"document.querySelector('iframe').contentDocument"]:
            assert ev("['s','p'].every(key=>['ctrlKey','metaKey'].every(mod=>{const e=new KeyboardEvent('keydown',{key,[mod]:true,cancelable:true,bubbles:true});"+target+".dispatchEvent(e);return e.defaultPrevented;}))",session)
    # Invoke real native application/event-bus/attachment paths; no data or print work.
    result=ev("""(async()=>{const w=document.querySelector('iframe').contentWindow,a=w.PDFViewerApplication;
      let data=0,printing=0,exports=0;
      const originalData=a.pdfDocument.getData,originalPrint=w.print,originalTrigger=a.downloadManager._triggerDownload;
      a.pdfDocument.getData=async()=>{data++;return new Uint8Array([1]);};
      w.print=()=>printing++;a.downloadManager._triggerDownload=()=>exports++;
      try {
        await a.download();await a.save();await a.downloadOrSave();await a.triggerPrinting();a.beforePrint();
        a.eventBus.dispatch('download',{});a.eventBus.dispatch('print',{});
        a.downloadManager.download(new Uint8Array([1]),'','x.pdf');
        a.downloadManager.downloadData(new Uint8Array([1]),'x.pdf','application/pdf');
        a.downloadManager.openOrDownloadData(new Uint8Array([1]),'x.pdf');
        w.document.getElementById('downloadButton').click();w.document.getElementById('printButton').click();
        await new Promise(r=>setTimeout(r,100));
        return {data,printing,exports,printService:!!a.printService};
      } finally {a.pdfDocument.getData=originalData;w.print=originalPrint;a.downloadManager._triggerDownload=originalTrigger;}
    })()""")
    assert result==dict(data=0,printing=0,exports=0,printService=False),result
    ev("document.querySelector('#review-view-menu').open=true")
    screenshot(cdp,a,'downloads-disabled')
    ev("document.querySelector('#review-view-menu').open=false")
    # Initial server-rendered policy survives a reload without briefly exposing controls.
    ev('window.policyReloading=true');cdp.call('Page.reload',{},a)
    wait("!window.policyReloading&&document.querySelector('#realtime-status')?.textContent==='Live'")
    assert ev("document.body.dataset.downloadsAllowed==='false'&&"+PDF+".getPageView(0).pdfPage!==null")
    cdp.call('Emulation.setEmulatedMedia',{'media':'print'},a)
    assert ev("getComputedStyle(document.body).visibility==='hidden'&&getComputedStyle(document.body).display==='none'")
    assert ev("getComputedStyle(document.querySelector('iframe').contentDocument.body).visibility==='hidden'")
    cdp.call('Emulation.setEmulatedMedia',{'media':''},a)
    # Re-enable without reloading, including already-bound native event handlers.
    save(1)
    wait("document.body.dataset.downloadsAllowed==='true'",b)
    assert ev("!document.querySelector('[data-pdf-control=downloadButton]').hidden")
    result=ev("""(async()=>{const a=document.querySelector('iframe').contentWindow.PDFViewerApplication;
      let exports=0;const original=a.downloadManager._triggerDownload;
      a.downloadManager._triggerDownload=()=>exports++;
      try {await a.download();return exports;}finally{a.downloadManager._triggerDownload=original;}
    })()""")
    assert result==1,result
    print('PASS owner download toggle, live reviewer updates, native/app/attachment action guards, Ctrl/Cmd+S/P, reload rendering, print fallback and re-enable',flush=True)
