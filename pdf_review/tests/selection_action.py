"""Desktop selection action follows the final selected line, including page breaks."""
import time
from tests.viewer_acceptance import PDF, viewport


def run_selection_action(cdp,session):
    ev=lambda script:cdp.evaluate(session,script)
    wait=lambda script:cdp.wait(session,script)
    viewport(cdp,session,1440,1000)
    ev(PDF+'.currentScale=1')
    wait(PDF+'.getPageView(0).textLayer?.div?.querySelector("span")!==null')
    ev("""(()=>{
      const frame=document.querySelector('iframe'),w=frame.contentWindow,pdf=w.PDFViewerApplication.pdfViewer;
      const add=(page,top,text)=>{
        const span=w.document.createElement('span');span.textContent=text;
        span.style.cssText=`left:100px;top:${top}px;font-size:16px;transform:none;`;
        pdf.getPageView(page-1).textLayer.div.append(span);return span.firstChild;
      };
      window.selectionFixture={w,pdf,first:add(1,100,'A long first selected line with several words'),
        middle:add(1,125,'Another long selected line before the end'),last:add(1,150,'Short ending')};
    })()""")
    for backwards in [False,True]:
        ev(f"""(()=>{{const {{w,first,last}}=selectionFixture;
          const s=w.getSelection();s.setBaseAndExtent({"last,5,first,2" if backwards else "first,2,last,5"});
        }})()""")
        time.sleep(.18)
        wait("!document.querySelector('#comment-selection-button').hidden&&!document.querySelector('#comment-selection-button').disabled")
        result=ev("""(()=>{
          const f=document.querySelector('iframe').getBoundingClientRect(),s=selectionFixture.w.getSelection();
          const rects=[...s.getRangeAt(0).getClientRects()].filter(r=>r.width>0&&r.height>0),end=rects.at(-1);
          const b=document.querySelector('#comment-selection-button').getBoundingClientRect();
          return {x:b.left-f.left-end.right,y:b.top-f.top-end.bottom,union:Math.max(...rects.map(r=>r.right))-end.right};
        })()""")
        assert result['union']>100 and abs(result['x']-4)<2 and abs(result['y']-4)<2,result
    # Changes faster than the 80ms payload debounce still update immediately.
    immediate=ev("""(()=>{
      const {w,first,last}=selectionFixture,checks=[];
      for(const offset of [2,7,4,9]){
        w.getSelection().setBaseAndExtent(first,2,last,offset);
        w.document.dispatchEvent(new w.Event('selectionchange'));
        const f=document.querySelector('iframe').getBoundingClientRect(),button=document.querySelector('#comment-selection-button');
        const r=[...w.getSelection().getRangeAt(0).getClientRects()].filter(r=>r.width>0&&r.height>0).at(-1),b=button.getBoundingClientRect();
        checks.push(!button.hidden&&!button.disabled&&Math.abs(b.left-f.left-r.right-4)<2&&Math.abs(b.top-f.top-r.bottom-4)<2);
      }
      // Clicking before deferred capture finishes must still use the full anchor.
      document.querySelector('#comment-selection-button').click();
      const quote=document.querySelector('#selection-comment-quote').textContent;
      const valid=!document.querySelector('#selection-comment-composer').hidden&&quote.includes('Short end');
      document.querySelector('#cancel-selection-comment').click();
      return {checks,valid};
    })()""")
    assert all(immediate['checks']) and immediate['valid'],immediate
    # Keep the native single-line behavior too.
    ev("(()=>{const {w,last}=selectionFixture;w.getSelection().setBaseAndExtent(last,0,last,5);})()")
    time.sleep(.18)
    assert ev("""(()=>{const f=document.querySelector('iframe').getBoundingClientRect(),r=selectionFixture.w.getSelection().getRangeAt(0).getClientRects()[0],b=document.querySelector('#comment-selection-button').getBoundingClientRect();return Math.abs(b.left-f.left-r.right-4)<2&&Math.abs(b.top-f.top-r.bottom-4)<2;})()""")
    # The final page determines placement for a selection crossing a page boundary.
    ev(PDF+'.currentPageNumber=2')
    wait(PDF+'.getPageView(1).textLayer?.div?.querySelector("span")!==null')
    ev("""(()=>{
      const {w,pdf,first}=selectionFixture,span=w.document.createElement('span');span.textContent='End on page two';
      span.style.cssText='left:100px;top:100px;font-size:16px;transform:none;';pdf.getPageView(1).textLayer.div.append(span);
      w.getSelection().setBaseAndExtent(first,2,span.firstChild,3);
    })()""")
    time.sleep(.2)
    wait("!document.querySelector('#comment-selection-button').hidden")
    assert ev("""(()=>{const f=document.querySelector('iframe').getBoundingClientRect(),r=[...selectionFixture.w.getSelection().getRangeAt(0).getClientRects()].filter(r=>r.width>0&&r.height>0).at(-1),b=document.querySelector('#comment-selection-button').getBoundingClientRect();return Math.abs(b.left-f.left-r.right-4)<2&&Math.abs(b.top-f.top-r.bottom-4)<2;})()""")
    print('PASS selection action at final line for forward/reverse multi-line, single-line and multi-page selections',flush=True)
