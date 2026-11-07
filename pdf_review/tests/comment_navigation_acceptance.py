"""Comment cycling with native keys, real highlights, and Account help layout."""
import json
import time
from tests.viewer_acceptance import PDF, SELECT, viewport, screenshot


def run_comment_navigation(cdp,a,b,fixture,base):
    ev=lambda script:cdp.evaluate(a,script)
    wait=lambda script:cdp.wait(a,script)
    viewport(cdp,a,1280,900)
    wait(PDF+'.getPageView(0).textLayer?.div?.querySelector("span")!=null')
    ev(SELECT)
    ids=ev("""(async()=>{
      const w=document.querySelector('iframe').contentWindow,c=JSON.parse(document.querySelector('#anchor-config').textContent);
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const base=captureTextSelection(w,w.PDFViewerApplication),ids=[];
      for(const y of [650,400,150]){
        const anchor=structuredClone(base);anchor.segments[0].rectangles=[[60,y,230,y+16]];
        ids.push((await createThread(c.threadsUrl,anchor,`Navigation fixture ${y}`)).thread_id);
      }
      w.getSelection().removeAllRanges();return ids;
    })()""")
    ev(PDF+'.currentPageNumber=2')
    wait(PDF+'.getPageView(1).textLayer?.div?.querySelector("span")!=null')
    ev(SELECT.replace('currentPageNumber=1','currentPageNumber=2').replace('getPageView(0)','getPageView(1)'))
    ids.append(ev("""(async()=>{
      const w=document.querySelector('iframe').contentWindow,c=JSON.parse(document.querySelector('#anchor-config').textContent);
      const {captureTextSelection}=await import('/static/review/anchor_selection.js');
      const {createThread}=await import('/static/review/thread_api.js');
      const id=(await createThread(c.threadsUrl,captureTextSelection(w,w.PDFViewerApplication),'Navigation second page')).thread_id;
      w.getSelection().removeAllRanges();return id;
    })()"""))
    wait("document.querySelectorAll('.thread-card').length===4")

    def active():return ev("document.querySelector('.thread-card.active')?.dataset.threadId")
    def focus_pdf():ev("document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer.container.focus({preventScroll:true})")
    def highlight(id):return "[...document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight')].find(e=>e.dataset.threadId==="+json.dumps(id)+")"
    def settle(id):
        wait("document.querySelector('.thread-card.active')?.dataset.threadId==="+json.dumps(id))
        wait("(()=>{const e="+highlight(id)+";if(!e)return false;const r=e.getBoundingClientRect(),s=document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer.container.getBoundingClientRect();return r.bottom>s.top&&r.top<s.bottom&&r.right>s.left&&r.left<s.right;})()")
        time.sleep(.08)
    def key(name,expected=None):
        code={'ArrowUp':38,'ArrowDown':40,'ArrowLeft':37,'ArrowRight':39}[name]
        for kind in ['keyDown','keyUp']:cdp.call('Input.dispatchKeyEvent',dict(type=kind,key=name,code=name,windowsVirtualKeyCode=code,modifiers=8),a)
        if expected:settle(expected)

    # First activation chooses the center-nearest target, then document order.
    ev(PDF+'.currentScale=1;'+PDF+'.currentPageNumber=1')
    time.sleep(.25)
    ev(highlight(ids[1])+".scrollIntoView({block:'center'})")
    focus_pdf();key('ArrowDown',ids[1]);key('ArrowDown',ids[2]);key('ArrowRight',ids[3])
    key('ArrowRight',ids[0]);key('ArrowUp',ids[3]);key('ArrowLeft',ids[2])

    # Continue from the last clicked highlight even after ordinary deselection.
    ev(PDF+'.currentScale=.5;'+PDF+'.currentPageNumber=1;'+PDF+'.container.scrollTop=0')
    time.sleep(.25)
    ev(highlight(ids[0])+".click();document.querySelector('.viewer-title').click()")
    focus_pdf();key('ArrowRight',ids[1])
    # Manual scrolling away from that target reseeds instead of advancing it.
    ev(PDF+'.currentScale=1;'+PDF+'.currentPageNumber=2')
    time.sleep(.25)
    ev(highlight(ids[3])+".scrollIntoView({block:'center'})")
    focus_pdf();key('ArrowUp',ids[3])

    # Native text editing and selection must keep Shift+Arrow functionality.
    ev("(()=>{const input=document.createElement('textarea');input.id='navigation-edit-fixture';input.value='selection test';input.style.cssText='position:fixed;top:60px;left:10px';document.body.append(input);input.focus();input.setSelectionRange(2,2);})()")
    key('ArrowRight')
    assert active()==ids[3]
    assert ev("document.querySelector('#navigation-edit-fixture').selectionEnd===3")
    ev("document.querySelector('#navigation-edit-fixture').remove()")
    ev(SELECT)
    focus_pdf();key('ArrowRight')
    assert active()==ids[3]
    ev("document.querySelector('iframe').contentWindow.getSelection().removeAllRanges()")

    # Repeated keys cannot let an earlier asynchronous reveal jump back later.
    ev(PDF+'.currentScale=.5;'+PDF+'.currentPageNumber=1')
    time.sleep(.25)
    ev(highlight(ids[0])+".click()")
    ev("(()=>{const w=document.querySelector('iframe').contentWindow;for(let i=0;i<4;i++)w.document.body.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowDown',shiftKey:true,bubbles:true,cancelable:true}));})()")
    settle(ids[0])

    # Scope/status filtering is honored; resolved comments don't reappear.
    ev("""(async()=>{
      const c=JSON.parse(document.querySelector('#anchor-config').textContent),{jsonRequest}=await import('/static/review/thread_api.js');
      await jsonRequest(c.resolveUrlTemplate.replace('__THREAD_ID__',THREAD_VALUE),{method:'POST'});
    })()""".replace('THREAD_VALUE',json.dumps(ids[3])))
    wait("![...document.querySelectorAll('.thread-card')].some(e=>e.dataset.threadId==="+json.dumps(ids[3])+")")
    ev(highlight(ids[2])+".click()")
    focus_pdf();key('ArrowDown',ids[0])

    # Geometry edge cases without drawing fake overlays or registering listeners.
    result=ev("""(async()=>{
      const {CommentNavigation}=await import('/static/review/comment_navigation.js');
      const thread=(id,page,offset,rect)=>({thread_id:id,status:'open',targets:[{anchor:{segments:[{page_number:page,text_start:offset,rectangles:[rect]}]}}]});
      const first=thread('center',1,0,[440,390,460,410]),multi=thread('multi',1,1,[0,0,20,20]),last=thread('last',3,0,[500,450,520,470]);
      multi.targets[0].anchor.segments.push({page_number:2,rectangles:[[320,320,340,340]]});
      const state={threads:[first,multi,last],filter:'all',visibleThreads(){return this.threads.filter(t=>this.filter==='all'||t.status==='open');}};
      const div={isConnected:true,clientLeft:0,clientTop:0,clientWidth:600,clientHeight:800,getBoundingClientRect:()=>({left:-300,top:-300})};
      const nav=Object.assign(Object.create(CommentNavigation.prototype),{state,frame:{contentWindow:{innerWidth:300,innerHeight:200}},application:{pdfViewer:{
        container:{clientLeft:0,clientTop:0,clientWidth:300,clientHeight:200,getBoundingClientRect:()=>({left:0,top:0})},
        getPageView:()=>({div,viewport:{width:600,height:800,convertToViewportPoint:(x,y)=>[x,y]}})}}});
      const initial=nav.next(1).thread.thread_id;nav.remember('multi');
      const continuation=nav.next(1).thread.thread_id;
      multi.targets[0].anchor.segments[1].rectangles=[[20,390,40,410]];
      const horizontal=nav.next(1).thread.thread_id;
      first.status='resolved';state.filter='open';const filtered=nav.next(1).thread.thread_id;
      state.threads=[];return {initial,continuation,horizontal,filtered,empty:nav.next(1)};
    })()""")
    assert result==dict(initial='center',continuation='last',horizontal='center',filtered='last',empty=None),result

    cdp.call('Page.navigate',{'url':base+'/account'},a)
    wait("document.readyState==='complete'&&document.querySelector('.keyboard-help li')!=null")
    assert ev("document.querySelectorAll('.keyboard-help li').length>=20")
    assert ev("(()=>{const p=document.querySelector('.account-overview > div').getBoundingClientRect(),h=document.querySelector('.keyboard-help').getBoundingClientRect();return h.left>p.right&&Math.abs(h.top-p.top)<2;})()")
    screenshot(cdp,a,'account-keyboard-help')
    viewport(cdp,a,390,844)
    assert ev("document.documentElement.scrollWidth<=innerWidth")
    screenshot(cdp,a,'account-keyboard-help-mobile')
    print('PASS center-nearest navigation, last click, wrap/all arrows, native editing/selection, rapid keys, filtering, multi-page/horizontal visibility and responsive shortcut help',flush=True)
