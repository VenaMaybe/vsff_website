"""Focused headless Firefox Page Properties check; synthetic PDFs and isolated profile.
Run: python tests/firefox_page_properties.py [--small]"""
import json,os,socket,subprocess,sys,tempfile,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
class Marionette:
 def __init__(self,port):
  self.socket=socket.create_connection(('127.0.0.1',port),timeout=30);self.file=self.socket.makefile('rb');self.counter=0;self.read()
 def read(self):
  length=b''
  while (char:=self.file.read(1))!=b':':
   if not char:raise RuntimeError('Firefox connection closed')
   length+=char
  return json.loads(self.file.read(int(length)))
 def call(self,command,params=None):
  self.counter+=1;message=json.dumps([0,self.counter,command,params or {}]).encode();self.socket.sendall(str(len(message)).encode()+b':'+message)
  reply=self.read()
  if reply[2]:raise RuntimeError(reply[2])
  return reply[3]
 def ev(self,script):
  result=self.call('WebDriver:ExecuteAsyncScript',{'script':"const done=arguments[arguments.length-1];Promise.resolve().then(()=>eval(arguments[0])).then(value=>done({value}),error=>done({error:String(error),stack:error.stack}));",'args':[script],'newSandbox':False,'sandbox':'default'})
  if result.get('value',{}).get('error'):raise RuntimeError(result)
  return result.get('value',{}).get('value')
 def wait(self,script):
  until=time.monotonic()+30
  while time.monotonic()<until:
   if self.ev(script):return
   time.sleep(.1)
  raise TimeoutError(script)
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
    try:client=Marionette(port)
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
   print('Firefox viewer ready',flush=True)
   client.ev("document.querySelector('[data-left-card=properties]').click()")
   client.wait("document.querySelector('.properties-status')&&!document.querySelector('.properties-status').textContent.startsWith('Calculating')")
   result=client.ev("""(async()=>{
    const times=[],chart=document.querySelector('.properties-chart'),first=chart.querySelector('.properties-bar');
    let changes=0;const observer=new MutationObserver(records=>{changes+=records.length;});observer.observe(chart,{attributes:true,childList:true,subtree:true});
    for(const metric of ['time','comments','words','time','comments','time']){
      const start=performance.now();document.querySelector('[data-metric='+metric+']').click();const sync=performance.now()-start;
      await new Promise(resolve=>setTimeout(resolve,150));times.push({metric,sync});
    }
    const beforeRepeat=changes;document.querySelector('[data-metric=time]').click();await new Promise(resolve=>setTimeout(resolve,150));
    const repeatedChanges=changes-beforeRepeat;observer.disconnect();
    return {times,changes,repeatedChanges,rows:chart.querySelectorAll('.properties-bar').length,stable:chart.querySelector('.properties-bar')===first,ticks:[...chart.querySelectorAll('text')].map(e=>e.textContent),toggle:!!document.querySelector('.properties-options')};
   })()""")
   print(json.dumps(result),flush=True)
   assert result['stable'] and not result['toggle'] and result['repeatedChanges']==0,result
   numbers=[label for label in result['ticks'] if label.replace(',','').replace('.','').isdigit()]
   assert all(float(label.replace(',','')).is_integer() for label in numbers),numbers
   assert max(entry['sync'] for entry in result['times'])<1000,result
   print('PASS Firefox stable metric switching, integer ticks, always-on grid and responsiveness',flush=True)
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
