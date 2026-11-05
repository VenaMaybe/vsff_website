"""Focused Page Properties acceptance, with synthetic immutable mixed-size PDFs."""
import math
from tests.viewer_acceptance import viewport, screenshot, PDF


def properties_pdf(label):
    count=138
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
             b'<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Length 3 >>\nstream\n\xff\x00\x00\nendstream']
    pages=[]
    for page in range(1,count+1):
        number=len(objects)+1;pages.append(f'{number} 0 R')
        words=0 if page==137 else int(120+1650*math.exp(-((page-61)/10)**2)+400*math.exp(-((page-107)/15)**2)+(page*37)%180)
        width,height=(792,500) if page%11==0 else (612,792)
        lines=[' '.join(['word']*min(20,words-start)) for start in range(0,words,20)]
        stream=b'BT /F1 6 Tf 7 TL 30 '+str(height-30).encode()+b' Td '+b' '.join(b'('+line.encode()+b') Tj T*' for line in lines)+b' ET'
        if page==5:stream+=b' q 30 0 0 30 200 200 cm /Img Do Q q 30 0 0 30 240 200 cm /Img Do Q'
        # One vector figure with multiple paths, plus an unrelated background.
        if page==6:stream+=b' /Artifact BMC 0 0 612 792 re f EMC /Figure << /MCID 0 >> BDC 100 200 20 20 re f 130 200 20 20 re f EMC'
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Resources << /Font << /F1 3 0 R >> /XObject << /Img 4 0 R >> >> /Contents {number+1} 0 R >>'.encode())
        objects.append(f'<< /Length {len(stream)} >>\nstream\n'.encode()+stream+b'\nendstream')
    objects[1]=f'<< /Type /Pages /Kids [{" ".join(pages)}] /Count {count} >>'.encode()
    data=b'%PDF-1.4\n%'+label.encode()+b'\n';offsets=[0]
    for i,obj in enumerate(objects,1):offsets.append(len(data));data+=f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(data);data+=f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode()
    data+=b''.join(f'{offset:010} 00000 n \n'.encode() for offset in offsets[1:])
    return data+f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


def seed_properties(app,document,version,user):
    from review import sections
    from review.database import transaction
    from review.threads import create_thread,add_comment
    from review import section_feedback
    from tests.test_threads import anchor_payload
    with transaction(app.config['DATABASE']) as c:
        beta=c.execute("SELECT user_id FROM users WHERE display_name='ReviewerBeta'").fetchone()[0]
        for uid,color in [(user['user_id'],'#4e79a7'),(beta,'#f28e2c')]:c.execute('UPDATE users SET review_color=? WHERE user_id=?',(color,uid))
    thread=create_thread(app.config['DATABASE'],version,user['user_id'],anchor_payload(),'First')
    add_comment(app.config['DATABASE'],thread['thread_id'],beta,'Reply by Beta')
    add_comment(app.config['DATABASE'],thread['thread_id'],user['user_id'],'Reply by Alpha')
    for name,start,end in [('Ch. 1',1,28),('Ch. 2',29,56),('Ch. 3',57,96),('Ch. 4',97,129),('Appendix',130,138)]:
        sid=sections.create_section(app.config['DATABASE'],document,user['user_id'],{'name':name})
        sections.save_placement(app.config['DATABASE'],sid,version,user['user_id'],dict(start_page=start,end_page=end,start_y=None,end_y=None,
            start_view_box=[0,0,612,792],end_view_box=[0,0,612,792],page_count=138,expected_revision=0))
        if start==1:
            response=section_feedback.create_response(app.config['DATABASE'],sid,version,user['user_id'],'Section thought')
            section_feedback.reply(app.config['DATABASE'],response,beta,'Section reply')


