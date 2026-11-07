"""Presentation-only extensions. Workers do I/O; Tk callbacks only render and dispatch."""
from ui_text import tr
import json
import time
from threading import Thread
import tkinter as tk
from tkinter import ttk, messagebox
import theme
import ui_preferences
from ui_refinement import RefinedUI, semantic_state

class WorkspaceUI(RefinedUI):

    def init_workspace(self):
        self.palette = dict(theme.DARK)
        self.ui_prefs = dict(ui_preferences.DEFAULTS)
        self.ui_scale = theme.scale_for(self.root)
        self.sort_column = 'account'
        self.sort_reverse = False
        self.row_cache = {}
        self.drag_start = None
        self.removal_timer = None
        self.ui_config_dirty = False
        self.profile_dirty = False
        self.current_profile_id = None
        if not hasattr(self, 'theme_choice'):
            self.theme_choice = tk.StringVar(value='dark')
        self.profile_window.protocol('WM_DELETE_WINDOW', self.close_profile)
        self.profile_window.bind('<KeyRelease>', lambda event: setattr(self, 'profile_dirty', True), add='+')
        self.root.configure(menu=self.menubar)
        self.initial_size_calibrated = False

        def mapped(event):
            if event.widget is self.root and (not self.initial_size_calibrated):
                self.initial_size_calibrated = True
                self.root.after_idle(self.calibrate_content_size)
        self.root.bind('<Map>', mapped, add='+')
        for index in range(4):
            self.menubar.entryconfigure(index, underline=1 if index == 3 else 0)
        for parent in (0, 1):
            menu = self.root.nametowidget(self.menubar.entrycget(parent, 'menu'))
            for index in range((menu.index('end') or 0) + 1):
                if menu.type(index) != 'command':
                    continue
                label = menu.entrycget(index, 'label')
                shortcut = 'Ctrl+N' if label.startswith(tr('ui_fadcf2d5a3d5')) else 'Ctrl+A' if label == tr('ui_8366d72b4661') else tr('ui_717e1e93af99') if label.startswith(tr('ui_4bd4ea834263')) else ''
                if shortcut:
                    menu.entryconfigure(index, accelerator=shortcut)
        view = self.root.nametowidget(self.menubar.entrycget(2, 'menu'))
        for label, mode in [(tr('ui_0d7f97c38367'), 'dark'), (tr('ui_21f72c3cc4b9'), 'light'), (tr('ui_cdb5c53c91f0'), 'system')]:
            view.add_radiobutton(label=label, variable=self.theme_choice, value=mode, command=lambda m=mode: self.choose_theme(m))
        view.add_command(label=tr('ui_b489c2383f34'), command=self.column_dialog)
        view.add_command(label=tr('ui_318f59b9332a'), command=self.first_run)
        self.table.bind('<Control-a>', lambda e: (self.select_all(), 'break')[-1])
        self.table.bind('<ButtonPress-1>', self.begin_drag, add='+')
        self.table.bind('<B1-Motion>', self.drag_select, add='+')
        self.table.bind('<ButtonRelease-1>', lambda e: self.persist_columns(), add='+')
        for col in self.table['columns']:
            self.table.heading(col, command=lambda c=col: self.sort_by(c))
        for key, action in [('<Control-n>', self.manual_dialog), ('<Control-f>', self.show_search), ('<Control-Return>', self.launch), ('<Control-r>', lambda: self.action('/reconnect')), ('<Control-comma>', self.show_config), ('<Control-k>', self.command_palette), ('<F5>', self.refresh)]:
            self.root.bind(key, lambda event, a=action: (a(), 'break')[-1])
        self.table.bind('<Delete>', lambda event: self.remove())
        self.banner = tk.Frame(self.workspace)
        self.banner_text = tk.Label(self.banner, anchor='w', justify='left')
        self.banner_text.pack(side='left', fill='x', expand=True, padx=8, pady=4)
        self.banner_action = tk.Button(self.banner, text=tr('ui_95d2c5ee416c'), command=self.undo_remove)
        self.banner_action.pack(side='right', padx=4)
        self.empty = tk.Frame(self.table)
        tk.Label(self.empty, text='＋', font=(theme.FONT, 22)).pack()
        tk.Label(self.empty, text=tr('ui_3f30d45a34e1'), font=(theme.FONT, 11, 'bold')).pack(pady=4)
        self.button(self.empty, tr('ui_b96eb457a37b'), self.manual_dialog, True).pack(pady=4)
        self.destination_error = tk.Label(self.place.master, text='', anchor='w', font=(theme.FONT, 8))
        self.destination_error.grid(row=5, column=0, sticky='new', pady=3)
        self.place.bind('<KeyRelease>', lambda event: self.validate_destination())
        self.place.bind('<<Paste>>', lambda event: self.root.after_idle(self.validate_destination))
        self.table.bind('<Motion>', self.row_tooltip, add='+')
        self.table.bind('<Leave>', lambda event: self.hide_tooltip())
        self.tip = None
        self.tip_after = None
        self.footer_selection = self.label(self.metrics[0].master, tr('ui_2e5298fd2ee8'), size=8, color=self.palette['muted'])
        self.footer_selection.pack(side='right')
        self.place.bind('<Down>', self.destination_history)
        for button in (self.open_button, self.reconnect_button):
            self.install_tooltip(button, lambda b=button: getattr(b, '_sk_reason', '') or b.cget('text'))
        self.install_tooltip(self.place, tr('ui_c7d0f2b4503e'))
        for variable in (self.start_windows, self.companion_enabled, self.start_weblauncher, self.start_accounts):
            variable.trace_add('write', lambda *args: setattr(self, 'ui_config_dirty', True))
        self.statusbar = tk.Frame(self.workspace)
        self.statusbar.pack(before=self.tabs, side='bottom', fill='x', pady=(2, 0))
        self.version_chip = self.label(self.statusbar, tr('ui_4176882510c1'), size=8, color=self.palette['muted'])
        self.version_chip.pack(side='left', padx=(0, 8))
        self.button(self.statusbar, tr('ui_040835e837a6'), self.diagnostic).pack(side='left', padx=2)
        self.update_chip = self.button(self.statusbar, tr('ui_cfeb11c07f77'), self.updates)
        self.update_chip.pack(side='right')
        self.last_check = '—'
        self.icons = {}
        self.table.configure(show=tr('ui_018d185002bd'))
        self.table.column('#0', width=round(36 * self.ui_scale), stretch=False, minwidth=32)
        self.load_ui_icons()
        self.apply_theme('dark')
        self.init_refinement()

        def load():
            value = ui_preferences.load()
            detected = theme.windows_theme()
            self.events.put((self.preferences_loaded, (value, detected), None))
        Thread(target=load, daemon=True).start()

    def preferences_loaded(self, value, error):
        prefs, system = value
        self.ui_prefs = prefs
        self.system_theme = system
        self.minimize_option.set(bool(prefs.get('minimizeToTray', True)))
        self.notify_option.set(bool(prefs.get('notifications', False)))
        self.theme_choice.set(prefs.get('theme', 'dark'))
        self.apply_theme(system if self.theme_choice.get() == 'system' else self.theme_choice.get())
        columns = [c for c in prefs.get('columns', []) if c in self.table['columns']]
        if columns:
            self.table.configure(displaycolumns=columns)
        for col, width in prefs.get('widths', {}).items():
            if col in self.table['columns'] and type(width) is int and (45 <= width <= 1200):
                self.table.column(col, width=width)
        self.user_widths = dict(prefs.get('manualWidths', {}))
        self.render_refinement()
        self.validate_destination()
        if not prefs.get('onboarded') and (not self.rows):
            self.show_banner(tr('ui_5671c8725752'), self.first_run, tr('ui_8d04ebe0bc07'))
        self.root.after(10000, self.poll_windows_theme)

    def poll_windows_theme(self):
        if self.theme_choice.get() == 'system':

            def worker():
                value = theme.windows_theme()
                self.events.put((lambda value, error: self.apply_theme(value), value, None))
            Thread(target=worker, daemon=True).start()
        self.root.after(10000, self.poll_windows_theme)

    def persist_ui(self):
        snapshot = json.loads(json.dumps(self.ui_prefs))
        revision = time.monotonic_ns()

        def worker():
            try:
                ui_preferences.save(snapshot, revision)
            except OSError:
                self.events.put((lambda value, error: self.notice.config(text=tr('ui_af2e99d571cf')), None, None))
        Thread(target=worker, daemon=True).start()

    def choose_theme(self, mode):
        self.ui_prefs['theme'] = mode
        self.theme_choice.set(mode)
        self.apply_theme(getattr(self, 'system_theme', 'dark') if mode == 'system' else mode)
        self.persist_ui()

    def apply_theme(self, mode):
        self.palette = dict(theme.PALETTES.get(mode, theme.DARK))
        theme.apply(self.root, self.palette, getattr(self, 'ui_scale', 1.0))
        if hasattr(self, 'table'):
            for name, color in [('even', 'surface'), ('odd', 'alternate'), ('online', 'success'), ('offline', 'muted'), ('error', 'error'), ('block', 'warning')]:
                self.table.tag_configure(name, **{'background' if name in ('even', 'odd') else 'foreground': self.palette[color]})
        if getattr(self, 'icons', None):
            self.refresh_icon_rows()
        if hasattr(self, 'destination_error'):
            self.destination_error.config(fg=self.palette['error'])
        self.style_refinement()

    def persist_columns(self):
        self.ui_prefs['columns'] = list(self.table['displaycolumns'])
        self.ui_prefs['widths'] = {col: self.table.column(col, 'width') for col in self.table['columns']}
        self.persist_ui()

    def column_dialog(self):
        body = self.dialog(tr('ui_1d109f1da215'))
        order = list(self.table['displaycolumns'])
        all_columns = list(self.table['columns'])
        order += [col for col in all_columns if col not in order]
        box = tk.Listbox(body, height=7, exportselection=False)
        box.pack(fill='x', pady=8)
        variables = {col: tk.BooleanVar(value=col in self.table['displaycolumns']) for col in order}
        for col in order:
            tk.Checkbutton(body, text=self.table.heading(col, 'text'), variable=variables[col]).pack(anchor='w')

        def render():
            box.delete(0, 'end')
            for col in order:
                box.insert('end', self.table.heading(col, 'text'))

        def move(delta):
            selected = box.curselection()
            if selected and 0 <= selected[0] + delta < len(order):
                i = selected[0]
                order[i], order[i + delta] = (order[i + delta], order[i])
                render()
                box.selection_set(i + delta)
        render()
        buttons = tk.Frame(body)
        buttons.pack(fill='x', pady=8)
        self.button(buttons, tr('ui_4d0bb340a011'), lambda: move(-1)).pack(side='left', padx=4)
        self.button(buttons, tr('ui_9d88821f1448'), lambda: move(1)).pack(side='left', padx=4)

        def save():
            cols = [col for col in order if variables[col].get()]
            if 'account' not in cols:
                cols.insert(0, 'account')
            self.table.configure(displaycolumns=cols)
            self.persist_columns()
            body.winfo_toplevel().destroy()
        self.button(body, tr('ui_e056840d01a0'), save, True).pack(anchor='w')

    def sort_by(self, column):
        self.sort_reverse = not self.sort_reverse if self.sort_column == column else False
        self.sort_column = column
        for name in self.table['columns']:
            text = self.table.heading(name, 'text').rstrip(' ↑↓')
            self.table.heading(name, text=text + (' ↓' if self.sort_reverse else ' ↑') if name == column else text)
        self.filter_accounts()

    def row_order(self):
        keys = {'account': 'username', 'age': 'age', 'connected': 'connected', 'server': 'jobId', 'retry': 'attempts', 'status': 'status'}
        key = keys.get(self.sort_column, 'username')

        def value(item):
            row = item[1]
            v = row.get(key)
            return (v is None, v if isinstance(v, (int, float)) else str(v or '').casefold())
        return sorted(self.rows.items(), key=value, reverse=self.sort_reverse)

    def begin_drag(self, event):
        if self.table.identify_region(event.x, event.y) == 'cell':
            self.drag_start = self.table.identify_row(event.y)
        else:
            self.drag_start = None

    def drag_select(self, event):
        target = self.table.identify_row(event.y)
        rows = list(self.table.get_children())
        if self.drag_start in rows and target in rows:
            i, j = sorted((rows.index(self.drag_start), rows.index(target)))
            self.table.selection_set(rows[i:j + 1])

    def validate_destination(self):
        raw = self.place.get().strip()
        valid = raw.isascii() and raw.isdigit() and (0 < int(raw) < 10 ** 16)
        self.place.config(highlightbackground=self.palette['border'] if valid or not raw else self.palette['error'])
        self.destination_error.config(text='' if valid or not raw else tr('ui_bcc11d82e6c1'))
        reason = tr('ui_d01b59f8c055') if not self.ids() else tr('ui_56087a9cfb50') if not valid else tr('ui_44b13386cdc7') if self.pending else ''
        for button in (self.open_button, self.reconnect_button):
            button.config(state='disabled' if reason else 'normal')
            button._sk_reason = reason
        return valid

    def show_banner(self, text, action=None, label=tr('ui_bf763df73110')):
        self.banner_text.config(text=text, bg=self.palette['surface'], fg=self.palette['text'])
        self.banner_action.config(text=label, command=action or (lambda: self.banner.pack_forget()))
        self.banner.pack(before=self.tabs, fill='x', pady=(0, 4))
        self.apply_theme('light' if self.palette == theme.LIGHT else 'dark')

    def schedule_remove(self, ids):
        if self.removal_timer:
            self.notice.config(text=tr('ui_e90a2d3a2da3'))
            return
        selected = list(ids)

        def commit():
            self.removal_timer = None
            self.banner.pack_forget()
            self.run('/remove', {'ids': selected})
        self.removal_timer = self.root.after(6000, commit)
        self.show_banner(tr('ui_4c964509b845', p0=len(ids)), self.undo_remove, tr('ui_95d2c5ee416c'))

    def undo_remove(self):
        if self.removal_timer:
            self.root.after_cancel(self.removal_timer)
        self.removal_timer = None
        self.banner.pack_forget()
        self.notice.config(text=tr('ui_44a6acf87d9d'))

    def close_selected(self):
        ids = self.ids()
        if ids and messagebox.askyesno(tr('ui_f00fa760c1ff'), tr('ui_e9320a00da98'), parent=self.root):
            self.run('/close', {'ids': ids})

    def command_palette(self):
        body = self.dialog(tr('ui_c1c872c18aa7'))
        query = tk.StringVar()
        field = self.entry(body)
        field.config(textvariable=query)
        field.pack(fill='x', pady=8)
        actions = [(tr('ui_b96eb457a37b'), self.manual_dialog), (tr('ui_535bc78c9148'), self.launch), (tr('ui_64d04acedf37'), lambda: self.action('/reconnect')), (tr('ui_871f24c4cdaf'), self.show_config), (tr('ui_eb4d4196e7cc'), self.heartbeat), (tr('ui_040835e837a6'), self.diagnostic), (tr('ui_cfeb11c07f77'), self.updates), (tr('ui_bea29e92ac2b'), self.history), (tr('ui_318f59b9332a'), self.first_run)]
        box = tk.Listbox(body, height=10)
        box.pack(fill='both', expand=True)
        matched = []

        def update(*args):
            matched[:] = [(name, action) for name, action in actions if query.get().casefold() in name.casefold()]
            box.delete(0, 'end')
            for name, _ in matched:
                box.insert('end', name)

        def execute(event=None):
            if box.curselection():
                action = matched[box.curselection()[0]][1]
                body.winfo_toplevel().destroy()
                action()
        query.trace_add('write', update)
        box.bind('<Double-1>', execute)
        box.bind('<Return>', execute)
        update()
        field.focus_set()

    def first_run(self):
        body = self.dialog(tr('ui_318f59b9332a'))
        self.label(body, tr('ui_630299cf4c17'), color=self.palette['muted']).pack(anchor='w', pady=4)
        for number, title, description, action in [('01', tr('ui_b96eb457a37b'), tr('ui_4d93ea693951'), self.manual_dialog), ('02', tr('ui_f2dc1a1b556c'), tr('ui_173a6a44d98b'), self.toggle_controls), ('03', tr('ui_776841b4216d'), tr('ui_9d1591c23be4'), self.heartbeat), ('04', tr('ui_c24ce0a9687f'), tr('ui_be4c5a0819dd'), self.connection_details)]:
            card = tk.Frame(body, padx=12, pady=8)
            card.pack(fill='x', pady=4)
            self.label(card, number + '  ' + title, bold=True).pack(anchor='w')
            self.label(card, description, wrap=490, color=self.palette['muted']).pack(anchor='w', pady=4)
            self.button(card, title, action).pack(anchor='w')

        def finish():
            self.ui_prefs['onboarded'] = True
            self.persist_ui()
            body.winfo_toplevel().destroy()
        self.button(body, tr('ui_c5500ee5cec4'), finish).pack(anchor='w', pady=8)

    def hide_tooltip(self):
        if self.tip_after:
            self.root.after_cancel(self.tip_after)
            self.tip_after = None
        if self.tip:
            self.tip.destroy()
            self.tip = None

    def row_tooltip(self, event):
        self.hide_tooltip()
        identity = self.table.identify_row(event.y)
        if not identity:
            return
        row = self.rows.get(identity, {})
        text = self.truncated_cell(event)
        if not text:
            return
        x, y = (event.x_root, event.y_root)

        def show():
            self.tip = tk.Toplevel(self.root)
            self.tip.overrideredirect(True)
            self.tip.geometry(f'+{x + 12}+{y + 14}')
            tk.Label(self.tip, text=text, bg=self.palette['surface'], fg=self.palette['text'], padx=8, pady=6).pack()
        self.tip_after = self.root.after(650, show)

    def build_ui_sections(self, general, reconnection, appearance, advanced):
        self.theme_choice = tk.StringVar(value='dark')
        self.label(general, tr('ui_915433de0f6c'), size=14, bold=True).pack(anchor='w', padx=16, pady=12)
        self.label(general, tr('ui_b5522d69bdcb'), wrap=630).pack(anchor='w', padx=16, pady=4)
        self.minimize_option = tk.BooleanVar(value=True)

        def minimize():
            self.ui_prefs['minimizeToTray'] = self.minimize_option.get()
            self.persist_ui()
        tk.Checkbutton(general, text=tr('ui_120f4fd08e81'), variable=self.minimize_option, command=minimize).pack(anchor='w', padx=16, pady=8)
        self.button(general, tr('ui_e4aab1a357fe'), self.first_run).pack(anchor='w', padx=16, pady=8)
        self.notify_option = tk.BooleanVar(value=False)

        def notify():
            self.ui_prefs['notifications'] = self.notify_option.get()
            self.persist_ui()
        tk.Checkbutton(general, text=tr('ui_edf8010ccd34'), variable=self.notify_option, command=notify).pack(anchor='w', padx=16, pady=6)
        self.label(reconnection, tr('ui_c0e8b360a6b3'), size=14, bold=True).pack(anchor='w', padx=16, pady=12)
        self.label(reconnection, tr('ui_8cc542df4c1a'), wrap=630).pack(anchor='w', padx=16, pady=8)
        self.button(reconnection, tr('ui_ffb6856e5ba3'), self.toggle_controls, True).pack(anchor='w', padx=16, pady=8)
        self.label(appearance, tr('ui_8ecb9f1828bd'), size=14, bold=True).pack(anchor='w', padx=16, pady=12)
        for title, mode in [(tr('ui_0d7f97c38367'), 'dark'), (tr('ui_21f72c3cc4b9'), 'light'), (tr('ui_cdb5c53c91f0'), 'system')]:
            tk.Radiobutton(appearance, text=title, variable=self.theme_choice, value=mode, command=lambda m=mode: self.choose_theme(m)).pack(anchor='w', padx=16, pady=6)
        self.button(appearance, tr('ui_e6ead528437c'), lambda: self.choose_theme('dark')).pack(anchor='w', padx=16, pady=12)
        self.button(appearance, tr('ui_faa03560c030'), self.column_dialog).pack(anchor='w', padx=16, pady=8)
        self.label(advanced, tr('ui_d73dd1539db1'), size=14, bold=True).pack(anchor='w', padx=16, pady=12)
        for title, action in [(tr('ui_41c95b03ecdf'), self.diagnostic), (tr('ui_7e96f97a3fbf'), self.auth_check), (tr('ui_fef9495ee515'), self.history), (tr('ui_cfeb11c07f77'), self.updates), (tr('ui_eb4d4196e7cc'), self.heartbeat)]:
            self.button(advanced, title, action).pack(anchor='w', padx=16, pady=5)

    def find_setting(self, query):
        query = query.strip().casefold()
        if not query:
            return

        def texts(widget):
            result = []
            try:
                result.append(widget.cget('text'))
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                result.extend(texts(child))
            return result
        for tab in self.config_sections.tabs():
            widget = self.root.nametowidget(tab)
            if query in ' '.join(texts(widget)).casefold() or query in self.config_sections.tab(tab, 'text').casefold():
                self.config_sections.select(tab)
                return

    def close_config(self):
        if self.ui_config_dirty and (not messagebox.askyesno(tr('ui_c068d5ebc43c'), tr('ui_3f1124bfe4ec'), parent=self.settings_window)):
            return
        self.ui_config_dirty = False
        self.settings_window.withdraw()

    def mark_config_clean(self):
        self.ui_config_dirty = False

    def add_tray_actions(self, hide):
        self.tray_hide = hide

    def reconnect_all(self):
        self.search.set('')
        self.state_filter.set(tr('ui_8a3c3440366a'))
        self.filter_accounts()
        self.select_all()
        self.action('/reconnect')

    def icon_key(self, row):
        return {'loading':'busy','block':'warning'}.get(semantic_state(row),semantic_state(row))

    def load_ui_icons(self):
        from pathlib import Path
        import sys
        assets = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
        size = 24 if self.ui_scale >= 1.5 else 20 if self.ui_scale >= 1.25 else 16
        target_size=round(16*self.ui_scale)

        def load():
            from PIL import Image
            import io
            values = {}
            for mode in ('dark', 'light'):
                for state in ('online', 'offline', 'busy', 'error', 'warning'):
                    try:
                        source='busy' if state=='warning' else state
                        image=Image.open(assets / 'artwork' / 'icons' / f'{mode}-{source}-{size}.png').convert('RGBA')
                        if state=='warning':
                            alpha=image.getchannel('A')
                            image=Image.new('RGBA',image.size,theme.PALETTES[mode]['warning']);image.putalpha(alpha)
                        image=image.resize((target_size,target_size),Image.Resampling.LANCZOS)
                        out=io.BytesIO();image.save(out,format='PNG');values[mode,state]=out.getvalue()
                    except OSError:
                        pass
            try:
                values['brand'] = (assets / 'artwork' / 'portrait.png').read_bytes()
            except OSError:
                pass
            self.events.put((self.icons_ready, values, None))
        Thread(target=load, daemon=True).start()

    def icons_ready(self, values, error):
        self.icons = {key: tk.PhotoImage(master=self.root, data=data, format='png') for key, data in values.items()}
        if 'brand' in self.icons:
            self.root.iconphoto(True, self.icons['brand'])
        self.refresh_icon_rows()
        self.refinement_icons_ready()

    def refresh_icon_rows(self):
        mode = 'light' if self.palette == theme.LIGHT else 'dark'
        for identity, row in self.rows.items():
            image = self.icons.get((mode, self.icon_key(row)))
            if image:
                self.table.item(identity, image=image)

    def destination_history(self, event=None):
        menu = tk.Menu(self.root, tearoff=False)
        for place in self.ui_prefs.get('destinations', []):

            def select(value=place):
                self.place.delete(0, 'end')
                self.place.insert(0, str(value))
                self.validate_destination()
            menu.add_command(label=str(place), command=select)
        if not self.ui_prefs.get('destinations'):
            menu.add_command(label=tr('ui_7e06dcb79642'), state='disabled')
        menu.tk_popup(self.place.winfo_rootx(), self.place.winfo_rooty() + self.place.winfo_height())
        menu.grab_release()
        return 'break'

    def install_tooltip(self, widget, text):

        def enter(event):
            self.hide_tooltip()

            def show():
                value = text() if callable(text) else text
                if not value:
                    return
                self.tip = tk.Toplevel(self.root)
                self.tip.overrideredirect(True)
                self.tip.geometry(f'+{event.x_root + 12}+{event.y_root + 14}')
                tk.Label(self.tip, text=value, bg=self.palette['surface'], fg=self.palette['text'], padx=8, pady=6, wraplength=300, justify='left').pack()
            self.tip_after = self.root.after(500, show)
        widget.bind('<Enter>', enter, add='+')
        widget.bind('<Leave>', lambda event: self.hide_tooltip(), add='+')

    def presentation_error(self, code):
        return {279: tr('ui_ef352caf7fcf'), 773: tr('ui_81afd13aac1e'), 403: tr('ui_f7ddd2bce342'), 415: tr('ui_8abf7910dd15'), 429: tr('ui_7f74710ed8f2')}.get(code, '')

    def reset_section(self, name):
        fields = {tr('ui_227221a807e9'): [(self.companion_path, ''), *((field, '10' if key == 'webLauncherDelay' else '20') for key, field in self.start_delays.items())], tr('ui_6291b22cc048'): [(self.rejoin_delay, '20'), (self.max_attempts, '3'), (self.profile_fps, '10'), (self.dimensions['limit'], '2'), (self.dimensions['width'], '320'), (self.dimensions['height'], '240')], tr('ui_fe22d91274fc'): [(self.opt_fps, '10'), (self.opt_folder, '')]}
        for field, value in fields.get(name, []):
            field.delete(0, 'end')
            field.insert(0, value)
        if name == tr('ui_227221a807e9'):
            for variable in (self.start_windows, self.companion_enabled, self.start_accounts):
                variable.set(False)
            self.start_weblauncher.set(True)
        if name == tr('ui_8ecb9f1828bd'):
            self.choose_theme('dark')
        if name == tr('ui_b6748d4ef8da'):
            self.minimize_option.set(True)
            self.notify_option.set(False)
            self.ui_prefs.update(minimizeToTray=True, notifications=False)
            self.persist_ui()
        self.ui_config_dirty = bool(fields.get(name))
        self.notice.config(text=tr('ui_f0b99c702350'))

    def show_timeline(self, body, steps):
        for title, detail, status in steps:
            card = tk.Frame(body, padx=10, pady=6)
            card.pack(fill='x', pady=3)
            symbol = '✓' if status is True else '!' if status is False else '○'
            color = self.palette['success'] if status is True else self.palette['error'] if status is False else self.palette['muted']
            self.label(card, symbol + '  ' + title, bold=True, color=color).pack(anchor='w')
            self.label(card, detail, wrap=520, color=self.palette['muted']).pack(anchor='w', pady=2)

    def calibrate_content_size(self, attempt=0):
        width, height = self.initial_content_size
        actual = (self.root.winfo_width(), self.root.winfo_height())
        if actual == (width, height) or attempt >= 3:
            return
        import re
        match = re.match('(\\d+)x(\\d+)', self.root.geometry())
        if match:
            requested_width, requested_height = map(int, match.groups())
            self.root.geometry(f'{requested_width + width - actual[0]}x{requested_height + height - actual[1]}')
            self.root.after_idle(lambda: self.calibrate_content_size(attempt + 1))

    @staticmethod
    def row_has_error(row):
        status = row.get('status', '').casefold()
        return bool(row.get('errorCode')) or any((word in status for word in ('erro', 'recusad', 'falhou')))

    def update_footer(self):
        self.render_footer()
        if hasattr(self, 'footer_selection'):
            errors = sum((self.row_has_error(row) for row in self.rows.values()))
            self.footer_selection.config(text=tr('ui_df71a54f3933', p0=len(self.ids()), p1=errors))

    def close_profile(self):
        if self.profile_dirty:
            if not messagebox.askyesno(tr('ui_c068d5ebc43c'), tr('ui_15eb9e738bf3'), parent=self.profile_window):
                return
            self.profile_dirty = False
            self.load_profile()
        self.profile_window.withdraw()
