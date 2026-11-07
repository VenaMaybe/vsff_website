// Public policies can reuse presentation without reading an account/session.
// This cookie contains only light/dark and never grants access to anything.
(() => {
  const root=document.documentElement;
  const remember=()=>{
    const theme=root.dataset.uiTheme==='dark'?'dark':'light';
    const value=`pdf_review_ui_theme=${theme}`;
    if(document.cookie.split(';').some(item=>item.trim()===value))return;
    document.cookie=`${value}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol==='https:'?'; Secure':''}`;
  };
  remember();
  new MutationObserver(remember).observe(root,{attributes:true,attributeFilter:['data-ui-theme']});
})();
