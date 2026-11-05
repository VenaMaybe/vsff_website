// Derived metadata only: never cache PDF bytes, extracted text or reading history.
const stores=new WeakMap();
const CACHE_SCHEMA=2,MAX_VERSIONS=12;
let databasePromise;
const yieldTask=()=>new Promise(resolve=>setTimeout(resolve,0));
const wordSegmenter=typeof Intl.Segmenter==='function'?new Intl.Segmenter(undefined,{granularity:'word'}):null;
function database() {
  if(!globalThis.indexedDB)return Promise.resolve(null);
  return databasePromise??=(new Promise(resolve=>{
    const request=indexedDB.open('pdf-review-page-properties',2);
    request.onupgradeneeded=()=>{
      const db=request.result,store=db.objectStoreNames.contains('versions')?request.transaction.objectStore('versions'):db.createObjectStore('versions',{keyPath:'key'});
      if(!store.indexNames.contains('updated'))store.createIndex('updated','updated');
    };
    request.onsuccess=()=>{request.result.onversionchange=()=>request.result.close();resolve(request.result);};request.onerror=()=>resolve(null);request.onblocked=()=>resolve(null);
  }));
}
async function readCache(key) {
  try {const db=await database();if(!db)return null;return await new Promise(resolve=>{
    const r=db.transaction('versions').objectStore('versions').get(key);r.onsuccess=()=>resolve(r.result);r.onerror=()=>resolve(null);
  });}catch{return null;}
}
async function writeCache(key,rows) {
  try {const db=await database();if(!db)return;await new Promise(resolve=>{
    const tx=db.transaction('versions','readwrite'),store=tx.objectStore('versions');
    store.put({key,rows,updated:Date.now()});
    // Evict by timestamp/key, without cloning every cached document's rows.
    let seen=0;const request=store.index('updated').openKeyCursor(null,'prev');
    request.onsuccess=()=>{
      const cursor=request.result;if(!cursor)return;
      if(++seen>MAX_VERSIONS)store.delete(cursor.primaryKey);cursor.continue();
    };
    tx.oncomplete=resolve;tx.onabort=resolve;tx.onerror=resolve;
  });}catch{/* Storage/quota failures do not prevent inspection. */}
}
export async function textMetadata(content,view=null) {
  const items=content.items.filter(i=>typeof i.str==='string'),text=items.map(i=>i.str).join(' ');
  const segments=wordSegmenter?wordSegmenter.segment(text):text.matchAll(/\S+/gu);
  let words=0,processed=0,started=performance.now(),item=0,offset=0;
  const positions=new Map();
  // Count lazily instead of materializing every segment + a second filtered array.
  for(const segment of segments){
    if(!wordSegmenter||segment.isWordLike){
      words++;
      if(view){
        while(item<items.length-1&&segment.index>=offset+items[item].str.length+1)offset+=items[item++].str.length+1;
        const run=items[item],at=Math.max(0,Math.min(.999999,(view[3]-(run.transform[5]+Math.abs(run.height||0)/2))/(view[3]-view[1])));
        const key=Math.round(at*1e6)/1e6;positions.set(key,(positions.get(key)||0)+1);
      }
    }
    if(++processed%256===0&&performance.now()-started>=8){await yieldTask();started=performance.now();}
  }
  return {words,wordRuns:[...positions].sort((a,b)=>a[0]-b[0])};
}
export async function countWords(content){return (await textMetadata(content)).words;}
// PDF has drawing operators, not SVG objects. An outer tagged Figure is one
// logical illustration, even when made from many paths, forms or raster tiles.
export function artworkMetadata(list,ops,view) {
  if(!ops||!list||list.fnArray.length!==list.argsArray.length)return null;
  const runs=[],marks=[],stack=[];let matrix=[1,0,0,1,0,0],figure=null;
  const multiply=(a,b)=>[a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3],a[0]*b[4]+a[2]*b[5]+a[4],a[1]*b[4]+a[3]*b[5]+a[5]];
  const bounds=(box,transform=matrix)=>{
    const points=[[box[0],box[1]],[box[2],box[1]],[box[0],box[3]],[box[2],box[3]]].map(([x,y])=>[transform[0]*x+transform[2]*y+transform[4],transform[1]*x+transform[3]*y+transform[5]]);
    return [Math.min(...points.map(p=>p[1])),Math.max(...points.map(p=>p[1]))];
  };
  const record=(box,count=1,transform=matrix)=>{
    const ys=bounds(box,transform);
    if(figure){figure.painted=true;figure.low=Math.min(figure.low,ys[0]);figure.high=Math.max(figure.high,ys[1]);return;}
    const at=Math.max(0,Math.min(.999999,(view[3]-(ys[0]+ys[1])/2)/(view[3]-view[1])));runs.push([at,count]);
  };
  const paints=new Set(['stroke','closeStroke','fill','eoFill','fillStroke','eoFillStroke','closeFillStroke','closeEOFillStroke'].map(name=>ops[name]).filter(n=>n!==undefined));
  for(let i=0;i<list.fnArray.length;i++){
    const op=list.fnArray[i],args=list.argsArray[i];
    if(op===ops.save||op===ops.paintFormXObjectBegin||op===ops.beginGroup){
      stack.push(matrix);
      // Transparency group matrices affect clipping; PDF.js restores the original
      // user transform for the group's child operators. Forms apply their matrix.
      const transform=op===ops.paintFormXObjectBegin?args[0]:null;
      if(transform)matrix=multiply(matrix,transform);
    }else if(op===ops.restore||op===ops.paintFormXObjectEnd||op===ops.endGroup){matrix=stack.pop()||[1,0,0,1,0,0];}
    else if(op===ops.transform)matrix=multiply(matrix,args);
    else if(op===ops.beginMarkedContent||op===ops.beginMarkedContentProps){
      const mark={tag:args[0]};marks.push(mark);
      if(mark.tag==='Figure'&&!figure){figure=mark;Object.assign(figure,{painted:false,low:Infinity,high:-Infinity});}
    }else if(op===ops.endMarkedContent){
      if(marks.pop()===figure){
        const finished=figure;figure=null;
        if(finished.painted){const at=Math.max(0,Math.min(.999999,(view[3]-(finished.low+finished.high)/2)/(view[3]-view[1])));runs.push([at,1]);}
      }
    }else if(op===ops.constructPath&&figure&&paints.has(args[0])){
      if(!args[2]||args[2].length!==4)return null;record(args[2]);
    }else if(op===ops.paintImageXObject||op===ops.paintInlineImageXObject||op===ops.paintImageMaskXObject||op===ops.paintSolidColorImageMask){record([0,0,1,1]);}
    else if(op===ops.paintImageXObjectRepeat||op===ops.paintImageMaskXObjectRepeat){
      const positions=args.at(-1);if(!positions||positions.length%2)return null;
      for(let n=0;n<positions.length;n+=2){
        const local=op===ops.paintImageXObjectRepeat?[args[1],0,0,args[2],positions[n],positions[n+1]]:[...args.slice(1,5),positions[n],positions[n+1]];
        record([0,0,1,1],1,multiply(matrix,local));
      }
    }else if(op===ops.paintInlineImageXObjectGroup||op===ops.paintImageMaskXObjectGroup){
      const group=op===ops.paintInlineImageXObjectGroup?args[1]:args[0];if(!Array.isArray(group))return null;
      for(const entry of group){if(!entry.transform)return null;record([0,0,1,1],1,multiply(matrix,entry.transform));}
    }else if(op===ops.setFillColorN||op===ops.setStrokeColorN){return null;}
  }
  if(figure||marks.length)return null;
  return {images:runs.reduce((n,r)=>n+r[1],0),imageRuns:runs};
}
export function pagePropertiesFor(pdf,config,ops) {
  if(!stores.has(pdf))stores.set(pdf,new PageProperties(pdf,config,ops));
  const store=stores.get(pdf);if(ops)store.ops=ops;return store;
}
export class PageProperties extends EventTarget {
  constructor(pdf,config,ops) {
    super();Object.assign(this,{pdf,ops});
    this.key=`${CACHE_SCHEMA}:${config.currentUserId}:${config.versionId}:${pdf.fingerprints?.[0]||''}:${pdf.numPages}`;
    this.rows=Array.from({length:pdf.numPages},(_,i)=>({page:i+1,words:null,area:null,images:null,wordRuns:[],imageRuns:[],textDone:false,imagesDone:false}));
    this.pending=new Map();this.scans=new Map();this.cacheHits=0;this.revision=0;
    this.ready=readCache(this.key).then(record=>{
      if(!Array.isArray(record?.rows)||record.rows.length!==pdf.numPages)return;
      record.rows.forEach((row,i)=>{
        if(row.page!==i+1)return;
        const integer=v=>Number.isInteger(v)&&v>=0&&v<=10000000;
        const words=integer(row.words)?row.words:null,images=integer(row.images)?row.images:null;
        const area=Number.isFinite(row.area)&&row.area>0?row.area:null;
        const validRuns=(runs,total)=>Array.isArray(runs)&&runs.every(r=>Array.isArray(r)&&r.length===2&&Number.isFinite(r[0])&&r[0]>=0&&r[0]<1&&integer(r[1]))&&runs.reduce((n,r)=>n+r[1],0)===total;
        const wordRuns=validRuns(row.wordRuns,words)?row.wordRuns:[],imageRuns=validRuns(row.imageRuns,images)?row.imageRuns:[];
        this.rows[i]={page:i+1,words,images,area,wordRuns,imageRuns,textDone:words!==null&&area!==null&&validRuns(wordRuns,words),imagesDone:images!==null&&validRuns(imageRuns,images)};
        if(words!==null)this.cacheHits++;
      });
      this.revision++;
    }).catch(()=>{});
  }
  async page(number,kind='text') {
    await this.ready;
    const row=this.rows[number-1];if(!row)return null;
    if(row[kind+'Done'])return row;
    const key=`${kind}:${number}`;
    if(this.pending.has(key))return this.pending.get(key);
    const pending=(async()=>{
      try {
        const page=await this.pdf.getPage(number);
        if(kind==='text') {
          const content=await page.getTextContent();Object.assign(row,await textMetadata(content,page.view));
          // CropBox/view is the visible, usable area. Honor PDF UserUnit and rotation.
          const viewport=page.getViewport({scale:1});row.area=viewport.width*viewport.height*(2.54/72)**2;
          if(!Number.isFinite(row.area)||row.area<=0)row.area=null;
        } else if(!page.isPureXfa) {
          const list=await page.getOperatorList({intent:'display',annotationMode:0});
          const metadata=artworkMetadata(list,this.ops,page.view);if(metadata)Object.assign(row,metadata);
        }
      } catch { /* Unknown stays null; it must never become an invented zero. */ }
      row[kind+'Done']=true;this.revision++;this.dispatchEvent(new Event('change'));return row;
    })();
    this.pending.set(key,pending);return pending;
  }
  async wordCount(number) {return (await this.page(number))?.words??null;}
  scan(kind='text') {
    if(this.scans.has(kind))return this.scans.get(kind);
    const promise=(async()=>{
      await this.ready;let cursor=0;
      await Promise.all(Array.from({length:2},async()=>{
        while(cursor<this.rows.length) {
          const number=++cursor;if(this.rows[number-1][kind+'Done'])continue;
          await this.page(number,kind);
          // Yield between pages, keeping text selection/zoom/control input responsive.
          await new Promise(resolve=>setTimeout(resolve,0));
        }
      }));
      await writeCache(this.key,this.rows.map(row=>({...row})));
      return this.rows;
    })();
    this.scans.set(kind,promise);return promise;
  }
}
