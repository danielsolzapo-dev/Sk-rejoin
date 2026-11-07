"""Native Windows rendering and real Treeview selection/filter behavior."""
import base64
import io
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

if os.name != 'nt':
    print('Native visual check runs on Windows.')
    raise SystemExit(0)

with tempfile.TemporaryDirectory() as folder:
    os.environ['LOCALAPPDATA'] = folder
    root_path = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root_path))
    import tkinter as tk
    from desktop import Desktop
    from PIL import ImageGrab
    window = tk.Tk()
    window.withdraw()
    try:
        with patch.object(Desktop, 'refresh'), patch.object(Desktop, 'check_startup_update'):
            ui = Desktop(window, 49327, 'fixture-key', root_path, {'place': 2753915549})
            states = [('sk_aurora', 'Online', 'Conectado', 2, None),
                      ('sk_horizon', 'BLOCK ACC · troca de servidor solicitada', 'Conectado', 3, None),
                      ('sk_lunar', 'Aguardando heartbeat', 'Carregando', 4, None),
                      ('sk_nova', 'Sem sinal', 'Sem sinal', 48, None),
                      ('sk_orion', 'Recuperando conexão', 'Erro 773', 2, 773)]
            rows = [{'userId': i, 'username': name, 'status': status, 'connection': connection,
                     'age': age, 'connected': 1800 if age < 20 else None, 'rejoin': True,
                     'attempts': 0, 'maxAttempts': 3, 'nextIn': 60, 'jobId': '7a901b26-abc123',
                     'errorCode': error, 'profile': {'place': 2753915549, 'fps': 10}}
                    for i, (name, status, connection, age, error) in enumerate(states, 1)]
            ui.refresh_done({'accounts': rows, 'waiting': 0, 'busy': False, 'version': '0.11.1',
                             'multi': 'Múltiplas instâncias observadas', 'rejoin': 5, 'startupStatus': ''}, None)
            ui.table.selection_set('1')
            ui.search.set('nova')
            assert ui.table.get_children() == ('4',)
            assert not ui.table.selection(), 'Hidden rows must not remain selected'
            ui.search.set('')
            ui.state_filter.set('Com erro')
            ui.filter_accounts()
            assert ui.table.get_children() == ('5',)
            ui.select_all()
            assert ui.ids() == [5]
            ui.state_filter.set('Todas')
            ui.filter_accounts()
            assert len(ui.table.get_children()) == 5
            ui.table.selection_set('1')
            ui.account_selected()
            assert tuple(ui.table["displaycolumns"]) == ("account", "status", "age")
            ui.detail_columns.set(True)
            ui.set_list_columns()
            assert len(ui.table["displaycolumns"]) == 6
            ui.detail_columns.set(False)
            ui.set_list_columns()
            ui.copy_account("username")
            assert window.clipboard_get() == "sk_aurora"
            ui.copy_account("userId")
            assert window.clipboard_get() == "1"
            assert ui.menubar.index("end") == 3
            assert not ui.settings_window.winfo_viewable()
            assert not ui.profile_window.winfo_viewable()
            window.deiconify()
            window.update()
            assert window.winfo_width() == 784 and window.winfo_height() == 380
            assert ui.table.winfo_height() >= 130
            # Synthetic accounts only. Preview is kept in CI logs for visual QA.
            box = (window.winfo_rootx(), window.winfo_rooty(),
                   window.winfo_rootx()+window.winfo_width(), window.winfo_rooty()+window.winfo_height())
            buffer = io.BytesIO()
            ImageGrab.grab(bbox=box).save(buffer, format='PNG')
            print('SK_VISUAL_PREVIEW=' + base64.b64encode(buffer.getvalue()).decode())
            ui.show_config()
            window.update()
            assert ui.settings_window.winfo_viewable()
            assert window.winfo_width() == 784 and window.winfo_height() == 380
            ui.toggle_controls()
            window.update()
            assert ui.profile_window.winfo_viewable()
            assert window.winfo_width() == 784 and window.winfo_height() == 380
            ui.profile_window.withdraw()
            ui.settings_window.withdraw()
            ui.show_search()
            window.update_idletasks()
            assert ui.search_field.winfo_viewable()
            for tab in range(8):
                ui.config_sections.select(tab)
                window.update_idletasks()
            ui.toggle_compact()
            ui.toggle_compact()
            window.update_idletasks()
            assert ui.table.winfo_exists()
            print('PASS native rendering, search, status filter, hidden selection safety, config pages, compact mode')
    finally:
        window.destroy()

