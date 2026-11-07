"""Render before/after screens with synthetic accounts; never launch browsers/games."""
import argparse
import asyncio
import base64
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import AsyncMock,patch

parser=argparse.ArgumentParser();parser.add_argument('--label',default='after');args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
if os.name!='nt':raise SystemExit('Screenshot matrix requires a Windows desktop.')
from PIL import Image,ImageGrab,ImageOps,ImageDraw
import tkinter as tk
os.environ['LOCALAPPDATA']=tempfile.mkdtemp(prefix='sk-ui-fixtures-')
import theme
import browser_login
if args.label=='before':
    spec=importlib.util.spec_from_file_location('before_desktop',ROOT/'docs'/'desktop-before.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);Desktop=module.Desktop
else:
    from desktop import Desktop
OUT=ROOT/'docs'/'screenshots';OUT.mkdir(parents=True,exist_ok=True)
ROWS=[{'userId':i,'username':name,'status':status,'connection':connection,'age':age,'connected':600 if age<20 else None,
       'rejoin':True,'attempts':0,'maxAttempts':3,'nextIn':60,'jobId':'fixture-server-'+str(i),'errorCode':error,
       'profile':{'place':2753915549,'width':320,'height':240,'fps':10,'delay':60,'max_attempts':3}}
      for i,(name,status,connection,age,error) in enumerate([
          ('sk_aurora','Online','Conectado',2,None),('sk_horizon','BLOCK ACC · troca de servidor solicitada','Conectado',3,None),
          ('sk_lunar','Aguardando heartbeat','Carregando',4,None),('sk_nova','Sem sinal','Sem sinal',65,None),
          ('sk_orion','Recuperando conexão','Erro 773',2,773)],1)]
STATE={'accounts':ROWS,'waiting':0,'busy':False,'version':'0.12.0 UI preview','multi':'Múltiplas instâncias observadas',
       'rejoin':5,'startupStatus':'2/4 · WebLauncher — aguardando 10 s','repo':''}

def dispatch(self,path,data,callback):
    fixture={'/state':STATE,'/diagnostic':{'checks':['Windows: disponível','Protocolo Roblox registrado','5 processos de exemplo','Ticket HTTP 200 · resgate não verificado']},
             '/auth-check':{'result':{'message':'Fixture de diagnóstico. Sem acesso a conta real.','stage':'verificado','sessionValid':True,'ticketHTTP':200,'ticketIssued':True}},
             '/history':{'entries':[{'time':'07/11/2026 07:00','account':'sk_aurora','event':'Heartbeat confirmado (exemplo)'}]},
             '/script':{'script':'-- Fixture: o script real é fornecido pelo serviço local.\n-- Nenhuma chave real nas capturas.'},
             '/check':{'available':'0.12.0','newer':False,'installable':False}}
    callback(fixture.get(path,{'ok':True,'message':'Exemplo'}),None)

def capture(window,name):
    window.deiconify();window.lift()
    window.update_idletasks();window.update()
    # Tk update finishes before the Windows compositor presents the new surface.
    # Allow native paint messages to settle before reading desktop pixels.
    end=time.monotonic()+.25
    while time.monotonic()<end:
        window.update();time.sleep(.01)
    try:
        import ctypes
        ctypes.windll.dwmapi.DwmFlush()
    except (AttributeError,OSError):pass
    x,y=window.winfo_rootx(),window.winfo_rooty();w,h=window.winfo_width(),window.winfo_height()
    try:
        import ctypes
        from ctypes import wintypes
        rect=wintypes.RECT()
        fn=ctypes.windll.user32.GetWindowRect
        fn.argtypes=[ctypes.c_void_p,ctypes.POINTER(wintypes.RECT)]
        handle=int(window.frame(),0)
        if fn(handle,ctypes.byref(rect)):
            dwm=ctypes.windll.dwmapi.DwmGetWindowAttribute
            dwm.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint]
            visible=wintypes.RECT()
            if dwm(handle,9,ctypes.byref(visible),ctypes.sizeof(visible))==0:rect=visible
            x,y,w,h=rect.left,rect.top,rect.right-rect.left,rect.bottom-rect.top
    except (AttributeError,OSError,ValueError):pass
    ImageGrab.grab((x,y,x+w,y+h)).save(OUT/name)

