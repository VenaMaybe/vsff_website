"""Firefox reading-card regression: isolated 138-page PDF and 24 chapter markers.
Run: python tests/firefox_reading_cards.py"""
import json,os,socket,subprocess,sys,tempfile,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from tests.firefox_client import Marionette
with tempfile.TemporaryDirectory(prefix='pdf-review-firefox-',ignore_cleanup_errors=True) as temporary:
 temp=Path(temporary);server=browser=client=None
 with (temp/'private.log').open('w') as log:
  try:
   env={**os.environ}
   if '--small' not in sys.argv:env['PDF_REVIEW_TEST_PROPERTIES']='1'
   server=subprocess.Popen([sys.executable,str(root/'tests/browser_sanity.py'),'--server',str(temp)],cwd=root,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
   until=time.monotonic()+20
   while not (temp/'fixture.json').exists():
    if time.monotonic()>until:raise TimeoutError('fixture startup')
    time.sleep(.1)
   fixture=json.loads((temp/'fixture.json').read_text());base=f"http://127.0.0.1:{fixture['port']}"
   with socket.socket() as port_probe:port_probe.bind(('127.0.0.1',0));port=port_probe.getsockname()[1]
   profile=temp/'profile';profile.mkdir();(profile/'user.js').write_text(f'user_pref("marionette.port",{port});\nuser_pref("browser.shell.checkDefaultBrowser",false);\nuser_pref("browser.aboutwelcome.enabled",false);\nuser_pref("datareporting.policy.dataSubmissionEnabled",false);\n')
   browser=subprocess.Popen(['C:/Program Files/Mozilla Firefox/firefox.exe','--headless','--no-remote','--profile',str(profile),'--marionette'],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
   until=time.monotonic()+20
   while client is None:
    try:client=Marionette(port,page_context=True)
    except ConnectionRefusedError:
     if time.monotonic()>until:raise
     time.sleep(.1)
   print('Firefox handshake ready',flush=True)
   client.call('WebDriver:NewSession',{'capabilities':{'alwaysMatch':{'acceptInsecureCerts':False}}})
   client.call('WebDriver:SetTimeouts',{'script':30000,'pageLoad':30000})
   client.call('WebDriver:Navigate',{'url':base+'/healthz'})
   client.call('WebDriver:AddCookie',{'cookie':{'name':'pdf_review_session','value':fixture['cookies'][0],'path':'/','httpOnly':True,'secure':False}})
   client.call('WebDriver:Navigate',{'url':base+f"/versions/{fixture['versions'][0]}/view"})
   client.wait("document.querySelector('#realtime-status')?.textContent==='Live'")
   print('Firefox reading viewer ready',flush=True)
   client.ev("""(()=>{
    const original=window.fetch;window.fetch=async(...args)=>{
      const response=await original(...args),url=String(args[0]);
      if(url.endsWith('/reading')&&response.ok){const data=await response.clone().json();data.sections=Array.from({length:24},(_,i)=>({section_id:'section'+i,name:'Chapter '+(i+1),start:i*138/24,end:(i+1)*138/24,start_page:Math.floor(i*138/24)+1,end_page:Math.ceil((i+1)*138/24)}));return new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}});}
      return response;
    };
   })()""")
   client.ev("document.querySelector('[data-left-card=reading]').click()")
   client.wait("document.querySelectorAll('.reading-spine-label.section').length===25")
   if '--all-tools' in sys.argv:
    client.ev("document.querySelector('#review-tools-menu > summary').dispatchEvent(new MouseEvent('dblclick',{bubbles:true}))")
    for tool in ['search','filters','analytics','properties','settings','sections']:
     client.ev(f"document.querySelector('.tools-panel [data-left-card={tool}]').click()")
    client.wait("document.querySelectorAll('.left-card').length===8&&document.querySelector('.settings-panel form')!==null")
   result=client.ev("""(async()=>{
    const spine=document.querySelector('.reading-spine'),content=spine.parentElement,label=document.querySelector('.reading-spine-label');
    let mutations=0,removedElements=0;const observer=new MutationObserver(changes=>{mutations+=changes.length;for(const change of changes)for(const removed of change.removedNodes)if(removed.nodeType===1)removedElements+=1+removed.querySelectorAll('*').length;});observer.observe(content,{subtree:true,childList:true,attributes:true});
    const times=[];for(let i=0;i<10;i++){
      document.querySelector('.reading-spine-card .dialog-header button:last-child').click();
      const start=performance.now();document.querySelector('[data-left-card=reading]').click();times.push(performance.now()-start);
      await new Promise(resolve=>setTimeout(resolve,100));
    }
    await new Promise(resolve=>setTimeout(resolve,500));observer.disconnect();
    return {sectionRows:document.querySelectorAll('.reading-spine-label.section').length,mutations,removedElements,stable:spine===document.querySelector('.reading-spine')&&label===document.querySelector('.reading-spine-label'),maxOpenMs:Math.max(...times),sumOpenMs:times.reduce((n,t)=>n+t,0)};

   })()""")
   print(json.dumps(result),flush=True)
   assert result['stable'] and result['removedElements']<10,result
   assert result['maxOpenMs']<1000,result
   from tests.reading_rendering import check_detached_pages
   check_detached_pages(client.ev)
   print('PASS Firefox long-document reading card: stable spine, bounded reopening and detached-page cancellation',flush=True)

  finally:
   if client:
    try:client.call('Marionette:Quit',{'flags':['eForceQuit']})
    except Exception:pass
    client.socket.close()
   if browser:
    try:browser.wait(timeout=5)
    except subprocess.TimeoutExpired:pass
   time.sleep(.5)
   for process in (browser,server):
    if process and process.poll() is None:process.terminate();process.wait(timeout=10)
