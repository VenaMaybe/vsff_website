import { jsonRequest } from './thread_api.js';

const form=document.getElementById('appearance-form');
const error=document.getElementById('appearance-error');
const values=()=>({
  ...Object.fromEntries(['ui_theme','pdf_theme'].map(key=>[key,form.elements[key].checked?'dark':'light'])),
  ...Object.fromEntries(['pdf_color_amount','pdf_white_point','card_zoom_threshold'].map(key=>[key,form.elements[key].valueAsNumber])),
});
let saved=values(),pending=false,running=false;

function apply(settings){
  for(const key of ['ui_theme','pdf_theme'])form.elements[key].checked=settings[key]==='dark';
  document.documentElement.dataset.uiTheme=settings.ui_theme;
  for(const key of ['pdf_color_amount','pdf_white_point','card_zoom_threshold']){
    const input=form.elements[key];input.value=settings[key];
    form.querySelector(`output[for="${input.id}"]`).textContent=`${settings[key]}%`;
  }
  form.querySelector('.appearance-pdf-colors').hidden=settings.pdf_theme!=='dark';
}

async function save(){
  if(running)return;
  running=true;form.dataset.saving='true';
  try{
    // Serialize writes and coalesce rapid changes, so an older response cannot
    // overwrite the latest choice. The UI never waits for these requests.
    while(pending){
      pending=false;
      const settings=values();
      try{
        await jsonRequest(form.action,{method:'POST',body:new URLSearchParams(settings),
          headers:{'Content-Type':'application/x-www-form-urlencoded'},keepalive:true});
        saved=settings;
      }catch{
        if(!pending){
          apply(saved);error.textContent='Couldn’t save appearance. Try again.';error.hidden=false;
        }
      }
    }
  }finally{running=false;form.dataset.saving='false';}
}

form.addEventListener('submit',event=>event.preventDefault());
form.addEventListener('input',()=>apply(values()));
form.addEventListener('change',()=>{
  apply(values());error.hidden=true;pending=true;save();
});
