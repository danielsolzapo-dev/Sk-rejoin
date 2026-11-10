"""Local synthetic export fixtures only. No browser, game or real account access."""
import os
from pathlib import Path
import sys
from queue import Queue
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import accounts
from session_export import export_session, SessionClipboard

COOKIE = 'synthetic_cookie_fixture_' + 'a' * 40
loader = Mock(return_value=({'username':'fixture_user'}, {'cookie':COOKIE}))
with patch.object(accounts, 'authenticated', side_effect=AssertionError('no HTTP')):
    assert export_session('fixture_user', loader=loader) == COOKIE
    assert export_session('fixture_user','combined','typed:password',loader=loader) == 'fixture_user:typed:password:'+COOKIE
    for mode, password in [('invalid',''),('combined',''),('combined','line\nbreak'),('combined','bad\rvalue')]:
        loader.reset_mock()
        try:
            export_session('fixture_user',mode,password,loader=loader)
            raise AssertionError('invalid export accepted')
        except ValueError:
            pass
        loader.assert_not_called()
    for data in [({'username':'someone_else'},{'cookie':COOKIE}),({'username':'fixture_user'},{'cookie':'invalid'})]:
        try:
            export_session('fixture_user',loader=lambda _:data)
            raise AssertionError('invalid secret accepted')
        except ValueError as error:
            assert COOKIE not in str(error)
    try:
        export_session('fixture_user',loader=Mock(side_effect=RuntimeError('secret:'+COOKIE)))
        raise AssertionError('failure swallowed')
    except ValueError as error:
        assert COOKIE not in str(error) and 'secret:' not in str(error)
print('PASS local export modes, validation, no HTTP and redacted errors')

class ClipboardRoot:
    def __init__(self):
        self.value='';self.callbacks={};self.serial=0
    def clipboard_get(self):return self.value
    def clipboard_clear(self):self.value=''
    def clipboard_append(self,value):self.value+=value
    def after(self,delay,fn):
        assert delay==30000
        self.serial+=1;self.callbacks[self.serial]=fn;return self.serial
    def after_cancel(self,token):self.callbacks.pop(token,None)
root=ClipboardRoot();clipboard=SessionClipboard(root)
clipboard.copy(COOKIE)
root.callbacks[clipboard.timer]()
assert root.value=='' and clipboard.value is None
clipboard.copy(COOKIE);root.value='user copied something else'
root.callbacks[clipboard.timer]()
assert root.value=='user copied something else'
clipboard.copy(COOKIE);old_callback=root.callbacks[clipboard.timer]
clipboard.copy('second copy');old_callback()
assert root.value=='second copy' and clipboard.value=='second copy'
root.callbacks[clipboard.timer]()
assert root.value==''
print('PASS clipboard expiry, later user copy and stale timer protection')

# UI integration is run by the Windows build (native Tk). Linux retains pure tests.
if os.name != 'nt':
    print('SKIP native export dialog: requires Windows Tk desktop')
    raise SystemExit(0)
import tkinter as tk
from tkinter import ttk
from session_export_ui import show_export
from ui_text import tr
root=tk.Tk();root.withdraw()
class App:
    def __init__(self):
        self.root=root;self.events=Queue();self.rows={'1':{'username':'fixture_user'}}
        self.notice=tk.Label(root);self.selected=[1]
    def ids(self):return self.selected
    def dialog(self,title):
        window=tk.Toplevel(root);window.title(title)
        body=tk.Frame(window);body.pack(fill='both',expand=True);return body
    def label(self,parent,text,**kwargs):
        return tk.Label(parent,text=text,wraplength=kwargs.get('wrap',0))
    def entry(self,parent):return tk.Entry(parent)
app=App()
def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)
def pump():
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        root.update()
        if not app.events.empty():
            callback,value,error=app.events.get_nowait();callback(value,error);return
        time.sleep(.01)
    raise AssertionError('worker did not finish')
try:
    app.selected=[];assert show_export(app) is None
    app.selected=[1,2];assert show_export(app) is None
    app.selected=[1]
    thread_ids=[]
    def local_load(username):
        thread_ids.append(threading.get_ident())
        return {'username':username},{'cookie':COOKIE}
    with patch.object(accounts,'load_session',side_effect=local_load):
        window=show_export(app,'combined');root.update()
        widgets=list(descendants(window))
        entry=next(w for w in widgets if isinstance(w,tk.Entry))
        button=next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text')==tr('export_copy'))
        assert entry.cget('show')=='•'
        button.invoke();assert app.events.empty()
        entry.insert(0,'typed-password');button.invoke()
        assert entry.get()==''
        pump()
        assert root.clipboard_get()=='fixture_user:typed-password:'+COOKIE
        assert thread_ids and all(t!=threading.get_ident() for t in thread_ids)
        assert all(COOKIE not in str(w.cget('text')) for w in widgets if 'text' in w.keys())
        app._session_clipboard.expire(app._session_clipboard.revision)
        window.destroy()
        window=show_export(app,'cookie');root.update()
        button=next(w for w in descendants(window) if isinstance(w,ttk.Button) and w.cget('text')==tr('export_copy'))
        button.invoke();pump();assert root.clipboard_get()==COOKIE
        app._session_clipboard.expire(app._session_clipboard.revision)
        window.destroy()
    print('PASS native dialog: selection, password masking, worker, both modes and hidden cookie')
finally:
    for token in root.tk.call('after','info'):root.after_cancel(token)
    root.destroy()
