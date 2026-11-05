"""Aggregation edge cases in the same JS modules used by the viewer."""
def aggregation_checks(ev):
    result=ev("""(async()=>{
      const {statisticsUnits,commentStatistics,mappedSections}=await import('/static/review/version_statistics.js');
      const {textMetadata,artworkMetadata}=await import('/static/review/page_properties_data.js');
      const check=(condition,message)=>{if(!condition)throw Error(message);};
      const policy={words_per_minute:400,minimum_page_seconds:5};
      const sections=[{id:'a',name:'First',start:0,end:.5},{id:'b',name:'Second',start:.5,end:1.5}];
      const rows=[{page:1,words:10,wordRuns:[[.25,3],[.75,7]],images:2,imageRuns:[[.25,1],[.75,1]]},
        {page:2,words:0,wordRuns:[],images:2,imageRuns:[[.1,1],[.9,1]]}];
      const author={user_id:'alice',display_name:'Alice',review_color:'#4e79a7'},beta={user_id:'beta',display_name:'Beta',review_color:'#f28e2c'};
      const thread={targets:[{anchor:{segments:[{page_number:1,pdf_view_box:[0,0,100,100],rectangles:[[0,70,50,80]]},{page_number:2}]}}],
        comments:[{comment_id:'c1',author},{comment_id:'c2',author:beta},{comment_id:'deleted',author:beta,is_deleted:true}]};
      const comments=commentStatistics([thread,thread],[{section_id:'b',comments:[{comment_id:'s1',author_id:'alice',display_name:'Alice',review_color:'#4e79a7'}]}],sections,2);
      check(comments.records.length===3,'Each message counts once; tombstones excluded');
      const pages=statisticsUnits(rows,sections,'pages',comments,policy),groups=statisticsUnits(rows,sections,'sections',comments,policy);
      check(JSON.stringify(pages.map(p=>p.comments))==='[2,1]','Section feedback attaches to its end page');
      check(JSON.stringify(groups.map(p=>p.words))==='[3,7,0]','Partial-page words use text locations');
      check(JSON.stringify(groups.map(p=>p.images))==='[1,2,1]','Image centers and unsectioned gaps');
      check(JSON.stringify(groups.map(p=>p.comments))==='[2,1,0]','Section thought stays with its own section');
      for(const metric of ['words','images','time','comments'])check(pages.reduce((n,p)=>n+p[metric],0)===groups.reduce((n,p)=>n+p[metric],0),'Totals preserved: '+metric);
      check(groups.every(g=>Number.isInteger(g.time)),'Integer ERT allocation');
      const unknown=statisticsUnits([{...rows[0],images:null}],sections,'sections',{records:[],authors:[]},policy);
      check(unknown[0].images===null&&unknown[1].images===null,'Unknown images never become zero');
      const text=await textMetadata({items:[{str:'one two',transform:[1,0,0,1,0,75],height:0},{str:'three',transform:[1,0,0,1,0,25],height:0}]},[0,0,100,100]);
      check(text.words===3&&JSON.stringify(text.wordRuns)==='[[0.25,2],[0.75,1]]','Word extraction and cached run counts agree');
      check(mappedSections([{section_id:'a',name:'Top',placement:{start_page:1,end_page:1,start_y:null,end_y:50,start_view_box:[0,0,100,100],end_view_box:[0,0,100,100]}}],2)[0].end===.5,'Canonical partial boundary');
      const ops={beginMarkedContent:1,endMarkedContent:2,constructPath:3,fill:4,paintImageXObject:5,beginMarkedContentProps:6,endPath:7,setFillColorN:8};
      const art=artworkMetadata({fnArray:[1,3,2,1,3,1,5,2,3,2,5],argsArray:[['Artifact'],[4,[],[0,0,100,100]],[],['Figure'],[4,[],[10,60,20,80]],['Figure'],[],[],[4,[],[30,60,40,80]],[],[]]},ops,[0,0,100,100]);
      check(art.images===2&&art.imageRuns[0][1]===1,'Nested vector/raster figure counts once; background ignored');
      check(artworkMetadata({fnArray:[8],argsArray:[[]]},ops,[0,0,100,100])===null,'Unsupported patterns remain unavailable');
      return {pages:pages.length,groups:groups.length,comments:comments.records.length,figures:art.images};
    })()""")
    assert result==dict(pages=2,groups=3,comments=3,figures=2),result
