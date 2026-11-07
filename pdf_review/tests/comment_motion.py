"""Comment selection animation checks using disposable viewer fixtures."""
from tests.viewer_acceptance import PDF, SELECT, viewport


def run_comment_motion(cdp, session):
    def ev(script): return cdp.evaluate(session, script)
    viewport(cdp, session, 1440, 900)
    ev(PDF+'.currentScale=1')
    cdp.wait(session, PDF+'.getPageView(0).textLayer?.div?.querySelector("span")!=null')
    ev(SELECT)
    ev("""(async()=>{
      const w=document.querySelector('iframe').contentWindow;
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const c=JSON.parse(document.querySelector('#anchor-config').textContent);
      const anchor=captureTextSelection(w,w.PDFViewerApplication);
      for(let i=0;i<4;i++)await createThread(c.threadsUrl,anchor,'Motion fixture '+i+' '+ 'A longer comment to push neighboring cards. '.repeat(8));
      w.getSelection().removeAllRanges();
    })()""")
    cdp.wait(session, "document.querySelectorAll('#thread-list .thread-card').length===4")
    result=ev("""(async()=>{
      const pause=()=>new Promise(r=>setTimeout(r,250));await pause();
      const app=document.querySelector('iframe').contentWindow.PDFViewerApplication;
      const trace=[],rebases=[];const original=Element.prototype.animate;
      const {CommentRail}=await import('/static/review/viewer_shell.js');
      const nativeMotion=CommentRail.prototype.animateComments;let rail;
      CommentRail.prototype.animateComments=function(...args){rail=this;return nativeMotion.apply(this,args);};
      Element.prototype.animate=function(frames,options){
        if(this.matches('.thread-card'))trace.push({id:this.dataset.threadId,frames,options});
        return original.call(this,frames,options);
      };
      const rebase=e=>rebases.push({dx:e.dx,dy:e.dy,synced:!!rail&&
        [...rail.commentPositions.values()].every(p=>Math.abs(p.top-parseFloat(p.node.style.top))<.01)});
      app.eventBus.on('documentoriginchanged',rebase);
      const runs=[];
      const id=[...document.querySelectorAll('#thread-list .thread-card')].sort((a,b)=>b.offsetTop-a.offsetTop)[0].dataset.threadId;
      try{for(let i=0;i<3;i++){
        trace.length=0;rebases.length=0;
        const before={scroll:app.pdfViewer.container.scrollTop,origin:app.reviewStage.originY,
          positions:[...document.querySelectorAll('#thread-list .thread-card')].map(n=>({id:n.dataset.threadId,top:n.offsetTop}))};
        [...document.querySelectorAll('#thread-list .thread-card')].find(n=>n.dataset.threadId===id).click();await pause();
        runs.push({trace:[...trace],rebases:[...rebases],origin:app.reviewStage.originY,
          before,scroll:app.pdfViewer.container.scrollTop,
          positions:[...document.querySelectorAll('#thread-list .thread-card')].map(n=>({id:n.dataset.threadId,top:n.offsetTop}))});
        document.querySelector('.thread-card.active .thread-card-header button').click();await pause();
      }}finally{
        Element.prototype.animate=original;CommentRail.prototype.animateComments=nativeMotion;
        app.eventBus.off('documentoriginchanged',rebase);
      }
      return runs;
    })()""")
    assert result[0]['rebases'], 'Tall stack must exercise the first-selection origin rebase'
    baseline={t['id']:float(t['frames'][0]['translate'].split()[1][:-2]) for t in result[0]['trace']}
    assert len(baseline)==4, result
    for run in result:
        assert all(r['synced'] for r in run['rebases']), run
        # A coordinate rebase moves the document and camera together.
        assert abs((run['scroll']-run['origin'])-(run['before']['scroll']-run['before']['origin']))<.01, run
        for trace in run['trace']:
            assert trace['options']==dict(duration=160,easing='ease-out'), trace
            assert trace['frames'][0]['opacity']==trace['frames'][1]['opacity']==1, trace
            delta=float(trace['frames'][0]['translate'].split()[1][:-2])
            assert abs(delta-baseline[trace['id']])<2, trace
    print('PASS first/repeated comment selection uses the same slide, rebased animation snapshots stay synchronized, PDF stays visually stationary',flush=True)
