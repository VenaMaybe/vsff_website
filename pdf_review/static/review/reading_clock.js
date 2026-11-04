// Monotonic time accounting, independent of DOM, networking, and PDF rendering.
export class ReadingClock {
  constructor() { this.pending=new Map();this.visit=0;this.previous=null; }
  reset() { this.previous=null; }
  clear() { this.reset();this.pending.clear(); }
  sample(now, eligible, pages) {
    const signature=eligible?pages.map(p=>p.page).sort((a,b)=>a-b).join(','):'';
    const old=this.previous,delta=old?now-old.now:0;
    if(signature && (!old?.signature || old.signature!==signature))this.visit++;
    // Never catch up after a throttled/suspended timer or count a navigation
    // interval whose page identity/active state changed between samples.
    if(signature && old?.signature===signature && delta>0 && delta<=2500) {
      const weight=pages.reduce((n,p)=>n+p.weight,0);
      if(weight>0)for(const page of pages) {
        const key=`${this.visit}:${page.page}`;
        const row=this.pending.get(key)||{page:page.page,visit:this.visit,ms:0};
        row.ms+=delta*page.weight/weight;this.pending.set(key,row);
      }
    }
    this.previous={now,signature};
  }
  drain(words) {
    const rows=[...this.pending.values()].filter(p=>p.ms>=1).map(p=>({...p,ms:Math.floor(p.ms),words:words.get(p.page)??null}));
    this.pending.clear();return rows.slice(0,32);
  }
}
