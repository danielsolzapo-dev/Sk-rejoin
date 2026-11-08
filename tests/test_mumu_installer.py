"""No emulator or third-party APK is executed: bounded transport and ADB contracts."""
import io,json,sys,tempfile,zipfile,subprocess
from pathlib import Path
from threading import Event
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import mumu_installer as m

def apk():
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('AndroidManifest.xml',b'fixture manifest')
        z.writestr('classes.dex',b'fixture dex, not executed')
    return out.getvalue()
class Response(io.BytesIO):
    def __init__(self,data,kind='application/octet-stream',length=None,url=None):
        super().__init__(data);self.headers={'Content-Type':kind}
        if length is not None:self.headers['Content-Length']=str(length)
        self.url=url or m.FILE_BASE+'Delta-2.745.1142.apk'
    def geturl(self):return self.url

def fails(fn,fragment=''):
    try:fn()
    except m.InstallerError as error:
        assert fragment in str(error),(fragment,str(error));return
    raise AssertionError('Expected refusal')

with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);payload=apk()
    index=json.dumps({'latest_apk':[{'name':'Delta-2.745.1142.apk','size':len(payload)}]}).encode()
    calls=[]
    def opener(url):
        calls.append(url)
        return Response(index,'application/json') if url==m.INDEX_URL else Response(payload,length=len(payload))
    result=m.download_delta(root/'cache',Event(),opener=opener)
    assert Path(result['path']).read_bytes()==payload and len(result['sha256'])==64
    assert calls==[m.INDEX_URL,m.FILE_BASE+'Delta-2.745.1142.apk']
    assert not list((root/'cache').glob('*.part'))
    adb=root/'ADB with spaces'/'adb.exe';adb.parent.mkdir();adb.write_bytes(b'fixture executable, never executed')
    commands=[]
    def runner(args,**kwargs):
        commands.append((args,kwargs))
        output='List of devices attached\n127.0.0.1:16384 device model:MuMu\n127.0.0.1:16416 device model:MuMu\nUSB123 device model:Phone\n127.0.0.1:16448 offline\n' if args[1:]==['devices','-l'] else 'Success\n'
        return subprocess.CompletedProcess(args,0,output,'')
    assert m.devices(adb,runner)==['127.0.0.1:16384','127.0.0.1:16416']
    m.install_apk(adb,'127.0.0.1:16416',result['path'],Event(),runner)
    args,kwargs=commands[-1]
    assert args[1:5]==['-s','127.0.0.1:16416','install','-r']
    assert kwargs['shell'] is False and kwargs['timeout']==240
    assert not any('uninstall' in args or 'clear' in args for args,_ in commands)
    commands.clear();stopped=Event();stopped.set()
    fails(lambda:m.install_apk(adb,'127.0.0.1:16416',result['path'],stopped,runner),'cancelada')
    assert not commands
    fails(lambda:m.install_apk(adb,'127.0.0.1:12345',result['path'],Event(),runner),'não está conectada')
    assert all('install' not in args for args,_ in commands)
    for serial in ('USB123','192.168.1.8:5555','127.0.0.1:0','127.0.0.1:65536','127.0.0.1:5555;whoami'):
        fails(lambda value=serial:m.local_serial(value))
    for url in ('http://example.org/a.apk','https://localhost/a.apk','https://127.0.0.1/a.apk','https://user:pass@example.org/a.apk'):
        fails(lambda value=url:m.secure_url(value))
    bad=root/'bad.apk';bad.write_bytes(b'MZ not an APK')
    fails(lambda:m.validate_apk(bad),'inválido')
    def bad_index(url):return Response(b'{"latest_apk":[{"name":"../../x.apk","size":20}]}','application/json')
    fails(lambda:m.latest_delta(Event(),bad_index),'inválidos')
    def html_opener(url):return Response(index,'application/json') if url==m.INDEX_URL else Response(b'<html>verify</html>','text/html')
    fails(lambda:m.download_delta(root/'html',Event(),opener=html_opener),'página')
    assert not list((root/'html').glob('*.part'))
    def short_opener(url):return Response(index,'application/json') if url==m.INDEX_URL else Response(payload[:-5])
    fails(lambda:m.download_delta(root/'short',Event(),opener=short_opener),'incompleto')
    assert not list((root/'short').glob('*.part'))
    stopped=Event()
    def cancel_progress(message,received,total):
        if received:stopped.set()
    fails(lambda:m.download_delta(root/'cancel',stopped,cancel_progress,opener),'cancelada')
    assert not list((root/'cancel').glob('*.part'))
    def failed(args,**kwargs):
        if args[1:]==['devices','-l']:return runner(args,**kwargs)
        return subprocess.CompletedProcess(args,1,'','INSTALL_FAILED_UPDATE_INCOMPATIBLE')
    fails(lambda:m.install_apk(adb,'127.0.0.1:16416',result['path'],Event(),failed),'UPDATE_INCOMPATIBLE')
print('PASS MuMu: exact local target, no shell/uninstall, validation, bounded download, cancellation, partial cleanup and signature failure preservation')

if sys.platform=='win32':
    import os,tkinter as tk
    from unittest.mock import patch
    from desktop import Desktop
    with tempfile.TemporaryDirectory() as directory:
        os.environ['LOCALAPPDATA']=directory
        window=tk.Tk();window.withdraw()
        try:
            with patch.object(Desktop,'refresh'),patch.object(Desktop,'check_startup_update'),patch.object(m,'discover_adb',return_value=[]):
                ui=Desktop(window,49327,'fixture-key',Path(__file__).resolve().parents[1],{})
                window.deiconify();window.update();ui.mumu_dialog();window.update()
                assert ui.mumu_window.winfo_exists()
                original=ui.mumu_window;ui.mumu_dialog();assert original is ui.mumu_window
                for mode in ('dark','light'):ui.apply_theme(mode);window.update()
                ui.mumu_window.destroy()
                print('PASS native MuMu dialog, singleton and theme switching')
        finally:
            for callback in window.tk.call('after','info'):window.after_cancel(callback)
            window.destroy()
