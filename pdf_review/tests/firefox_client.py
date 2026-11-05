"""Minimal Firefox Marionette client for isolated browser acceptance checks."""
import json,socket,time

class Marionette:
 def __init__(self,port,*,page_context=False):
  self.sandbox=None if page_context else 'default'
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
  result=self.call('WebDriver:ExecuteAsyncScript',{'script':"const done=arguments[arguments.length-1];Promise.resolve().then(()=>eval(arguments[0])).then(value=>done({value}),error=>done({error:String(error),stack:error.stack}));",'args':[script],'newSandbox':False,'sandbox':self.sandbox})
  if result.get('value',{}).get('error'):raise RuntimeError(result)
  return result.get('value',{}).get('value')
 def wait(self,script):
  until=time.monotonic()+30
  while time.monotonic()<until:
   if self.ev(script):return
   time.sleep(.1)
  raise TimeoutError(script)
