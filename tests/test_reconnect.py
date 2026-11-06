import os,sys,tempfile,time,threading,json,urllib.request
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp:
 os.environ['LOCALAPPDATA']=temp
 sys.path.insert(0,str(root))
 import app as a
 a.accounts.accounts=lambda:[{'userId':1,'username':'test_one'},{'userId':2,'username':'test_two'}]
 a.PORT=49687
 server=a.ThreadingHTTPServer(('127.0.0.1',a.PORT),a.Handler)
 threading.Thread(target=server.serve_forever,daemon=True).start()
 def req(path,value,key=None):
  request=urllib.request.Request(f'http://127.0.0.1:{a.PORT}'+path,data=json.dumps(value).encode(),headers={'X-Heartbeat-Key' if path=='/heartbeat' else 'X-Rejoin-Key':key or (a.KEY if path=='/heartbeat' else a.ADMIN)})
  with urllib.request.urlopen(request) as r:return json.load(r)
 try:
  req('/rejoin',{'ids':[1],'place':10,'rejoin_delay':60,'max_attempts':4})
  req('/rejoin',{'ids':[2],'place':20,'rejoin_delay':120,'max_attempts':2})
  assert a.REJOIN[1]['place']==10 and a.REJOIN[2]['place']==20
  req('/heartbeat',{'userId':1,'placeId':10,'session':'new'})
  a.LIVE[1]['received']=time.monotonic()-61
  calls=[]
  with patch.object(a,'start_job',lambda value,**kw:calls.append(value)):
   a.watch_once()
   assert calls==[{'ids':[1],'place':10}]
   assert a.REJOIN[1]['attempts']==1
   assert 58<a.REJOIN[1]['next']-time.monotonic()<=60
   a.REJOIN[1]['next']=0
   a.watch_once()
   assert 118<a.REJOIN[1]['next']-time.monotonic()<=120
   a.BINDINGS[1]=(23,345)
   a.REJOIN[1]['next']=0
   with patch.object(a.windows,'same_process',lambda *args:True):a.watch_once()
   assert len(calls)==2 and 'ainda aberta' in a.STATUS[1]
   a.BINDINGS.clear()
   a.REJOIN[1]['attempts']=4
   a.watch_once()
   assert len(calls)==2 and 'Limite' in a.STATUS[1]
  req('/heartbeat',{'userId':1,'placeId':10,'session':'new'})
  assert a.REJOIN[1]['attempts']==4,'single heartbeat must not reset retries'
  a.LIVE[1]['since']=time.monotonic()-121
  req('/heartbeat',{'userId':1,'placeId':10,'session':'new'})
  assert a.REJOIN[1]['attempts']==0
  req('/rejoin',{'ids':[1],'place':10,'disable':True})
  assert 1 not in a.REJOIN and 2 in a.REJOIN
  a.REJOIN.clear();a.LIVE.clear();a.restore_profiles()
  assert 1 not in a.REJOIN and 2 in a.REJOIN
  assert a.public_state()['accounts'][1]['nextIn'] is None
  assert req('/diagnostic',{})['checks']
  print('PASS app: authenticated HTTP, independent profiles, selected pause, restart restoration, progressive delay, attempt cap, stable recovery, duplicate-process protection')
 finally:server.shutdown();server.server_close()
