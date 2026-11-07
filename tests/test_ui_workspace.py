"""Native presentation smoke. Uses fixtures and UI-only temporary storage."""
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if os.name!='nt':
    print('UI workspace smoke requires Windows.');raise SystemExit(0)
with tempfile.TemporaryDirectory() as directory:
    os.environ['LOCALAPPDATA']=directory
    import tkinter as tk
    from desktop import Desktop
    import theme
    import ui_preferences
    root=tk.Tk();root.withdraw()
    try:
        with patch.object(Desktop,'refresh'),patch.object(Desktop,'check_startup_update'):
            started=time.monotonic()
            ui=Desktop(root,49327,'fixture-key',Path(__file__).resolve().parents[1],{'place':2753915549})
            root.deiconify();root.update()
            print('UI construction seconds:',round(time.monotonic()-started,3))
            rows=[{'userId':i,'username':f'fixture_{i:03}','status':'Online','connection':'Conectado','age':2,
                   'connected':60,'rejoin':True,'attempts':0,'maxAttempts':3,'nextIn':60,'jobId':'fixture-job','errorCode':None,
                   'profile':{'place':2753915549,'fps':10}} for i in range(1,101)]
            state={'accounts':rows,'waiting':0,'busy':False,'version':'fixture','multi':'fixture','rejoin':100,'startupStatus':''}
            ui.refresh_done(state,None)
            # No identical row data should be rewritten.
            with patch.object(ui.table,'item',wraps=ui.table.item) as item:
                ui.refresh_done(state,None)
                assert not item.called
            ui.table.selection_set('3','4');selection=ui.table.selection()
            ui.refresh_done(state,None);assert ui.table.selection()==selection
            ui.sort_by('account');assert ui.table.get_children()[0]=='100'
            ui.search.set('fixture_050');assert ui.table.get_children()==('50',)
            ui.search.set('');ui.select_all();assert len(ui.ids())==100
            for mode in ('dark','light'):
                ui.apply_theme(mode);root.update_idletasks()
                assert ui.palette==theme.PALETTES[mode]
            ui.place.delete(0,'end');ui.place.insert(0,'invalid')
            assert not ui.validate_destination()
            assert ui.open_button['state']=='disabled'
            ui.place.delete(0,'end');ui.place.insert(0,'2753915549');assert ui.validate_destination()
            ui.schedule_remove([1]);assert ui.removal_timer
            with patch.object(ui,'run',side_effect=AssertionError('Undo must not send remove')):
                ui.undo_remove();root.update()
            assert not ui.removal_timer
            ui.import_dialog();root.update()
            window=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel) and w.title()=='Importar sessões')
            def children(widget):
                out=[]
                for child in widget.winfo_children():out.append(child);out.extend(children(child))
                return out
            widgets=children(window)
            field=next(w for w in widgets if isinstance(w,tk.Entry))
            assert field.cget('show')=='•'
            root.clipboard_clear();root.clipboard_append('fixture-session-A-'*3+'\n'+'fixture-session-B-'*3)
            field.event_generate('<<Paste>>');root.update()
            button=next(w for w in widgets if isinstance(w,tk.Button) and w.cget('text')=='Validar e importar')
            with patch.object(ui,'run') as request:
                button.invoke()
                assert len(request.call_args.args[1]['cookies'].splitlines())==2
                assert field.get()==''
            window.destroy()
            ui.column_dialog();ui.command_palette();ui.first_run();root.update()
            assert root.winfo_width()==784 and root.winfo_height()==301
            assert not list(ui_preferences.location().parent.glob('native-sessions*'))
            print('PASS theme switching, identical snapshots, selection, 100 rows, ordering, validation and undo.')
    finally:
        for callback in root.tk.call('after','info'):
            root.after_cancel(callback)
        root.destroy()