def run_properties(cdp,a,b,fixture,base):
    ev=lambda script:cdp.evaluate(a,script)
    wait=lambda script:cdp.wait(a,script)
    viewport(cdp,a,1280,1100)
    ev("document.querySelector('[data-left-card=properties]').click()")
    wait("document.querySelectorAll('.properties-bar').length===138&&!document.querySelector('.properties-status').textContent.startsWith('Calculating')")
    # Stable DOM and native left-card lifecycle; no parallel chart implementation.
    ev("window.propertiesChart=document.querySelector('.properties-chart');window.propertiesFirst=document.querySelector('.properties-bar');document.querySelector('.page-properties-card .left-card-pin').click()")
    wait("(()=>{const e=document.querySelector('.page-properties-card');return e.getAnimations().length===0&&e.getBoundingClientRect().top<65;})()")
    assert ev("document.querySelectorAll('.properties-bracket').length===5")
    assert ev("Number(document.querySelector('[data-page=\"137\"]').getAttribute('width'))===1")
    assert ev("parseFloat(document.querySelector('.properties-chart').style.height)>550&&document.querySelector('.properties-chart').getBoundingClientRect().width>230")
    screenshot(cdp,a,'page-properties-words')
    result=ev("""(async()=>{
      const {pagePropertiesFor,PageProperties,artworkMetadata,countWords}=await import('/static/review/page_properties_data.js');
      const app=document.querySelector('iframe').contentWindow.PDFViewerApplication,c=JSON.parse(document.querySelector('#anchor-config').textContent);
      const store=pagePropertiesFor(app.pdfDocument,c);await store.scan();
      const cached=new PageProperties({numPages:138,fingerprints:app.pdfDocument.fingerprints,getPage(){throw Error('cache miss');}},c);
      await cached.scan();
      const ops={paintImageXObject:1,paintInlineImageXObject:2,paintImageMaskXObject:3,paintSolidColorImageMask:4,paintImageXObjectRepeat:5,paintImageMaskXObjectRepeat:6,paintInlineImageXObjectGroup:7,paintImageMaskXObjectGroup:8,setFillColorN:9,setStrokeColorN:10};
      const images=artworkMetadata({fnArray:[1,5,7,3],argsArray:[[],['id',1,1,[0,0,3,3]],[{},Array.from({length:3},()=>({transform:[1,0,0,1,0,0]}))],[]]},ops,[0,0,612,792])?.images??null;
      let yielded=false;setTimeout(()=>{yielded=true;},0);const largeCount=await countWords({items:[{str:'word '.repeat(60000)}]});
      if(largeCount!==60000||!yielded)throw Error('Large word counting did not yield correctly');
      const unknown=artworkMetadata({fnArray:[9],argsArray:[[]]},ops,[0,0,612,792]);
      return {cache:cached.cacheHits,words:cached.rows.every((r,i)=>r.words===store.rows[i].words),images,unknown,blank:store.rows[136].words,mixed:store.rows[0].area!==store.rows[10].area};
    })()""")
    assert result==dict(cache=138,words=True,images=7,unknown=None,blank=0,mixed=True),result
    for metric in ['time','comments','images','words']:
        ev(f"document.querySelector('[data-metric={metric}]').click()")
        wait("!document.querySelector('.properties-status').textContent.startsWith('Calculating')")
        assert ev("document.querySelector('.properties-chart')===propertiesChart&&document.querySelector('.properties-bar')===propertiesFirst")
        if metric=='images':
            assert ev("document.querySelector('.properties-bar[data-page=\"5\"] title').textContent.includes('2 images / figures')")
            assert ev("document.querySelector('.properties-bar[data-page=\"6\"] title').textContent.includes('1 images / figures')")
            screenshot(cdp,a,'page-properties-images')
        if metric=='comments':
            assert ev("document.querySelector('.properties-info strong').textContent==='Total: 5'")
            assert ev("document.querySelector('.properties-bar[data-page=\"1\"] title').textContent.includes('3 comments (ReviewerAlpha: 2, ReviewerBeta: 1)')")
            assert ev("(()=>{const bars=[...document.querySelector('.properties-bar').nextElementSibling.children];return bars.length===2&&bars[0].getAttribute('fill')==='#4e79a7'&&bars[1].getAttribute('fill')==='#f28e2c'&&Math.abs(Number(bars[0].getAttribute('width'))/Number(bars[1].getAttribute('width'))-2)<.001;})()")
            assert ev("""(async()=>{window.commentBar=document.querySelector('.properties-bar');const c=JSON.parse(document.querySelector('#anchor-config').textContent),threads=await (await fetch(`/api/versions/${c.versionId}/threads`)).json();const reply=await fetch(`/api/threads/${threads.threads[0].thread_id}/comments`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name=csrf-token]').content},body:JSON.stringify({body:'Live statistics reply'})});return reply.status===201;})()""")
            wait("document.querySelector('.properties-info strong').textContent==='Total: 6'")
            assert ev("document.querySelector('.properties-bar')===commentBar")
    ev("document.querySelector('[data-page=\"61\"]').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
    wait(PDF+'.currentPageNumber===61')
    assert ev("document.querySelector('[data-page=\"61\"]').dataset.current==='true'")
    ev("document.querySelector('[data-metric=comments]').click();document.querySelector('[data-grouping=sections]').click()")
    assert ev("document.querySelectorAll('.properties-bar').length===5&&document.querySelector('.properties-bar title').textContent.includes('6 comments')")
    assert ev("document.querySelector('.left-card h2').textContent==='Version statistics'&&!document.querySelector('[data-metric=density]')")
    assert ev("document.querySelectorAll('.properties-grid').length>0")
    assert ev("!document.querySelector('.properties-options')")
    screenshot(cdp,a,'version-statistics-section-comments')
    ev("window.propertiesBeforeReload=true")
    cdp.call('Page.reload',{},a)
    wait("!window.propertiesBeforeReload&&document.querySelector('#realtime-status')?.textContent==='Live'")
    wait("document.querySelector('.page-properties-card [data-metric=comments]')?.getAttribute('aria-pressed')==='true'&&document.querySelector('[data-grouping=sections]')?.getAttribute('aria-pressed')==='true'")
    wait("!document.querySelector('.properties-status').textContent.startsWith('Calculating')")
    assert ev("document.querySelectorAll('.properties-grid').length>0&&document.querySelectorAll('.page-properties-card').length===1")
    # No mapped sections is a regular full-width histogram, not an error.
    ev("document.querySelector('[data-close-all-tools]').click()")
    wait("document.querySelectorAll('.left-card').length===0")
    cdp.call('Page.navigate',{'url':base+f"/versions/{fixture['versions'][1]}/view"},a)
    wait(f"location.pathname.includes('{fixture['versions'][1]}')&&document.querySelector('#realtime-status')?.textContent==='Live'")
    ev("document.querySelector('[data-left-card=properties]').click()")
    wait("document.querySelectorAll('.properties-bar').length===138&&!document.querySelector('.properties-status').textContent.startsWith('Calculating')")
    assert ev("document.querySelectorAll('.properties-bracket').length===0")
    ev("document.querySelector('[data-grouping=sections]').click()")
    assert ev("document.querySelectorAll('.properties-bar').length===1&&document.querySelector('.properties-bar title').textContent.startsWith('Unsectioned:')")
    from tests.version_statistics_acceptance import aggregation_checks
    aggregation_checks(ev)
    print('PASS Version statistics: 138 pages, persistent cache, vector figures, proportional author colors, sections, navigation, stable metrics, saved grouping and partial-page aggregation',flush=True)