for scale in (1.0,1.5):
 for mode in (('original',) if args.label=='before' else ('dark','light')):
    os.environ['SK_UI_CAPTURE_SCALE']=str(scale)
    root=tk.Tk();root.withdraw();root.tk.call('tk','scaling',96*scale/72)
    with patch.object(Desktop,'refresh'),patch.object(Desktop,'check_startup_update'),patch.object(Desktop,'dispatch',dispatch),patch.object(browser_login,'import_batch',new=AsyncMock(return_value=None)):
        ui=Desktop(root,49327,'fixture-key',ROOT,{'place':2753915549})
        root.deiconify();ui.refresh_done(STATE,None);root.update()
        if hasattr(ui,'palette'):
            # Drain asynchronous preferences before choosing the render theme.
            end=time.monotonic()+.2
            while time.monotonic()<end:root.update();time.sleep(.01)
            ui.theme_choice.set(mode);ui.apply_theme(mode);ui.ui_scale=scale;theme.apply(root,ui.palette,scale)
        prefix=f'{args.label}-{mode}-{round(scale*100)}'
        ui.table.selection_set('1');ui.account_selected();root.update()
        capture(root,prefix+'-main.png')
        ui.show_config();root.update()
        for index in range(len(ui.config_sections.tabs())):
            ui.config_sections.select(index);root.update();capture(ui.settings_window,prefix+f'-config-{index}.png')
        ui.settings_window.withdraw();ui.toggle_controls();root.update();capture(ui.profile_window,prefix+'-profile.png');ui.profile_window.withdraw()
        methods=['connection_details','auth_check','diagnostic','heartbeat','fps_dialog','updates','history','import_dialog','password_dialog','manual_dialog']
        if args.label!='before':methods+=['first_run','column_dialog','command_palette']
        for method in methods:
            previous=set(root.winfo_children());getattr(ui,method)();root.update()
            dialogs=[w for w in root.winfo_children() if isinstance(w,tk.Toplevel) and w not in previous]
            for dialog in dialogs:
                dialog.update();capture(dialog,prefix+'-'+method+'.png');dialog.destroy()
            ui.pending=False
        hundred=[{**ROWS[0],'userId':i,'username':f'fixture_{i:03}'} for i in range(1,101)]
        ui.refresh_done({**STATE,'accounts':hundred},None)
        assert len(ui.table.get_children())==100
        if hasattr(ui,'choose_theme'):
            ui.sort_by('account');assert ui.table.get_children()[0]=='100'
            ui.search.set('fixture_050');assert len(ui.table.get_children())==1;ui.search.set('')
            ui.apply_theme(mode)
        root.update();capture(root,prefix+'-100-accounts.png')
        for callback in root.tk.call('after','info'):root.after_cancel(callback)
        root.destroy()
print('SCREENSHOTS_COMPLETE='+args.label)
if args.label=='after':
    names=['before-original-100-main.png','after-dark-100-main.png','after-light-100-main.png']
    tiles=[]
    for name in names:
        image=Image.open(OUT/name).convert('RGB');image.thumbnail((784,340))
        tile=Image.new('RGB',(808,380),'#dce3ec');tile.paste(image,(12,28));ImageDraw.Draw(tile).text((12,8),name,fill='#142237');tiles.append(tile)
    contact=Image.new('RGB',(808,380*len(tiles)),'white')
    for i,tile in enumerate(tiles):contact.paste(tile,(0,380*i))
    contact.save(OUT/'comparison.png')
    preview=io.BytesIO();contact.save(preview,format='JPEG',quality=75)
    print('SK_UI_PREVIEW='+base64.b64encode(preview.getvalue()).decode())
