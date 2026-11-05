"""Centered insertion pushes each side only as needed, with a page-one limit."""
import time
from tests.viewer_acceptance import viewport


def run_left_card_insertion(cdp,session):
    ev=lambda script:cdp.evaluate(session,script)
    wait=lambda script:cdp.wait(session,script)
    viewport(cdp,session,1600,1000)
    result=ev("""(async()=>{
      const {packCardSequence:pack,insertionSlot}=await import('/static/review/card_packing.js');
      const items=[{card:'a',preferredTop:100,height:100},{card:'b',preferredTop:260,height:100},
        {card:'c',preferredTop:480,height:80},{card:'d',preferredTop:600,height:100},{card:'new',preferredTop:300,height:240}];
      const asymmetric=pack(items,'new',0,8);
      const spill=pack([{card:'a',preferredTop:20,height:60},{card:'b',preferredTop:100,height:60},
        {card:'c',preferredTop:450,height:80},{card:'new',preferredTop:120,height:200}],'new',0,8);
      const tall=[{card:'a',top:-1500,height:1700},{card:'b',top:208,height:400},{card:'c',top:616,height:400}];
      const slot=insertionSlot(tall,730);
      const shrunk=tall.map(x=>({card:x.card,preferredTop:x.top,height:x.card==='c'?100:x.height}));
      shrunk.push({card:'new',preferredTop:610,height:240});
      const stable=pack(shrunk,'new',-2000,8,slot);
      const nearEnd=insertionSlot([{card:'a',top:-500,height:510},{card:'b',top:13,height:465},{card:'c',top:481,height:470}],730);
      return {asymmetric:asymmetric.map(x=>[x.card,x.top]),spill:spill.map(x=>[x.card,x.top]),stable:stable.map(x=>x.card),nearEnd};
    })()""")
    assert result['asymmetric']==[['a',84],['b',192],['new',300],['c',548],['d',636]],result
    assert result['spill']==[['a',20],['new',120],['b',328],['c',450]],result
    assert result['stable']==['a','b','new','c'],result
    assert result['nearEnd']=={'above':['a','b'],'below':['c']},result
    for zoom in [1,.5]:
      for new_height in [360,600,1400]:
        ev(f"document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer.currentScale={zoom}")
        ev(f"window.insertionZoom={zoom}")
        ev("""(async()=>{
          const {LeftCard}=await import('/static/review/left_card.js');
          const frame=document.querySelector('iframe'),application=frame.contentWindow.PDFViewerApplication;
          application.pdfViewer.container.scrollTop=0;
          const viewer={sectionViewer:{frame,application}};
          const cards=[120,150,110,130].map((height,i)=>{
            const card=new LeftCard('Neighbor '+i,{viewer});card.element.style.minHeight=height/insertionZoom+'px';
            card.open({focus:false});card.openingCentered=false;return card;
          });
          cards[0].closeButton.focus({preventScroll:true});cards[0].activate();
          const parent=cards[0].element.parentElement.getBoundingClientRect();
          cards.forEach((card,i)=>card.captureAnchor(parent.top+[80,240,500,650][i]));cards[0].schedule();
          window.insertionFixture={cards,viewer,LeftCard};
        })()""")
        time.sleep(.3)
        before=ev("insertionFixture.cards.map(c=>c.element.getBoundingClientRect().top)")
        ev("""(()=>{
          const {viewer,LeftCard}=insertionFixture,large=new LeftCard('New fixture',{viewer});
          large.element.style.minHeight=80/insertionZoom+'px';large.open({focus:false});large.contentReady();
          insertionFixture.large=large;
        })()""")
        time.sleep(.25)
        # Simulate a tool growing after its asynchronous content arrives.
        ev(f"insertionFixture.large.element.style.minHeight={new_height}/insertionZoom+'px'")
        time.sleep(.3)
        wait("[...insertionFixture.cards,insertionFixture.large].every(c=>c.element.getAnimations().length===0)")
        result=ev("""(()=>{
          const {cards,large,viewer}=insertionFixture,parent=large.element.parentElement;
          const rect=c=>{const r=c.element.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:r.height};};
          const first=viewer.sectionViewer.frame.getBoundingClientRect().top+viewer.sectionViewer.application.pdfViewer.getPageView(0).div.getBoundingClientRect().top;
          return {cards:cards.map(rect),large:rect(large),center:parent.getBoundingClientRect().top+parent.clientHeight/2,
            first,viewportTop:parent.getBoundingClientRect().top,viewportHeight:parent.clientHeight,
            focus:cards[0].element.classList.contains('active'),newFocused:large.element.classList.contains('active')};
        })()""")
        assert result['focus'] and not result['newFocused'],result
        wanted=max(result['first'],result['viewportTop']+max(8,(result['viewportHeight']-result['large']['height'])/2))
        assert abs(result['large']['top']-wanted)<1.5,result
        ordered=sorted([result['large'],*result['cards']],key=lambda r:r['top'])
        assert ordered[0]['top']>=result['first']-1,result
        assert all(ordered[i]['top']>=ordered[i-1]['bottom']+8*zoom-1 for i in range(1,len(ordered))),result
        if new_height==360:
          assert result['cards'][0]['top']<before[0]-10 and result['cards'][1]['top']<before[1]-10,result
          assert result['cards'][2]['top']>before[2]+10 and result['cards'][3]['top']>before[3]+10,result
        if new_height==600:
          assert result['cards'][0]['bottom']<result['large']['top'] and result['cards'][1]['top']>result['large']['bottom'],result
        if new_height==1400:
          assert all(c['top']>result['large']['bottom'] for c in result['cards']),result
          ev("insertionFixture.viewer.sectionViewer.application.pdfViewer.container.scrollTop+=50")
          time.sleep(.25)
          after=ev("insertionFixture.large.element.getBoundingClientRect().top")
          assert abs(after-result['large']['top']+50)<2,(result,after)
        ev("insertionFixture.large.close(false);insertionFixture.cards.forEach(c=>c.close(false));delete window.insertionFixture")
    print('PASS midpoint insertion, asymmetric up/down chains, page-one spill, asynchronous growth, focus retention at 100% and 50%',flush=True)


