"""Guard against detached analytics page-list retries starving the event loop."""
def check_detached_pages(ev):
    result=ev("""(async()=>{
      const {ReadingCards}=await import('/static/review/reading_cards.js');
      const method=ReadingCards.prototype.paintPages;
      const run=async(closeDuringExtraction)=>{
        const element=document.createElement('section'),views=document.createElement('div'),group=document.createElement('details'),body=document.createElement('div');
        group.className='reading-page-group';group.dataset.sectionId='chapter';group.open=true;
        body.className='reading-pages';group.append(body);views.append(group);element.append(views);
        const section={section_id:'chapter',start_page:1,end_page:3};let calls=0,wordCalls=0,release;
        const gate=new Promise(resolve=>{release=resolve;});
        const data={pages:Array.from({length:3},(_,i)=>({page_number:i+1,word_count:closeDuringExtraction?null:10})),stale:false};
        const harness={selected:'reader',analytics:{element},sectionViews:views,windows:new Map([['reader:chapter',data]]),
          tracker:{policy:{words_per_minute:400,minimum_page_seconds:5},wordCount:async()=>{wordCalls++;await gate;return 10;}}};
        harness.paintPages=(...args)=>{
          // A regression fails finitely instead of freezing the test browser.
          if(++calls>8)return;
          return method.call(harness,...args);
        };
        if(closeDuringExtraction)document.body.append(element);
        const pending=harness.paintPages(body,section);element.remove();release();await pending;
        await new Promise(resolve=>setTimeout(resolve,0));
        return {calls,wordCalls,painted:body.childElementCount};
      };
      return {closed:await run(false),closedWhileExtracting:await run(true)};
    })()""")
    assert result['closed']==dict(calls=1,wordCalls=0,painted=0),result
    assert result['closedWhileExtracting']['calls']==1 and result['closedWhileExtracting']['painted']==0,result
    print('PASS detached analytics: no retry loop or hidden text extraction, including close during extraction',flush=True)
