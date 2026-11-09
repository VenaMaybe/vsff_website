"""The base page owns loading UI; detail tiles refine an already painted page."""
import time


def run_detail_loading(cdp, session):
    ev = lambda script: cdp.evaluate(session, script)
    cdp.call('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=3, mobile=True), session)
    ev("""window.detailApp=document.querySelector('iframe').contentWindow.PDFViewerApplication;
      window.detailPdf=detailApp.pdfViewer;window.detailPage=detailPdf.getPageView(0);
      detailPdf.currentPageNumber=1;detailPdf.scrollMode=0;detailPdf.spreadMode=0;
      detailPage.maxCanvasPixels=5242880;detailPage.enableDetailCanvas=true;
      window.detailDraws=[];
      detailApp.eventBus.on('pagerender',e=>{if(e.source===detailPage.detailView)
        detailDraws.push({base:detailPage.renderingState,loading:detailPage.div.classList.contains('loadingIcon')});});
      detailPdf.currentScale=3;detailPdf.container.scrollLeft=300;detailPdf.container.scrollTop=300;
    """)
    cdp.wait(session, 'detailPage.renderingState===3&&detailPage.detailView?.renderingState===3')
    for _ in range(4):
        ev('detailPdf.container.scrollTop+=400')
        time.sleep(.15)
    cdp.wait(session, 'detailPage.detailView?.renderingState===3')
    records = ev('detailDraws')
    assert len(records) >= 2, records
    assert all(r['base'] == 3 and not r['loading'] for r in records), ('detail redraw displayed page loading indicator', records)
    # Deterministic coverage of the native lifecycle, including a slow tile.
    state = ev("""(async()=>{const p=detailPage,d=p.detailView;
      d.renderingState=1;await new Promise(r=>setTimeout(r,20));
      const detailLoading=p.div.classList.contains('loading');d.renderingState=3;
      p.renderingState=1;await new Promise(r=>setTimeout(r,20));
      const initialLoading=p.div.classList.contains('loading');p.renderingState=3;
      return {detailLoading,initialLoading};})()""")
    assert state == dict(detailLoading=False, initialLoading=True), state
    print(f'PASS {len(records)} native detail redraws without page spinner; initial page loading indicator retained', flush=True)
