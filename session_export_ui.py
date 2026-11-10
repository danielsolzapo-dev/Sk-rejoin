"""Native local export dialog; DPAPI and disk access run outside the Tk thread."""
from threading import Thread
import tkinter as tk
from tkinter import ttk
from ui_text import tr
from session_export import export_session, SessionClipboard


def show_export(app, mode='cookie'):
    ids = app.ids()
    if len(ids) != 1:
        app.notice.config(text=tr('export_select_one'))
        return
    row = app.rows.get(str(ids[0]), {})
    username = row.get('username')
    if not username:
        app.notice.config(text=tr('export_select_one'))
        return
    body = app.dialog(tr('export_title'))
    window = body.winfo_toplevel()
    app.label(body, tr('export_account', username=username)).pack(anchor='w')
    app.label(body, tr('export_help'), wrap=480).pack(anchor='w', pady=(8, 12))
    selection = tk.StringVar(window, value=mode)
    for value, key in (('cookie', 'export_cookie'), ('combined', 'export_combined')):
        ttk.Radiobutton(body, text=tr(key), variable=selection, value=value).pack(anchor='w', pady=3)
    password_label = app.label(body, tr('export_password'))
    password_label.pack(anchor='w', pady=(12, 4))
    password = app.entry(body)
    password.configure(show='•')
    password.pack(fill='x', pady=(0, 8))
    status = app.label(body, '', wrap=480)
    status.pack(anchor='w', pady=8)
    alive, busy = True, False

    def change_mode(*_):
        password.delete(0, 'end')
        password.configure(state='normal' if selection.get() == 'combined' else 'disabled')

    def close():
        nonlocal alive
        alive = False
        password.configure(state='normal')
        password.delete(0, 'end')
        window.destroy()

    def received(value, error):
        nonlocal busy
        busy = False
        if not alive or not window.winfo_exists():
            return
        button.configure(state='normal')
        password.configure(state='normal' if selection.get() == 'combined' else 'disabled')
        if error:
            status.configure(text=tr('export_unavailable'))
            return
        try:
            if not hasattr(app, '_session_clipboard'):
                app._session_clipboard = SessionClipboard(app.root)
            app._session_clipboard.copy(value)
        except Exception:
            status.configure(text=tr('export_clipboard_failed'))
            return
        status.configure(text=tr('export_copied'))

    def copy():
        nonlocal busy
        if busy:
            return
        chosen, supplied = selection.get(), password.get()
        if chosen == 'combined' and (not supplied or any(c in supplied for c in '\r\n\x00')):
            status.configure(text=tr('export_password_required'))
            password.focus_set()
            return
        busy = True
        password.configure(state='normal')
        password.delete(0, 'end')
        password.configure(state='disabled')
        button.configure(state='disabled')
        status.configure(text=tr('export_preparing'))

        def worker():
            nonlocal supplied
            try:
                value = export_session(username, chosen, supplied)
            except Exception:
                app.events.put((received, None, True))
            else:
                app.events.put((received, value, None))
            finally:
                supplied = ''
        Thread(target=worker, daemon=True).start()

    button = ttk.Button(body, text=tr('export_copy'), command=copy)
    button.pack(anchor='w', pady=8)
    ttk.Button(body, text=tr('export_close'), command=close).pack(anchor='w')
    selection.trace_add('write', change_mode)
    change_mode()
    if mode == 'combined':
        password.focus_set()
    window.protocol('WM_DELETE_WINDOW', close)
    window.bind('<Escape>', lambda _: close())
    return window
