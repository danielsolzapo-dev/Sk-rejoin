"""Real authenticated bridge, durable receipts and selected-account controls."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import uuid
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError

with tempfile.TemporaryDirectory() as temp:
    os.environ['LOCALAPPDATA']=temp
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    import app
    import bridge_commands as commands
    app.accounts.accounts=lambda:[{'userId':1,'username':'first_one'},{'userId':2,'username':'second_two'}]
    http=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
    app.PORT=http.server_port
    threading.Thread(target=http.serve_forever,daemon=True).start()
    def request(path,data,key=None):
        req=Request(f'http://127.0.0.1:{app.PORT}'+path,data=json.dumps(data).encode(),headers={'X-Rejoin-Key':key or app.TRACKER_KEY})
        with urlopen(req) as response:return json.load(response)
    def command(action,payload=None,identity=None):
        value={'id':identity or uuid.uuid4().hex,'action':action,'payload':payload or {},'expires':time.time()+60}
        request('/tracker/command',value)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            receipt=next(r for r in commands.snapshot() if r['id']==value['id'])
            if receipt['status'] in ('completed','failed','uncertain'):return value,receipt
            time.sleep(.01)
        raise AssertionError('Command did not finish')
    try:
        _,receipt=command('diagnostic')
        assert receipt['status']=='completed' and receipt['result']['checks']
        try:
            request('/startup',{},app.TRACKER_KEY);raise AssertionError('Bridge key may not edit startup executables')
        except HTTPError as error:assert error.code==401
        profile={'ids':[1],'place':10,'fps':15,'width':400,'height':300,'delay':60,'max_attempts':3,'rejoin':True}
        value,receipt=command('profile',profile)
        assert receipt['status']=='completed'
        assert app.accounts.read(app.PROFILES,{})['1']['fps']==15
        assert 1 in app.REJOIN
        with patch.object(app,'execute_unified',side_effect=AssertionError('Command replayed')):
            assert request('/tracker/command',value)['status']=='completed'
        app.REJOIN={i:{'place':i*10,'delay':60,'attempts':0,'max_attempts':3,'next':0} for i in (1,2)}
        app.BINDINGS={1:(101,11),2:(202,22)}
        closed=[]
        with patch.object(app.windows,'same_process',return_value=True),patch.object(app.windows,'close_bound',lambda *binding:closed.append(binding)):
            _,receipt=command('close',{'ids':[1]})
        assert receipt['status']=='completed' and closed==[(101,11)]
        assert 1 not in app.REJOIN and 2 in app.REJOIN and app.BINDINGS[2]==(202,22)
        def launch(payload):
            now=time.monotonic()
            app.LIVE[1]={'received':now,'since':now,'place':10,'session':'new'}
        with patch.object(app,'start_job',launch):
            _,receipt=command('open',{'ids':[1]})
        assert receipt['status']=='completed'
        with patch.object(app,'start_job',lambda payload:None):
            _,receipt=command('open',{'ids':[1]})
        assert receipt['status']=='failed','Old heartbeat must not confirm a new launch'
        _,receipt=command('profile',{**profile,'ids':[999]})
        assert receipt['status']=='failed'
        with patch.object(app.update,'manifest',return_value=({'version':'9.0.0'},True)):
            _,receipt=command('update_check')
        assert receipt['result']['available']=='9.0.0'
        app.APP_EXIT=lambda:None
        with patch.object(app.update,'manifest',return_value=({'version':'9.0.0'},True)),patch.object(app.update,'install') as install,patch.object(app.threading,'Timer') as timer:
            _,receipt=command('update_install')
            assert receipt['status']=='completed'
            install.assert_called_once()
            assert timer.call_args.args==(2,app.APP_EXIT)
        def prepare():app.STARTUP_STATUS='Sequência de inicialização concluída'
        with patch.object(app,'startup_sequence',prepare):
            _,receipt=command('prepare')
            assert receipt['status']=='completed'
        # A receipt persisted across a crash must never run its side effect again.
        stale=uuid.uuid4().hex
        rows=app.accounts.read(commands.PATH,{})
        rows[stale]={'id':stale,'status':'running','created':time.time(),'action':'close'}
        app.accounts.write(commands.PATH,rows)
        assert next(r for r in commands.snapshot() if r['id']==stale)['status']=='uncertain'
        assert request('/tracker/state',{})['bridgeProtocol']==2
        print('PASS unified bridge: restricted key, real receipts, durable replay protection, profile, targeted close, fresh-session confirmation and update check')
    finally:
        http.shutdown();http.server_close()
