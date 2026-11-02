export class ReviewPresence {
  constructor(versionId, container, currentUserId) {
    Object.assign(this, { versionId, container,currentUserId });
    this.rows=[];
    this.page = null;
    this.timer = null;
    this.send = () => {};
  }
  render(event) {
    if (event?.schema_version !== 1 || event.version_id !== this.versionId ||
        !Array.isArray(event.reviewers)) return;
    const rows = event.reviewers.filter((user) => typeof user?.display_name === "string");
    this.rows=rows;
    this.paint();
    document.getElementById("presence-count").textContent = rows.length;
    this.container.textContent = rows.length
      ? rows.map((user) => `${user.display_name}${Number.isInteger(user.page) ? ` · p. ${user.page}` : ""}`).join(", ")
      : "No named reviewers connected";
  }
  clear() { this.rows=[];this.paint();document.getElementById("presence-count").textContent = "0"; this.container.textContent = "Presence unavailable"; }
  paint() {
    if(!this.application)return;
    const pdf=this.application.pdfViewer,doc=pdf.viewer.ownerDocument;
    doc.querySelectorAll('.review-page-presence').forEach(e=>e.remove());
    const pages=new Map();
    for(const user of this.rows.filter(u=>u.user_id!==this.currentUserId))for(const page of (user.pages?.length?user.pages:[user.page]).slice(0,2)){
      if(!Number.isInteger(page))continue;const users=pages.get(page)??[];users.push(user);pages.set(page,users);
    }
    for(const [page,users] of pages){const div=pdf.getPageView(page-1)?.div;if(!div)continue;
      for(const [i,user] of users.slice(0,3).entries()){
        const layer=doc.createElement('div');layer.className='review-page-presence';layer.dataset.userId=user.user_id;
        layer.style.setProperty('--presence-inset',`${i+1}px`);layer.style.setProperty('--presence-color',/^#[0-9a-f]{6}$/.test(user.review_color)?user.review_color:'#659a54');
        const avatar=doc.createElement('span');avatar.className='review-presence-avatar';avatar.textContent=user.display_name.split(/\s+/).map(n=>n[0]).slice(0,2).join('').toUpperCase();
        avatar.style.setProperty('--avatar-right',`${4+i*20}px`);avatar.title=user.display_name;avatar.setAttribute('aria-label',`${user.display_name} viewing page ${page}`);layer.append(avatar);
        if(i===2 && users.length>3){const more=avatar.cloneNode();more.textContent=`+${users.length-3}`;more.style.setProperty('--avatar-right','64px');more.title=users.slice(3).map(u=>u.display_name).join(', ');layer.append(more);}
        div.append(layer);
      }
    }
  }
  watch(application, send) {
    this.application=application;
    for(const event of ['pagerendered','scalechanging','rotationchanging'])application.eventBus.on(event,()=>this.paint());
    // PDF.js dispatches mode changes before rebuilding spread DOM.
    application.eventBus.on('spreadmodechanged',()=>requestAnimationFrame(()=>this.sendCurrentPage()));
    this.send = send;
    this.page = application.pdfViewer.currentPageNumber;
    application.eventBus.on("pagechanging", ({ pageNumber }) => {
      if (pageNumber === this.page) return;
      this.page = pageNumber;
      if (this.timer) return;
      this.timer = window.setTimeout(() => {
        this.timer = null;
        this.sendCurrentPage();
      }, 350);
    });
    this.sendCurrentPage();
  }
  sendCurrentPage() {
    if (Number.isInteger(this.page) && this.page > 0) {
      const pdf=this.application?.pdfViewer,div=pdf?.getPageView(this.page-1)?.div;
      const pages=pdf?.spreadMode && div?.closest('.spread')?[...div.closest('.spread').querySelectorAll(':scope > .page')].map(p=>Number(p.dataset.pageNumber)).slice(0,2):[this.page];
      this.send(this.page,pages.length?pages:[this.page]);
    }
  }
}
