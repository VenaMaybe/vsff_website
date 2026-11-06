"""Real pointer and keyboard focus must adopt collision-displaced card positions."""
import time
from tests.viewer_acceptance import viewport


def run_focus(cdp, session):
    def ev(script): return cdp.evaluate(session, script)
    viewport(cdp, session, 1440, 1000)
    ev("""(async()=>{
      const {LeftCard}=await import('/static/review/left_card.js');
      const frame=document.querySelector('iframe'),application=frame.contentWindow.PDFViewerApplication;
      application.pdfViewer.currentScale=.5;application.pdfViewer.container.scrollTop=0;
      const viewer={sectionViewer:{frame,application}};
      const cards=['First utility','Second utility'].map(title=>{
        const card=new LeftCard(title,{viewer});
        for(let i=0;i<8;i++){const row=document.createElement('div');row.textContent='Setting '+(i+1);card.body.append(row);}
        card.open();card.contentReady();return card;
      });
      window.focusFixture={cards,frame};
    })()""")
    time.sleep(.25)

    def arrange():
        ev("""(()=>{const {cards,frame}=window.focusFixture;
          cards.forEach(c=>c.openingCentered=false);
          cards[0].closeButton.focus({preventScroll:true});cards[0].activate();
          cards.forEach(c=>c.captureAnchor(frame.getBoundingClientRect().top+80));cards[0].schedule();
        })()""")
        time.sleep(.25)
        data=ev("""(()=>{const {cards}=window.focusFixture;return cards.map(c=>({top:c.element.getBoundingClientRect().top,left:c.element.getBoundingClientRect().left,anchor:c.documentTop()+c.element.parentElement.getBoundingClientRect().top}));})()""")
        assert data[1]['top']-data[1]['anchor']>50, data
        return data

    def pointer(kind, x, y, **extra):
        cdp.call('Input.dispatchMouseEvent',dict(type=kind,x=x,y=y,**extra),session)

    # Clicking an inactive neighbor must not restore its preferred pre-packing Y.
    before=arrange();x=before[1]['left']+60;y=before[1]['top']+12
    pointer('mousePressed',x,y,button='left',clickCount=1)
    assert abs(ev('window.focusFixture.cards[1].element.getBoundingClientRect().top')-before[1]['top'])<1
    pointer('mouseReleased',x,y,button='left',clickCount=1)
    time.sleep(.25)
    for i in [0,1]:
        assert abs(ev(f'window.focusFixture.cards[{i}].element.getBoundingClientRect().top')-before[i]['top'])<1

    # Grabbing the header starts from the displayed position, then follows the pointer.
    before=arrange();x=before[1]['left']+60;y=before[1]['top']+12
    pointer('mousePressed',x,y,button='left',clickCount=1)
    pointer('mouseMoved',x,y+55,buttons=1)
    pointer('mouseReleased',x,y+55,button='left',clickCount=1)
    time.sleep(.25)
    assert abs(ev('window.focusFixture.cards[1].element.getBoundingClientRect().top')-before[1]['top']-55)<1

    # Catch a displaced card during an existing motion without applying its offset twice.
    arrange()
    ev("window.focusFixture.cards[1].element.animate([{transform:'translateY(20px)'},{transform:'translateY(20px)'}],{duration:1000})")
    point=ev("(()=>{const r=window.focusFixture.cards[1].element.getBoundingClientRect();return {x:r.left+60,y:r.top+12,top:r.top};})()")
    pointer('mousePressed',point['x'],point['y'],button='left',clickCount=1)
    pointer('mouseReleased',point['x'],point['y'],button='left',clickCount=1)
    time.sleep(.25)
    assert abs(ev('window.focusFixture.cards[1].element.getBoundingClientRect().top')-point['top'])<1

    # Keyboard focus has the same behavior; deliberate section-line centering still moves.
    before=arrange()
    ev('window.focusFixture.cards[1].closeButton.focus({preventScroll:true})')
    time.sleep(.25)
    assert abs(ev('window.focusFixture.cards[1].element.getBoundingClientRect().top')-before[1]['top'])<1
    ev('window.focusFixture.cards[1].centerOn(()=>window.focusFixture.frame.getBoundingClientRect().top+650)')
    time.sleep(.25)
    assert abs(ev('window.focusFixture.cards[1].element.getBoundingClientRect().top')-before[1]['top'])>20
    ev('window.focusFixture.cards.forEach(c=>c.close(false));delete window.focusFixture')
    print('PASS inactive-card click, header grab/drag and keyboard focus adopt displayed anchors; intentional centering remains',flush=True)

    # First open and reopening use one identical entrance; content-ready must
    # not replace it with travel from a CSS/default or previously stored top.
    entrance=ev("""(async()=>{
      const {LeftCard}=await import('/static/review/left_card.js');
      const frame=document.querySelector('iframe'),application=frame.contentWindow.PDFViewerApplication;
      const card=new LeftCard('Entrance fixture',{viewer:{sectionViewer:{frame,application}}});
      card.element.style.minHeight='320px';
      let trace=[];const animate=card.element.animate.bind(card.element);
      card.element.animate=(frames,options)=>{trace.push({frames,options});return animate(frames,options);};
      const pause=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
      card.open({focus:false});card.contentReady();await pause();
      const first=trace;card.close(false);trace=[];
      card.open({focus:false});card.contentReady();await pause();
      const second=trace;card.close(false);
      trace=[];
      card.open({focus:false});card.contentReady();await pause();
      card.setPinned(true);card.body.style.height='500px';
      card.contentReady();card.activate();await pause();
      const pinned=trace;card.close(false);
      return {first,second,pinned};
    })()""")
    assert len(entrance['first'])==1 and entrance['first']==entrance['second'],entrance
    assert entrance['pinned']==entrance['first'],entrance
    assert entrance['first'][0]['frames']==[{'translate':'0 4px','opacity':0},{'translate':'0 0','opacity':1}],entrance
    assert entrance['first'][0]['options']=={'duration':160,'easing':'ease-out'},entrance
    cdp.call('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]},session)
    try:
        assert ev("""(async()=>{
          const {LeftCard}=await import('/static/review/left_card.js');
          const frame=document.querySelector('iframe'),application=frame.contentWindow.PDFViewerApplication;
          const card=new LeftCard('Reduced motion',{viewer:{sectionViewer:{frame,application}}});
          let calls=0;card.element.animate=()=>{calls++;};card.open({focus:false});card.contentReady();card.close(false);return calls;
        })()""")==0
    finally:
        cdp.call('Emulation.setEmulatedMedia',{'features':[]},session)
    print('PASS identical first/reopen 160ms fade and 4px slide, uninterrupted by content-ready; reduced motion respected',flush=True)
