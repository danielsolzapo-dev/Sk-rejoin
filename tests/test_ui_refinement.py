"""Presentation acceptance: no game, browser, credentials or service requests."""
import os
import sys
from pathlib import Path
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ui_refinement import semantic_state, status_text, summary_text
assert semantic_state({'age':2,'status':'Aguardando heartbeat'})=='loading'
assert semantic_state({'age':2,'status':'BLOCK ACC · troca de servidor'})=='block'
assert semantic_state({'age':2,'status':'Online'})=='online'
assert semantic_state({'age':None,'status':'Sem sinal'})=='offline'
assert semantic_state({'age':2,'status':'Falhou','errorCode':403})=='error'
assert '1 selecionada · 1 erro' in summary_text(1,1,0,1,1)
assert '2 selecionadas · 0 erros' in summary_text(2,2,0,2,0)
assert '773' in status_text({'status':'Recuperando conexão','errorCode':773})
print('PASS semantic status priority, labels and pluralization')
if os.name!='nt':
    print('Native layout matrix requires Windows');raise SystemExit(0)
import tkinter as tk
from tkinter import font as tkfont,ttk
import theme
from desktop import Desktop
with tempfile.TemporaryDirectory() as folder:
    os.environ['LOCALAPPDATA']=folder
    for scale in (1.0,1.25,1.5,2.0):
      for mode in ('dark','light'):
        os.environ['SK_UI_CAPTURE_SCALE']=str(scale)
        root=tk.Tk();root.withdraw();root.tk.call('tk','scaling',96*scale/72)
        try:
          with patch.object(Desktop,'refresh'),patch.object(Desktop,'check_startup_update'):
            ui=Desktop(root,49327,'fixture-key',Path(__file__).resolve().parents[1],{'place':2753915549})
            root.deiconify();root.update()
            rows=[{'userId':i,'username':f'sk_{i:03}','status':'Online','connection':'Conectado','age':2,
                   'connected':60,'rejoin':True,'attempts':0,'maxAttempts':3,'nextIn':60,'jobId':'fixture','errorCode':None,
                   'profile':{'place':2753915549}} for i in range(1,101)]
            state={'accounts':rows,'waiting':0,'busy':False,'version':'0.12.0 UI preview','multi':'fixture','rejoin':100,'startupStatus':''}
            ui.refresh_done(state,None);ui.apply_theme(mode);root.update();ui.fit_columns();root.update()
            assert len(ui.table.get_children())==100
            print('FIT',scale,mode,ui.table.winfo_width(),ui.table.xview(),{col:ui.table.column(col) for col in ('#0',*ui.table['displaycolumns'])})
            assert not ui.horizontal.winfo_manager(),'Unnecessary horizontal scrollbar'
            assert not ui.statusbar.winfo_manager()
            assert 'UI preview' not in ui.version_chip.cget('text')
            assert str(ui.chip_diagnostic.cget('takefocus'))=='1'
            assert ui.chip_diagnostic.winfo_viewable() and ui.chip_update.winfo_viewable()
            assert not any(isinstance(w,tk.Menubutton) for w in ui.compact_panel.winfo_children())
            ui.ui_prefs['destinations']=[1,2,3,4,5,6];ui.render_refinement();root.update()
            assert sum(bool(link.winfo_manager()) for link in ui.recent_links)==5
            for link in ui.recent_links:
                assert link.winfo_rooty()+link.winfo_height()<=ui.compact_panel.winfo_rooty()+ui.compact_panel.winfo_height(),('Recent destination clipped',scale,mode)
            ui.select_recent(3);assert ui.place.get()=='4'
            ui.notice.config(text='fixture transient');assert ui.footer_summary.cget('text')=='fixture transient'
            ui.clear_status_message();assert 'Contas: 100' in ui.footer_summary.cget('text')
            ui.table.selection_set('1');ui.account_selected();root.update()
            ui.user_widths={'account':130};ui.fit_columns();root.update()
            assert ui.table.column('account','width')>=round(130*scale)
            if scale==1.0:
                assert root.winfo_width()==784
                font=tkfont.Font(root=root,font=ttk.Style(root).lookup('Treeview','font'))
                for col in ui.table['displaycolumns']:
                    assert font.measure(ui.table.set('1',col))+12<=ui.table.column(col,'width'),col
            # Geometry containment: scaled/clamped main controls remain inside the client.
            for widget in (ui.table,ui.compact_panel,ui.footer_line,ui.toolbar,ui.header):
                assert widget.winfo_viewable()
                assert widget.winfo_rootx()>=root.winfo_rootx()
                assert widget.winfo_rooty()+widget.winfo_height()<=root.winfo_rooty()+root.winfo_height()+2
            print('PASS native layout',mode,scale)
        finally:
            for callback in root.tk.call('after','info'):root.after_cancel(callback)
            root.destroy()
    os.environ.pop('SK_UI_CAPTURE_SCALE',None)