def run_tall_stack(cdp,session):
    ev=lambda script:cdp.evaluate(session,script)
    wait=lambda script:cdp.wait(session,script)
    viewport(cdp,session,1200,1500)
    ev("""(async()=>{
      const {LeftCard}=await import('/static/review/left_card.js');
      const frame=document.querySelector('iframe'),application=frame.contentWindow.PDFViewerApplication;
      application.pdfViewer.currentScale=.3;
      const viewer={sectionViewer:{frame,application}};
      const cards=[510,465,470].map((height,i)=>{
        const c=new LeftCard('Tall stack '+i,{viewer});c.element.style.minHeight=height/.3+'px';c.open({focus:false});c.openingCentered=false;return c;
      });
      cards[0].closeButton.focus({preventScroll:true});cards[0].activate();
      const parent=cards[0].element.parentElement.getBoundingClientRect();
      cards.forEach((c,i)=>c.captureAnchor(parent.top+[1,514,982][i]));cards[0].schedule();
      window.tallStack={cards};
      cards[2].element.animate([{translate:'0 -35px'},{translate:'0 -35px'}],{duration:2000});
      const fetch=window.fetch;window.fetch=async(...args)=>{if(String(args[0]).endsWith('/review-settings'))await new Promise(r=>setTimeout(r,180));return fetch(...args);};
    })()""")
    time.sleep(.35)
    ev("document.querySelector('#review-tools-menu [data-left-card=settings]').click()")
    wait("document.querySelector('.settings-panel form')!==null")
    time.sleep(.6)
    result=ev("""(()=>{
      const r=document.querySelector('.settings-panel').getBoundingClientRect();
      return {after:tallStack.cards.map(c=>({top:c.element.getBoundingClientRect().top,height:c.height})),settings:{top:r.top,height:r.height},animating:tallStack.cards.some(c=>c.element.getAnimations().length>0)};
    })()""")
    assert any(r['top']>result['settings']['top']+result['settings']['height'] for r in result['after']),result
    assert any(r['top']+r['height']<result['settings']['top'] for r in result['after']),result
    assert not result['animating'],result
    print('PASS real delayed Settings splits three tall cards and cancels prior movement',flush=True)
