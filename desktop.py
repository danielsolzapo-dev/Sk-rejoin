"""Desktop interface for the local Rejoin Desk service."""
from ui_text import tr
import json
import os
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
import accounts
import theme
from ui_workspace import WorkspaceUI
from queue import Empty, Queue
from threading import Event, Thread
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
BG, PANEL, LINE, TEXT, MUTED, MINT = ('#242424', '#2d2d2d', '#505050', '#eeeeee', '#bcbcbc', '#82b5f2')

class Desktop(WorkspaceUI):

    def __init__(self, root, port, key, assets, settings):
        self.root, self.port, self.key = (root, port, key)
        self.events = Queue()
        self.refreshing = False
        self.rows = {}
        self.state = {}
        self.pending = False
        self.economy = bool(settings.get('economy'))
        root.title(tr('ui_4176882510c1'))
        if (assets / 'artwork' / 'sk.ico').exists():
            root.iconbitmap(str(assets / 'artwork' / 'sk.ico'))
        scale = max(1.0, root.winfo_fpixels('1i') / 96)
        width, height = (round(784 * scale), round(301 * scale))
        width = min(width, root.winfo_screenwidth() - 40)
        height = min(height, root.winfo_screenheight() - 80)
        root.geometry(f'{width}x{height}+20+20')
        root.minsize(round(720 * scale), round(285 * scale))
        root.configure(bg=BG)
        root.option_add('*Font', ('Segoe UI', 9))
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure(tr('ui_d78dca84fb22'), background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=20, borderwidth=1, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, font=('Segoe UI', 9))
        style.configure('Treeview.Heading', background='#383838', foreground=TEXT, relief='raised', padding=(4, 3), font=('Segoe UI', 9))
        style.map(tr('ui_d78dca84fb22'), background=[('selected', '#3b587b')], foreground=[('selected', '#ffffff')])
        style.configure('TNotebook', background=BG, borderwidth=0, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
        style.configure('Workspace.TNotebook', background=BG, borderwidth=0, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
        style.configure('TNotebook.Tab', background='#303030', foreground=TEXT, padding=(15, 5))
        style.map('TNotebook.Tab', background=[('selected', '#464646')], foreground=[('selected', TEXT)])
        style.configure('TCombobox', background=LINE, fieldbackground='#202020', foreground=TEXT, arrowcolor=TEXT, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, padding=3)
        style.map('TCombobox', fieldbackground=[('readonly', '#202020')], foreground=[('readonly', TEXT)])
        for direction in (tr('ui_4b937cc841d8'), tr('ui_4f57a1ce99e6')):
            style.configure(direction + '.TScrollbar', background='#454545', troughcolor=BG, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, arrowsize=13, borderwidth=0)
        self.compact = True
        self.workspace = workspace = tk.Frame(root, bg=BG)
        workspace.pack(fill='both', expand=True, padx=6, pady=4)
        menubar = tk.Menu(root, tearoff=False, bg=PANEL, fg=TEXT, activebackground='#3b587b', activeforeground='white')
        accounts_menu = tk.Menu(menubar, tearoff=False, bg=PANEL, fg=TEXT)
        for title, action in ((tr('ui_9e77511a41de'), self.password_dialog), (tr('ui_3b85b826d713'), self.import_dialog), (tr('ui_8366d72b4661'), self.select_all), (tr('ui_b6ae7ef07df1'), self.remove)):
            accounts_menu.add_command(label=title, command=action)
        accounts_menu.add_separator()
        accounts_menu.add_command(label=tr('ui_8041ee4c59fa'), command=root.destroy)
        menubar.add_cascade(label=tr('ui_88235861896f'), menu=accounts_menu)
        utilities = tk.Menu(menubar, tearoff=False, bg=PANEL, fg=TEXT)
        for title, action in ((tr('ui_eb4d4196e7cc'), self.heartbeat), (tr('ui_bea29e92ac2b'), self.history), (tr('ui_7e96f97a3fbf'), self.auth_check), (tr('ui_040835e837a6'), self.diagnostic), (tr('ui_7c87e63a566b'), self.fps_dialog), (tr('ui_05744e4e7ae0'), self.show_optimization), (tr('ui_cfeb11c07f77'), self.updates)):
            utilities.add_command(label=title, command=action)
        menubar.add_cascade(label=tr('ui_04bf24f351a0'), menu=utilities)
        view_menu = tk.Menu(menubar, tearoff=False, bg=PANEL, fg=TEXT)
        view_menu.add_command(label=tr('ui_1326845d5435'), command=self.toggle_compact)
        view_menu.add_command(label=tr('ui_782a015bd0fa'), command=self.toggle_controls)
        self.detail_columns = tk.BooleanVar(value=False)
        view_menu.add_checkbutton(label=tr('ui_b430235815cd'), variable=self.detail_columns, command=self.set_list_columns)
        menubar.add_cascade(label=tr('ui_46b613becea0'), menu=view_menu)
        menubar.add_command(label=tr('ui_871f24c4cdaf'), command=self.show_config)
        self.menubar = menubar
        style.layout('Workspace.TNotebook.Tab', [])
        self.tabs = ttk.Notebook(workspace, style='Workspace.TNotebook')
        self.tabs.pack(fill='both', expand=True)
        sessions = tk.Frame(self.tabs, bg=BG)
        self.settings_window = tk.Toplevel(root, bg=BG)
        self.settings_window.withdraw()
        self.settings_window.title(tr('ui_825308c10694'))
        self.settings_window.geometry(f'{round(760 * scale)}x{round(600 * scale)}')
        self.settings_window.transient(root)
        self.settings_window.protocol('WM_DELETE_WINDOW', self.close_config)
        config = tk.Frame(self.settings_window, bg=BG)
        config.pack(fill='both', expand=True)
        self.tabs.add(sessions, text=tr('ui_88235861896f'))
        self.build_config(config, settings)
        self.settings_window.bind('<KeyRelease>', lambda event: setattr(self, 'ui_config_dirty', True), add='+')
        self.notice = self.label(workspace, tr('ui_5de7f226e47e'), size=8, color=MUTED, wrap=0)
        self.notice.pack(before=self.tabs, side='bottom', fill='x', pady=(2, 0))
        self.toolbar = toolbar = tk.Frame(sessions, bg=BG)
        toolbar.pack(side='bottom', fill='x', pady=(3, 0))
        add_group = tk.Frame(toolbar, bg=BG)
        add_group.pack(side='left', padx=(0, 5))
        self.add_button = self.button(add_group, tr('ui_b96eb457a37b'), self.manual_dialog)
        self.add_button.pack(side='left')
        self.add_arrow = tk.Menubutton(add_group, text='▾', bg='#414141', fg=TEXT, activebackground='#555555', activeforeground=TEXT, relief='raised', bd=1, padx=5, pady=2, cursor='hand2', direction='above')
        self.add_arrow.pack(side='left')
        self.add_menu = tk.Menu(self.add_arrow, tearoff=False, bg=PANEL, fg=TEXT)
        self.add_menu.add_command(label=tr('ui_d8cf60d31b95'), command=self.manual_dialog)
        self.add_menu.add_command(label=tr('ui_e8bfe534e6f3'), command=self.password_dialog)
        self.add_menu.add_command(label=tr('ui_524cf50b5df5'), command=self.import_dialog)
        self.add_arrow.configure(menu=self.add_menu)
        for title, action in ((tr('ui_4bd4ea834263'), self.remove), (tr('ui_8366d72b4661'), self.select_all), (tr('ui_6dd94e23a8f9'), self.connection_details)):
            self.button(toolbar, title, action).pack(side='left', padx=(0, 5))
        self.button(toolbar, tr('ui_871f24c4cdaf'), self.show_config).pack(side='right')
        metrics = tk.Frame(sessions, bg=BG)
        metrics.pack(side='bottom', fill='x', pady=(2, 0))
        self.metrics = []
        for title in (tr('ui_1c15737c2a66'), tr('ui_fa449d714a0b'), tr('ui_b288a0724ec3')):
            self.label(metrics, title, size=8, color=MUTED).pack(side='left', padx=(0, 4))
            value = self.label(metrics, '—', size=8, bold=True)
            value.pack(side='left', padx=(0, 20))
            self.metrics.append(value)
        content = tk.Frame(sessions, bg=BG)
        content.pack(fill='both', expand=True)
        content.columnconfigure(0, weight=1, minsize=350)
        content.rowconfigure(0, weight=1)
        accounts_panel = tk.Frame(content, bg=BG)
        accounts_panel.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        filters = tk.Frame(accounts_panel, bg=BG)
        self.filters_frame = filters
        self.label(filters, tr('ui_a62405e2cefb'), size=9).pack(side='left', padx=(0, 6))
        self.search = tk.StringVar()
        self.search_field = self.entry(filters)
        self.search_field.configure(textvariable=self.search)
        self.search_field.pack(side='left', fill='x', expand=True, ipady=3, padx=(0, 6))
        self.state_filter = tk.StringVar(value=tr('ui_8a3c3440366a'))
        chooser = ttk.Combobox(filters, textvariable=self.state_filter, state='readonly', width=13, values=(tr('ui_8a3c3440366a'), tr('ui_0c661608c587'), tr('ui_b419880b4c70'), tr('ui_09763d9fa8a7'), tr('ui_0748e2f5bdcf'), tr('ui_ead8eeb4740e')))
        chooser.pack(side='right')
        info = tk.Frame(accounts_panel, bg=BG)
        self.search_hint = self.label(info, tr('ui_9f7234ef3411'), size=8, color=MUTED)
        self.search_hint.pack(side='left')
        self.selection_info = self.label(info, tr('ui_2e5298fd2ee8'), size=8, color=MUTED)
        self.selection_info.pack(side='right')
        self.search.trace_add('write', lambda *args: self.filter_accounts())
        chooser.bind('<<ComboboxSelected>>', lambda event: self.filter_accounts())
        table_shell = tk.Frame(accounts_panel, bg=BG)
        table_shell.pack(fill='both', expand=True)
        self.table = ttk.Treeview(table_shell, columns=('account', 'status', 'age', 'connected', 'retry', 'server'), displaycolumns=('account', 'status', 'age'), show='headings', selectmode='extended')
        for column, name, size in (('account', tr('ui_4d07517575be'), 145), ('status', tr('ui_87cf2a843e2e'), 220), ('age', tr('ui_b76cf4bf00f0'), 50), ('connected', tr('ui_899658e27a6c'), 70), ('retry', tr('ui_6291b22cc048'), 110), ('server', tr('ui_07728991147d'), 100)):
            self.table.heading(column, text=name, anchor='w')
            self.table.column(column, width=size, minwidth=100 if column == 'status' else 50, stretch=column == 'status')
        scrollbar = ttk.Scrollbar(table_shell, orient='vertical', command=self.table.yview)
        scrollbar.pack(side='right', fill='y')
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(fill='both', expand=True)
        horizontal = ttk.Scrollbar(accounts_panel, orient='horizontal', command=self.table.xview)
        horizontal.pack(before=table_shell, side='bottom', fill='x')
        self.table.configure(xscrollcommand=horizontal.set)
        for tag, color in (('even', '#2d2d2d'), ('odd', '#292929')):
            self.table.tag_configure(tag, background=color)
        for tag, color in (('online', '#b4dbb6'), ('offline', '#bbbbbb'), ('error', '#ffa0a0'), ('block', '#e9ce8d')):
            self.table.tag_configure(tag, foreground=color)
        self.selected_summary = self.label(accounts_panel, tr('ui_d3963af30024'), size=8, color=MUTED, wrap=650)
        self.table.bind('<<TreeviewSelect>>', self.account_selected)
        self.table.bind('<Double-1>', lambda event: self.connection_details())
        self.table.bind('<Button-3>', self.account_context)
        self.table.bind('<Control-c>', lambda event: self.copy_account('username'))
        compact_panel = tk.Frame(content, bg=PANEL, width=round(236 * scale), padx=8, pady=6)
        compact_panel.grid(row=0, column=1, sticky='nsew')
        compact_panel.grid_propagate(False)
        compact_panel.columnconfigure(0, weight=1)
        self.label(compact_panel, tr('ui_b54da73fef4e'), size=8, color=MUTED).grid(row=0, column=0, sticky='w')
        self.place = self.entry(compact_panel)
        self.place.insert(0, str(settings.get('place', '')))
        self.place.grid(row=1, column=0, sticky='ew', pady=(1, 4), ipady=1)
        buttons = tk.Frame(compact_panel, bg=PANEL)
        buttons.grid(row=2, column=0, sticky='ew')
        self.open_button=self.button(buttons,tr('ui_535bc78c9148'),self.launch,True)
        self.open_button.pack(side='left',fill='x',expand=True,padx=(0,4))
        self.reconnect_button=self.button(buttons,tr('ui_64d04acedf37'),lambda:self.action('/reconnect'))
        self.reconnect_button.pack(side='left',fill='x',expand=True)
        self.current_account = self.label(compact_panel, tr('ui_6feee3a0e9e0'), size=9, color=MINT, wrap=230)
        self.current_account.grid(row=3, column=0, sticky='ew', pady=(7, 3))
        self.compact_status = self.label(compact_panel, tr('ui_13d8fb6b1ef5'), size=8, color=MUTED, wrap=230)
        self.compact_status.grid(row=4, column=0, sticky='nw')
        compact_panel.rowconfigure(5, weight=1)
        self.button(compact_panel, tr('ui_c8e4eed80827'), self.toggle_controls).grid(row=6, column=0, sticky='ew', pady=(4, 3))
        bottom_tools = tk.Frame(compact_panel, bg=PANEL)
        bottom_tools.grid(row=7, column=0, sticky='ew')
        self.button(bottom_tools, tr('ui_eb4d4196e7cc'), self.heartbeat).pack(side='left', fill='x', expand=True, padx=(0, 3))
        tools = tk.Menubutton(bottom_tools, text=tr('ui_55e6a46a7716'), bg='#414141', fg=TEXT, relief='raised', bd=1, padx=6, pady=2, cursor='hand2')
        tools_menu = tk.Menu(tools, tearoff=False, bg=PANEL, fg=TEXT)
        for title, action in ((tr('ui_ac1bfe35e71d'), self.show_search), (tr('ui_e282d008dca7'), self.connection_details), (tr('ui_bea29e92ac2b'), self.history), (tr('ui_7e96f97a3fbf'), self.auth_check), (tr('ui_040835e837a6'), self.diagnostic), ('FPS', self.fps_dialog), (tr('ui_05744e4e7ae0'), self.show_optimization), (tr('ui_cfeb11c07f77'), self.updates), (tr('ui_8366d72b4661'), self.select_all), (tr('ui_6fc2e4220f00'), lambda: self.run('/cancel', {}))):
            tools_menu.add_command(label=title, command=action)
        tools_menu.add_separator()
        tools_menu.add_command(label=tr('ui_1326845d5435'), command=self.toggle_compact)
        tools_menu.add_checkbutton(label=tr('ui_b430235815cd'), variable=self.detail_columns, command=self.set_list_columns)
        tools.configure(menu=tools_menu)
        tools.pack(side='left', fill='x', expand=True)
        root.bind('<Control-f>', lambda event: self.show_search())
        self.profile_window = tk.Toplevel(root, bg=PANEL)
        self.profile_window.withdraw()
        self.profile_window.title(tr('ui_2feea7cfc5eb'))
        self.profile_window.geometry(f'{round(420 * scale)}x{round(600 * scale)}')
        self.profile_window.transient(root)
        self.profile_window.protocol('WM_DELETE_WINDOW', self.profile_window.withdraw)
        sidebar_shell = tk.Frame(self.profile_window, bg=PANEL)
        sidebar_shell.pack(fill='both', expand=True)
        self.controls_shell = sidebar_shell
        self.controls_visible = False
        canvas = tk.Canvas(sidebar_shell, bg=PANEL, highlightthickness=0)
        scroll = ttk.Scrollbar(sidebar_shell, orient='vertical', command=canvas.yview)
        scroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        sidebar = tk.Frame(canvas, bg=PANEL, padx=10, pady=8)
        item = canvas.create_window((0, 0), window=sidebar, anchor='nw')
        sidebar.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(item, width=e.width))
        self.label(sidebar, tr('ui_3dc3c8f5a52e'), size=12, bold=True).pack(anchor='w', pady=(0, 8))
        self.label(sidebar, tr('ui_1baf452d8d0f'), wrap=222).pack(anchor='w', pady=(8, 0))
        self.rejoin_delay = self.entry(sidebar)
        self.rejoin_delay.insert(0, str(settings.get('rejoin_delay', 20)))
        self.rejoin_delay.pack(fill='x', ipady=3)
        self.label(sidebar, tr('ui_7b6f5a9f8ef9'), color=MUTED).pack(anchor='w', pady=(8, 0))
        self.max_attempts = self.entry(sidebar)
        self.max_attempts.insert(0, str(settings.get('max_attempts', 3)))
        self.max_attempts.pack(fill='x', ipady=3)
        self.label(sidebar, tr('ui_c5e041e41a35'), color=MUTED, wrap=222).pack(anchor='w', pady=5)
        self.use_profiles = tk.BooleanVar(value=True)
        tk.Checkbutton(sidebar, text=tr('ui_8a058d7e8230'), variable=self.use_profiles, bg=PANEL, fg=TEXT, selectcolor=BG, activebackground=PANEL, activeforeground=TEXT).pack(anchor='w')
        self.dimensions = {}
        for key, label, default in (('limit', tr('ui_d917a6580f1a'), 2), ('width', tr('ui_d5d367932c3a'), 320), ('height', tr('ui_ffc3560fe2d9'), 240)):
            row = tk.Frame(sidebar, bg=PANEL)
            row.pack(fill='x', pady=(6, 0))
            self.label(row, label, color=MUTED).pack(side='left')
            entry = self.entry(row)
            entry.config(width=6)
            entry.insert(0, settings.get(key, default))
            entry.pack(side='right', ipady=3)
            self.dimensions[key] = entry
        self.label(sidebar, tr('ui_4d6ffe40c5f0'), color=MUTED, wrap=222).pack(anchor='w', pady=(8, 0))
        self.profile_fps = self.entry(sidebar)
        self.profile_fps.insert(0, '10')
        self.profile_fps.pack(fill='x', ipady=3)
        for title, action in ((tr('ui_a3b8cef37b6c'), self.save_selected_profile), (tr('ui_486d752a9a9e'), self.connection_details), (tr('ui_6fc2e4220f00'), lambda: self.run('/cancel', {})), (tr('ui_64feb1dcfd4a'), self.rejoin), (tr('ui_6398895fde8a'), lambda: self.action('/pause')), (tr('ui_8366d72b4661'), self.select_all), (tr('ui_b6ae7ef07df1'), self.remove)):
            self.button(sidebar, title, action, title == tr('ui_3ec2c6b05cf8')).pack(fill='x', pady=(4, 0))
        self.rejoin_status = self.label(sidebar, '', color=MUTED, wrap=222)
        self.rejoin_status.pack(anchor='w', pady=(12, 0))
        self.root.after(80, self.drain)
        self.init_workspace()
        self.startup_update_checked = False
        self.refresh()

    def build_config(self, parent, settings):
        options = ttk.Notebook(parent)
        self.config_sections = options
        options.pack(fill='both', expand=True)

        def scroll_page(title):
            shell = tk.Frame(options, bg=BG)
            options.add(shell, text=title)
            canvas = tk.Canvas(shell, bg=BG, highlightthickness=0)
            scrollbar = ttk.Scrollbar(shell, orient='vertical', command=canvas.yview)
            scrollbar.pack(side='right', fill='y')
            canvas.pack(side='left', fill='both', expand=True)
            canvas.configure(yscrollcommand=scrollbar.set)
            body = tk.Frame(canvas, bg=BG)
            item = canvas.create_window((0, 0), window=body, anchor='nw')
            body.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
            canvas.bind('<Configure>', lambda event: canvas.itemconfigure(item, width=event.width))
            canvas.bind('<MouseWheel>', lambda event: canvas.yview_scroll(-int(event.delta / 120), 'units'))
            body.bind('<MouseWheel>', lambda event: canvas.yview_scroll(-int(event.delta / 120), 'units'))
            return body
        general = scroll_page(tr('ui_b6748d4ef8da'))
        boot = scroll_page(tr('ui_227221a807e9'))
        reconnection = scroll_page(tr('ui_6291b22cc048'))
        performance = scroll_page(tr('ui_fe22d91274fc'))
        block_page = scroll_page(tr('ui_ead8eeb4740e'))
        launchers = scroll_page('WebLauncher')
        appearance = scroll_page(tr('ui_8ecb9f1828bd'))
        advanced = scroll_page(tr('ui_e0e8ba9a498d'))
        self.build_ui_sections(general, reconnection, appearance, advanced)
        search_bar = tk.Frame(parent, bg=BG)
        search_bar.pack(before=options, fill='x', padx=16, pady=8)
        self.label(search_bar, tr('ui_e9849dd8f804'), color=MUTED).pack(side='left', padx=(0, 8))
        search = tk.StringVar()
        search_entry = self.entry(search_bar)
        search_entry.config(textvariable=search)
        search_entry.pack(side='left', fill='x', expand=True)
        search.trace_add('write', lambda *args: self.find_setting(search.get()))
        self.build_startup(boot, settings)
        panel = tk.Frame(performance, bg=PANEL, padx=20, pady=16)
        panel.pack(fill='x', padx=18, pady=12)
        self.label(panel, tr('ui_2ef676178ad2'), size=15, bold=True).pack(anchor='w')
        self.label(panel, tr('ui_cc3326844f82'), color=MUTED, wrap=650).pack(anchor='w', pady=8)
        self.opt_folder = self.entry(panel)
        self.opt_folder.insert(0, settings.get('optimizationFolder', ''))
        self.opt_folder.pack(fill='x', pady=4)
        self.button(panel, tr('ui_b03525362de6'), self.choose_optimization_folder).pack(anchor='w')
        self.label(panel, tr('ui_3b2b652148d5'), color=MUTED, wrap=650).pack(anchor='w', pady=5)
        line = tk.Frame(panel, bg=PANEL)
        line.pack(fill='x', pady=8)
        self.label(line, tr('ui_9a5f27733594')).pack(side='left', padx=(0, 8))
        self.opt_fps = self.entry(line)
        self.opt_fps.config(width=5)
        self.opt_fps.insert(0, '10')
        self.opt_fps.pack(side='left', padx=(0, 12))
        self.button(line, 'OTIMIZAR', lambda: self.optimize('apply'), True).pack(side='left', padx=(0, 8))
        self.button(line, tr('ui_e65c9e38cd7f'), lambda: self.optimize('restore')).pack(side='left')
        self.opt_status = self.label(panel, tr('ui_506d9453649e'), wrap=650)
        self.opt_status.pack(anchor='w')
        block = tk.Frame(block_page, bg=PANEL, padx=20, pady=16)
        block.pack(fill='x', padx=18, pady=(0, 12))
        self.label(block, tr('ui_ead8eeb4740e'), size=15, bold=True).pack(anchor='w')
        self.block_acc = tk.BooleanVar(value=settings.get('blockACC') is True)
        tk.Checkbutton(block, text=tr('ui_4ecd11d82066'), variable=self.block_acc, command=self.save_block_acc, bg=PANEL, fg=TEXT, selectcolor=BG, activebackground=PANEL, activeforeground=TEXT).pack(anchor='w', pady=8)
        self.label(block, tr('ui_d24e94249bee'), color=MUTED, wrap=650).pack(anchor='w')
        box = tk.Frame(launchers, bg=PANEL, padx=20, pady=18)
        box.pack(fill='x', padx=22, pady=15)
        self.label(box, tr('ui_1b933a4ac4ce'), size=16, bold=True).pack(anchor='w')
        self.config_multi = self.label(box, tr('ui_2c2c1c5e3323'), color=MINT, wrap=850)
        self.config_multi.pack(anchor='w', pady=8)
        self.label(box, tr('ui_2b470c6caaf2'), color=MUTED, wrap=850).pack(anchor='w')
        tools = tk.Frame(launchers, bg=PANEL, padx=20, pady=18)
        tools.pack(fill='x', padx=22, pady=(0, 15))
        self.label(tools, tr('ui_91f29ee1f7cd'), size=16, bold=True).pack(anchor='w')
        self.label(tools, tr('ui_8610e376d94b'), color=MUTED, wrap=850).pack(anchor='w', pady=8)
        self.label(tools, tr('ui_38cba4d41c55'), color=MUTED).pack(anchor='w')
        self.bootstrap_status = self.label(tools, tr('ui_74b3a5ebfb93'), wrap=850)
        self.bootstrap_status.pack(anchor='w', pady=8)
        actions = tk.Frame(tools, bg=PANEL)
        actions.pack(fill='x')
        for title, action in ((tr('ui_68a37a2c2e3a'), 'check'), (tr('ui_9a6cd8b26236'), 'download'), (tr('ui_cb745b1b35bd'), 'open')):
            self.button(actions, title, lambda a=action: self.bootstrap_action(a), action == 'open').pack(side='left', padx=(0, 8))
        self.button(actions, tr('ui_ab71f8e40f0e'), self.choose_bootstrapper).pack(side='left')
        self.label(tools, tr('ui_96a9579f63aa'), color=MUTED, wrap=850).pack(anchor='w', pady=(10, 0))

    def show_optimization(self):
        self.show_config()
        self.config_sections.select(3)

    def choose_optimization_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title=tr('ui_1f8e83c8058b'))
        if folder:
            self.opt_folder.delete(0, 'end')
            self.opt_folder.insert(0, folder)

    def optimize(self, action):
        try:
            fps = int(self.opt_fps.get()) if action == 'apply' else 10
        except ValueError:
            self.opt_status.config(text=tr('ui_6f1c30f3a70b'))
            return

        def done(result):
            self.opt_status.config(text=result['message'])
            self.economy = action == 'apply'
            if self.compact != self.economy:
                self.toggle_compact()
        self.run('/optimization', {'action': action, 'fps': fps, 'folder': self.opt_folder.get().strip()}, done)

    def save_block_acc(self):
        desired = self.block_acc.get()

        def done(value, error):
            self.pending = False
            if error:
                self.block_acc.set(not desired)
            self.notice.config(text=error or (tr('ui_8f59149b6e77') if value['enabled'] else tr('ui_a70f2c616442')))
        if self.pending:
            self.block_acc.set(not desired)
            return
        self.pending = True
        self.dispatch('/block-acc', {'enabled': desired}, done)

    def bootstrap_action(self, action, path=None):

        def done(value):
            available = value.get('available')
            text = tr('ui_7efc400a3ae0') + value.get('version', '') if value.get('installed') else tr('ui_8778bde24c9c')
            if available:
                text += tr('ui_cb230978adc9') + available['version']
            if value.get('path'):
                text += '\n' + value['path']
            if action == 'download':
                text += tr('ui_4dd55c612c5a')
            elif action == 'open':
                text += tr('ui_6006c83d3ec4')
            self.bootstrap_status.config(text=text)
        self.run('/bootstrapper', {'action': action, 'path': path}, done)

    def choose_bootstrapper(self):
        path = filedialog.askopenfilename(parent=self.root, title=tr('ui_1478327672a1'), filetypes=[(tr('ui_9e0da1d60e25'), '*.exe')])
        if path:
            self.bootstrap_action('select', path)

    def label(self, parent, text, size=10, color=TEXT, bold=False, wrap=0):
        return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=color, anchor='w', justify='left', wraplength=wrap, font=('Segoe UI', min(size, 14), 'bold' if bold else 'normal'))

    def button(self, parent, text, action, primary=False):
        button = tk.Button(parent, text=text, command=action, bg='#47698f' if primary else '#414141', fg=TEXT, activebackground='#739fce' if primary else '#505050', activeforeground=TEXT, relief='raised', bd=1, highlightthickness=0, padx=8, pady=3, font=('Segoe UI', 9), cursor='hand2')
        button._sk_primary = primary
        return button

    def entry(self, parent):
        return tk.Entry(parent, bg='#202020', fg=TEXT, insertbackground=MINT, relief='flat', bd=0, highlightthickness=1, highlightbackground=LINE, highlightcolor=MINT, selectbackground='#3b587b')

    def dialog(self, title):
        window = tk.Toplevel(self.root, bg=PANEL)
        window.title(title)
        window.geometry('660x520')
        window.minsize(530, 320)
        window.transient(self.root)
        canvas = tk.Canvas(window, bg=PANEL, highlightthickness=0)
        scroll = ttk.Scrollbar(window, orient='vertical', command=canvas.yview)
        scroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        body = tk.Frame(canvas, bg=PANEL, padx=24, pady=22)
        item = canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(item, width=event.width))
        self.label(body, title, size=17, bold=True).pack(anchor='w', pady=(0, 10))
        if hasattr(self, 'palette'):
            self.root.after_idle(lambda: theme.apply(self.root, self.palette, getattr(self, 'ui_scale', 1.0)))
        return body

    def request(self, path, data):
        request = Request(f'http://127.0.0.1:{self.port}{path}', data=json.dumps(data).encode(), headers={'Content-Type': 'application/json', 'X-Rejoin-Key': self.key})
        try:
            with build_opener(ProxyHandler({})).open(request, timeout=1600 if path in ('/import', '/install', '/bootstrapper') else 45) as response:
                return json.load(response)
        except HTTPError as error:
            raise ValueError(json.load(error)['error']) from None

    def dispatch(self, path, data, callback):

        def worker():
            try:
                result = self.request(path, data)
                self.events.put((callback, result, None))
            except Exception as error:
                self.events.put((callback, None, str(error)))
        Thread(target=worker, daemon=True).start()

    def drain(self):
        try:
            while True:
                callback, value, error = self.events.get_nowait()
                callback(value, error)
        except Empty:
            pass
        finally:
            self.root.after(80, self.drain)

    def run(self, path, data, done=None):
        if self.pending:
            self.notice.config(text=tr('ui_44b13386cdc7'))
            return
        self.pending = True
        self.notice.config(text=tr('ui_53acce39d40f'))

        def finished(value, error):
            self.pending = False
            self.notice.config(text=error or tr('ui_ed9ff3e79c5f'))
            if not error and done:
                done(value)
        self.dispatch(path, data, finished)

    def refresh(self):
        self.dispatch('/state', {}, self.refresh_done)

    def refresh_done(self, state, error):
        if error:
            self.notice.config(text=error)
        else:
            self.state = state
            rows = {str(row['userId']): row for row in state['accounts']}
            cache = getattr(self, 'row_cache', {})
            next_cache = {}
            for identity in self.rows.keys() - rows.keys():
                self.table.delete(identity)
            for index, (identity, row) in enumerate(rows.items()):
                values = (row['username'], self.connection_text(row), '—' if row['age'] is None else tr('ui_54fbd60b2373', p0=row['age']), '—' if row.get('connected') is None else tr('ui_f4587e3c182e', p0=row['connected'] // 60), tr('ui_144ffd9ba321') if not row.get('rejoin') else f"{row['attempts']}/{row['maxAttempts']}" + (tr('ui_1d3f55212ba6') if row['attempts'] >= row['maxAttempts'] else tr('ui_57c5ab791359') if row.get('nextIn') is None else tr('ui_c08d02286152', p0=row['nextIn'])), row.get('jobId', '')[:8] or (tr('ui_8f5e025aa2f8') if state.get('blockACC') and row['age'] is not None else '—'))
                tags = ('even' if index % 2 == 0 else 'odd',) + (('error',) if row.get('errorCode') else ('block',) if row['status'].startswith(tr('ui_ead8eeb4740e')) else ('online',) if row['age'] is not None and row['age'] < 20 else ('offline',))
                next_cache[identity] = (values, tags)
                if identity in self.rows:
                    if cache.get(identity) != (values, tags):
                        self.table.item(identity, values=values, tags=tags)
                else:
                    self.table.insert('', 'end', iid=identity, values=values, tags=tags)
            self.row_cache = next_cache
            if getattr(self,"icons",None):
                mode="light" if self.palette==theme.LIGHT else "dark"
                for identity,row in rows.items():
                    if cache.get(identity)!=next_cache.get(identity):
                        icon=self.icons.get((mode,self.icon_key(row)))
                        if icon:self.table.item(identity,image=icon)
            self.rows = rows
            if hasattr(self, 'search'):
                self.filter_accounts()
            for label, value in zip(self.metrics, (len(rows), sum((r['age'] is not None and r['age'] < 20 for r in rows.values())), tr('ui_0a45660c135f', p0=state['waiting']) if state['busy'] else tr('ui_5c0c4cd5668c'))):
                label.config(text=value)
            if hasattr(self, 'empty'):
                if rows:
                    self.empty.place_forget()
                else:
                    self.empty.place(relx=0.5, rely=0.5, anchor='center')
            if hasattr(self, 'startup_update_checked') and (not self.startup_update_checked) and state.get('repo'):
                self.startup_update_checked = True
                self.check_startup_update(state['repo'])
            self.config_multi.config(text=state['multi'])
            if hasattr(self,"startup_progress"):self.startup_progress.config(text=state.get("startupStatus", ""))
            if hasattr(self,"footer_selection"):
                errors=sum(bool(row.get("errorCode")) for row in rows.values())
                self.footer_selection.config(text=f"{len(self.ids())} selecionadas · {errors} erro(s)")
            self.rejoin_status.config(text=tr('ui_9de78c0ac341', p0=state['rejoin'], p1=state['multi'], p2=state.get('startupStatus', ''), p3=state['version']))
        self.root.after(4000 if self.economy else 2000, self.refresh)

    def show_config(self):
        self.settings_window.deiconify()
        self.settings_window.lift()

    def show_search(self):
        if not self.filters_frame.winfo_manager():
            self.filters_frame.pack(before=self.table.master, fill='x', pady=(0, 3))
        self.search_field.focus_set()

    def toggle_controls(self):
        self.controls_visible = True
        self.profile_window.deiconify()
        self.profile_window.lift()

    @staticmethod
    def connection_text(row):
        status = row.get('status', '')
        connection = row.get('connection', '')
        if status == tr('ui_c3e839df6084'):
            return '●  ' + (connection or tr('ui_ef40dbe45178'))
        icon = '!  ' if row.get('errorCode') or 'recusad' in status.lower() or 'erro' in status.lower() else '↻  ' if 'abrindo' in status.lower() or 'aguardando' in status.lower() else '○  '
        return icon + (connection + ' · ' if connection and connection not in status else '') + status

    def filter_accounts(self):
        query = self.search.get().strip().casefold()
        category = self.state_filter.get()
        visible = 0
        for identity, row in self.row_order() if hasattr(self, 'sort_column') else self.rows.items():
            fresh = row.get('age') is not None and row['age'] < 20
            match = query in (row.get('username', '') + ' ' + identity).casefold()
            match = match and (category == tr('ui_8a3c3440366a') or (category == tr('ui_0c661608c587') and fresh and (row.get('connection') == tr('ui_ef40dbe45178'))) or (category == tr('ui_b419880b4c70') and fresh and (row.get('connection') == tr('ui_b419880b4c70'))) or (category == tr('ui_09763d9fa8a7') and (not fresh)) or (category == tr('ui_0748e2f5bdcf') and bool(row.get('errorCode'))) or (category == tr('ui_ead8eeb4740e') and row.get('status', '').startswith(tr('ui_ead8eeb4740e'))))
            if match:
                if identity not in self.table.get_children() or self.table.index(identity) != visible:
                    self.table.move(identity, '', visible)
                visible += 1
            else:
                self.table.selection_remove(identity)
                self.table.detach(identity)
        self.search_hint.config(text=tr('ui_35f8518f4786', p0=visible, p1=len(self.rows)))
        self.selection_info.config(text=tr('ui_4a62e217880b', p0=len(self.table.selection())))

    def account_selected(self, event=None):
        if hasattr(self,"palette"):self.root.after_idle(self.validate_destination)
        self.load_profile(event)
        ids = self.ids()
        if len(ids) == 1:
            row = self.rows.get(str(ids[0]), {})
            self.current_account.config(text=row.get('username', '') + tr('ui_ffe2f9374a97') + str(ids[0]))
            self.compact_status.config(text=self.connection_text(row))
        else:
            self.current_account.config(text=tr('ui_f5cfd70fef54', p0=len(ids)))
            self.compact_status.config(text=tr('ui_4466995d575f'))
        self.selection_info.config(text=tr('ui_4a62e217880b', p0=len(self.ids())))
        if len(self.ids()) == 1:
            row = self.rows.get(str(self.ids()[0]), {})
            self.selected_summary.config(text=row.get('username', '') + '  /  ' + self.connection_text(row))
        else:
            self.selected_summary.config(text=tr('ui_49a688b3c2ca', p0=len(self.ids())))

    def select_all(self):
        self.table.selection_set(self.table.get_children())

    def ids(self):
        return [int(identity) for identity in self.table.selection()]

    def action(self, path):
        try:
            place = int(self.place.get().strip())
        except ValueError:
            self.notice.config(text=tr('ui_56087a9cfb50'))
            return
        ids = self.ids()
        if not ids:
            self.notice.config(text=tr('ui_0890e3632aa9'))
            return
        payload = {'ids': ids, 'place': place, 'use_profiles': self.use_profiles.get()}
        if path in ('/rejoin', '/pause'):
            payload['disable'] = path == '/pause'
            path = '/rejoin'
            try:
                payload['rejoin_delay'] = int(self.rejoin_delay.get().strip())
                payload['max_attempts'] = int(self.max_attempts.get().strip())
            except ValueError:
                self.notice.config(text=tr('ui_76206e422165'))
                return
        if path in ('/launch', '/reconnect'):
            try:
                payload.update({key: int(field.get()) for key, field in self.dimensions.items()})
            except ValueError:
                self.notice.config(text=tr('ui_844eff263459'))
                return
        if path in ("/launch","/reconnect") and hasattr(self,"ui_prefs"):
            recent=self.ui_prefs.get("destinations",[])
            self.ui_prefs["destinations"]=[place]+[p for p in recent if p!=place][:7]
            self.persist_ui()
        self.run(path, payload)

    def build_startup(self, host, settings):
        panel = tk.Frame(host, bg=PANEL, padx=20, pady=18)
        panel.pack(fill='x', padx=18, pady=12)
        self.label(panel, tr('ui_89a60d625693'), size=16, bold=True).pack(anchor='w')
        self.start_windows = tk.BooleanVar(value=bool(settings.get('startWithWindows')))
        self.companion_enabled = tk.BooleanVar(value=bool(settings.get('companionEnabled')))
        self.start_weblauncher = tk.BooleanVar(value=bool(settings.get('startupWebLauncher', True)))
        self.start_accounts = tk.BooleanVar(value=bool(settings.get('startupAccounts')))
        self.startup_ids = list(settings.get('startupAccountIds', []))
        for text, variable in ((tr('ui_2f91d767d3e6'), self.start_windows), (tr('ui_c36d65fd5d82'), self.start_weblauncher), (tr('ui_bc5afc8b32ce'), self.companion_enabled), (tr('ui_00b8d687046f'), self.start_accounts)):
            tk.Checkbutton(panel, text=text, variable=variable, bg=PANEL, fg=TEXT, selectcolor=BG, activebackground=PANEL, activeforeground=TEXT).pack(anchor='w', pady=8)
        self.companion_path = self.entry(panel)
        self.companion_path.insert(0, settings.get('companionPath', ''))
        self.companion_path.pack(fill='x', pady=6)
        self.button(panel, tr('ui_250edc96c87d'), self.choose_companion).pack(anchor='w', pady=5)
        self.start_delays = {}
        for key, text, default in (('webLauncherDelay', tr('ui_f251b73e8f5a'), 10), ('executorDelay', tr('ui_3b29c4b2bad0'), 20)):
            self.label(panel, text, color=MUTED).pack(anchor='w', pady=(8, 2))
            field = self.entry(panel)
            field.insert(0, str(settings.get(key, default)))
            field.pack(anchor='w')
            self.start_delays[key] = field
        self.startup_count = self.label(panel, str(len(self.startup_ids)) + tr('ui_1d7f85059339'), color=MINT)
        self.startup_count.pack(anchor='w', pady=8)
        self.button(panel, tr('ui_48d7ec3aa0ab'), self.set_startup_accounts).pack(anchor='w', pady=5)
        self.label(panel, tr('ui_3bba9dac0f57'), color=MUTED, wrap=700).pack(anchor='w', pady=8)
        self.button(panel, tr('ui_b45329a293e6'), self.save_startup, True).pack(anchor='w', pady=5)
        self.button(panel, tr('ui_198458609e19'), lambda: self.run('/startup', {'action': 'sequence'})).pack(anchor='w', pady=5)
        self.button(panel, tr('ui_06b00a36df2b'), lambda: self.run('/startup', {'action': 'cancel'})).pack(anchor='w', pady=5)
        self.button(panel, tr('ui_f54e062a61af'), lambda: self.run('/startup', {'action': 'open'}, lambda v: self.notice.config(text=v['message']))).pack(anchor='w', pady=5)
        self.label(panel, tr('ui_988d4c3a3378'), color=MUTED, wrap=700).pack(anchor='w', pady=10)

        self.startup_progress=self.label(panel,"",color=MINT,wrap=650)
        self.startup_progress.pack(anchor="w",pady=8)

    def choose_companion(self):
        path = filedialog.askopenfilename(parent=self.root, title=tr('ui_556e79fb4477'), filetypes=[(tr('ui_5590a11391bb'), '*.exe')])
        if path:
            self.companion_path.delete(0, 'end')
            self.companion_path.insert(0, path)

    def set_startup_accounts(self):
        self.startup_ids = self.ids()
        self.startup_count.config(text=str(len(self.startup_ids)) + tr('ui_0a7eb114a947'))

    def save_startup(self):
        try:
            delays = {key: int(field.get()) for key, field in self.start_delays.items()}
        except ValueError:
            self.notice.config(text=tr('ui_bdc05541c4d8'))
            return
        self.run('/startup', {'startWithWindows': self.start_windows.get(), 'companionEnabled': self.companion_enabled.get(), 'companionPath': self.companion_path.get().strip(), 'startupWebLauncher': self.start_weblauncher.get(), 'startupAccounts': self.start_accounts.get(), 'startupAccountIds': self.startup_ids, **delays}, lambda v: (self.mark_config_clean(), self.notice.config(text=v['message'])))

    def save_selected_profile(self):
        try:
            payload = {'ids': self.ids(), 'place': int(self.place.get()), 'delay': int(self.rejoin_delay.get()), 'max_attempts': int(self.max_attempts.get()), 'fps': int(self.profile_fps.get())}
            payload.update({k: int(self.dimensions[k].get()) for k in ('width', 'height')})
        except ValueError:
            self.notice.config(text=tr('ui_153decdffe9a'))
            return
        self.run('/profile', payload, lambda v: self.notice.config(text=v['message']))

    def connection_details(self):
        selected = [self.rows.get(str(i), {}) for i in self.ids()]
        if not selected:
            self.notice.config(text=tr('ui_641487889457'))
            return
        body = self.dialog(tr('ui_c06aa16165bb'))
        text = tk.Text(body, bg=BG, fg=TEXT, width=75, height=22, wrap='word')
        text.pack(fill='both', expand=True)
        for row in selected:
            diag = row.get('block', {})
            other = self.rows.get(str(diag.get('conflictUserId')), {}).get('username', '—')
            text.insert('end', tr('ui_e099b420402e', p0=row.get('username'), p1=row.get('connection', '—'), p2=row.get('status'), p3=row.get('jobId') or tr('ui_0cd27ebeee66'), p4=other, p5=diag.get('target') or tr('ui_1172562d2a15'), p6=diag.get('nextIn', 0), p7='suportado' if row.get('fpsSupported') else tr('ui_9d7f5331fc66')))
        text.config(state='disabled')

    def toggle_compact(self):
        self.compact = not self.compact
        if hasattr(self,'banner') and self.compact and not self.removal_timer:self.banner.pack_forget()
        if hasattr(self,'ui_prefs'):
            self.ui_prefs['compact']=self.compact;self.persist_ui()
        ttk.Style(self.root).configure(tr('ui_d78dca84fb22'), rowheight=20 if self.compact else 28)

    def set_list_columns(self):
        self.table.configure(displaycolumns=('account', 'status', 'age', 'connected', 'retry', 'server') if self.detail_columns.get() else ('account', 'status', 'age'))

    def copy_account(self, field):
        text = '\n'.join((str(self.rows.get(str(identity), {}).get(field, identity if field == 'userId' else '')) for identity in self.ids()))
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

    def account_context(self, event):
        identity = self.table.identify_row(event.y)
        if identity and identity not in self.table.selection():
            self.table.selection_set(identity)
        menu = tk.Menu(self.root, tearoff=False, bg=PANEL, fg=TEXT)
        for title, action in ((tr('ui_535bc78c9148'), self.launch), (tr('ui_64d04acedf37'), lambda: self.action('/reconnect')), (tr('ui_f00fa760c1ff'), self.close_selected), (tr('ui_0eecac926ef6'), lambda: self.action('/pause')), (tr('ui_64feb1dcfd4a'), self.rejoin), (tr('ui_4dc412e47058'), lambda: self.copy_account('username')), (tr('ui_e4b299310335'), lambda: self.copy_account('userId')), (tr('ui_6dd94e23a8f9'), self.connection_details), (tr('ui_4bd4ea834263'), self.remove)):
            menu.add_command(label=title, command=action)
        theme.apply(menu, self.palette, getattr(self, 'ui_scale', 1.0))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def load_profile(self, event=None):
        ids = self.ids()
        if len(ids) != 1:
            return
        row = self.rows.get(str(ids[0]), {})
        profile = row.get('profile', {})
        for key, field in (('place', self.place), ('delay', self.rejoin_delay), ('max_attempts', self.max_attempts), ('fps', self.profile_fps), ('width', self.dimensions['width']), ('height', self.dimensions['height'])):
            if key in profile:
                field.delete(0, 'end')
                field.insert(0, str(profile[key]))

    def auth_check(self):
        ids = self.ids()
        if len(ids) != 1:
            self.notice.config(text=tr('ui_0137ccddb484'))
            return
        try:
            place = int(self.place.get().strip())
        except ValueError:
            self.notice.config(text=tr('ui_56087a9cfb50'))
            return

        def show(value):
            body = self.dialog(tr('ui_f26a20b05946'))
            result = value['result']
            lines = [result.get('message', ''), tr('ui_a5b7f76f00d1') + result.get('stage', '—'), tr('ui_42c7f57fcc0c') + (tr('ui_84fb9bfc81c8') if result.get('sessionValid') else tr('ui_72534bbb0ce3')), tr('ui_de80e6064caa') + str(result.get('ticketHTTP', '—')), tr('ui_108f168241ae') + (tr('ui_84fb9bfc81c8') if result.get('ticketIssued') else tr('ui_72534bbb0ce3')), tr('ui_d3ef9834724f') + (tr('ui_84fb9bfc81c8') if result.get('challenge') else tr('ui_72534bbb0ce3')), tr('ui_6c4122b22412')]
            self.label(body, '\n\n'.join(lines), wrap=520).pack(anchor='w')
        self.run('/auth-check', {'id': ids[0], 'place': place}, show)

    def diagnostic(self):

        def show(value):
            body = self.dialog(tr('ui_41c95b03ecdf'))
            field = tk.Text(body, height=18, wrap='word', bg=BG, fg=TEXT)
            report = '\n\n'.join(value['checks'])
            field.insert('1.0', report)
            field.config(state='disabled')
            field.pack(fill='both', expand=True)

            def copy():
                self.root.clipboard_clear()
                self.root.clipboard_append(report)
            self.button(body, tr('ui_3e3d40fc0898'), copy).pack(anchor='w', pady=8)
        self.run('/diagnostic', {}, show)

    def launch(self):
        self.action('/launch')

    def rejoin(self):
        self.action('/rejoin')

    def remove(self):
        ids = self.ids()
        if ids and messagebox.askyesno(tr('ui_915139432d7a'), tr('ui_aa12f23b4391'), parent=self.root):
            self.schedule_remove(ids)

    def import_dialog(self):
        import accounts
        body = self.dialog(tr('ui_e2b278f1e9c9'))
        window = body.winfo_toplevel()
        self.label(body, tr('ui_26759906aba4'), color=MUTED).pack(anchor='w')
        field = self.entry(body)
        field.config(show='•')
        field.pack(fill='x', pady=8)
        status = self.label(body, tr('ui_5f139ed2a0f3'), color=MUTED, wrap=520)
        status.pack(anchor='w')
        results = tk.Text(body, height=8, bg=BG, fg=TEXT, state='disabled', wrap='word')
        results.pack(fill='both', expand=True, pady=8)
        session_lines = []

        def validate(event=None):
            session_lines[:] = [line.strip().removeprefix('.ROBLOSECURITY=') for line in field.get().splitlines() if line.strip()]
            count = sum((accounts.valid_cookie(value) for value in session_lines))
            status.config(text=tr('ui_fabd0dd0650d', p0=count, p1=len(session_lines)))

        def paste():
            try:
                value = self.root.clipboard_get()
            except tk.TclError:
                return 'break'
            field.delete(0, 'end')
            field.insert(0, value)
            validate()
            return 'break'
        field.bind('<<Paste>>', lambda event: paste())
        field.bind('<KeyRelease>', validate)
        self.button(body, tr('ui_96329e05c2b2'), paste).pack(anchor='w')

        def show(value):
            if results.winfo_exists():
                results.config(state='normal')
                results.delete('1.0', 'end')
                results.insert('end', '\n'.join(value['results']))
                results.config(state='disabled')

        def submit():
            validate()
            if not session_lines or len(session_lines) > 100 or any((not accounts.valid_cookie(value) for value in session_lines)):
                status.config(text=tr('ui_39f990a0255e'))
                return
            payload = '\n'.join(session_lines)
            session_lines.clear()
            field.delete(0, 'end')
            self.run('/import', {'cookies': payload}, show)
        self.button(body, tr('ui_15581fd26db3'), submit, True).pack(anchor='w', pady=8)

        def close():
            field.delete(0, 'end')
            session_lines.clear()
            window.destroy()
        window.protocol('WM_DELETE_WINDOW', close)

    def heartbeat(self):

        def show(value):
            body = self.dialog(tr('ui_03083e37918b'))
            field = tk.Text(body, bg=BG, fg=TEXT, relief='flat', height=9)
            field.insert('1.0', value['script'])
            field.config(state='disabled')
            field.pack(fill='both', expand=True)

            def copy():
                self.root.clipboard_clear()
                self.root.clipboard_append(value['script'])
                button.config(text=tr('ui_65298c0ca89c'))
            button = self.button(body, tr('ui_3886f3e4fef2'), copy, True)
            button.pack(anchor='w', pady=(8, 0))
        self.run('/script', {}, show)

    def check_startup_update(self, repo):
        self.pending = True
        self.notice.config(text=tr('ui_fdd545991bf1'))

        def checked(value, error):
            self.pending = False
            self.last_check=time.strftime('%H:%M')
            if error:
                self.notice.config(text=tr('ui_948fd9776678', p0=error))
            elif value['newer'] and value['installable']:
                self.run('/install', {'repo': repo}, lambda _: self.root.destroy())
            else:
                self.notice.config(text=tr('ui_e7d7503dbf9d') if not value['newer'] else tr('ui_727e0859e9f5'))
        self.dispatch('/check', {'repo': repo}, checked)

    def fps_dialog(self):
        import ui_services
        body = self.dialog(tr('ui_7c87e63a566b'))
        self.label(body, tr('ui_87c62e925c13'), wrap=520).pack(anchor='w')
        field = self.entry(body)
        field.insert(0, '10')
        field.pack(fill='x', pady=8)
        status = self.label(body, '', wrap=520)
        status.pack(anchor='w')

        def change(remove=False):
            if self.pending:
                return
            try:
                fps = None if remove else int(field.get().strip())
            except ValueError:
                status.config(text=tr('ui_c87f47b0379f'))
                return
            self.pending = True
            status.config(text=tr('ui_8e17a2d6a309'))

            def worker():
                try:
                    result, error = (ui_services.change_fps(fps), None)
                except (ValueError, OSError):
                    result, error = (None, tr('ui_674bc24175c4'))
                self.events.put((done, result, error))

            def done(value, error):
                self.pending = False
                if status.winfo_exists():
                    status.config(text=error or value)
            Thread(target=worker, daemon=True).start()
        self.button(body, tr('ui_33ddeca17240'), change, True).pack(anchor='w', pady=8)
        self.button(body, tr('ui_4f436eaf3113'), lambda: change(True)).pack(anchor='w')

    def updates(self):
        body = self.dialog(tr('ui_cfeb11c07f77'))
        self.label(body, tr('ui_c11c693672e8'), color=MUTED).pack(anchor='w')
        repo = self.entry(body)
        repo.insert(0, self.state.get('repo', ''))
        repo.pack(fill='x', ipady=5, pady=8)
        status = self.label(body, '', color=MUTED, wrap=520)
        status.pack(anchor='w')
        install = self.button(body, tr('ui_b7cdda093dd6'), lambda: None, True)
        install.config(state='disabled')

        def check():
            source = repo.get().strip()
            install.config(state='disabled')

            def checked(value):
                if not install.winfo_exists():
                    return
                status.config(text=tr('ui_422bd9c33cfc', p0=value['available']) if value['newer'] else tr('ui_e7d7503dbf9d'))
                if value['newer'] and value['installable']:
                    install.config(state='normal', command=lambda: self.run('/install', {'repo': source}, lambda _: self.root.destroy()))
                elif value['newer']:
                    status.config(text=tr('ui_e9addffe52e7'))
            self.run('/check', {'repo': source}, checked)
        self.button(body, tr('ui_c876601f11fe'), check).pack(anchor='w', pady=8)
        install.pack(anchor='w')

    def add_tray(self, hide):
        self.button(self.toolbar, tr('ui_65d2e388ad8c'), hide).pack(side='right', padx=6)

    def history(self):

        def show(value):
            body = self.dialog(tr('ui_fef9495ee515'))
            field = tk.Text(body, bg=BG, fg=TEXT, relief='flat', wrap='word')
            for entry in reversed(value['entries']):
                field.insert('end', tr('ui_b867292db55b', p0=entry['time'], p1=entry['account'], p2=entry['event']))
            if not value['entries']:
                field.insert('end', tr('ui_146f2675d357'))
            field.config(state='disabled')
            field.pack(fill='both', expand=True)
        self.run('/history', {}, show)

    def manual_dialog(self):
        import asyncio
        import browser_login
        if self.pending:
            self.notice.config(text=tr('ui_44b13386cdc7'))
            return
        body = self.dialog(tr('ui_edf5c6542395'))
        window = body.winfo_toplevel()
        self.label(body, tr('ui_52e6c2b99cd7'), wrap=580).pack(anchor='w', pady=6)
        self.label(body, tr('ui_4bf1189d42bd'), color=MUTED, wrap=580).pack(anchor='w', pady=6)
        status = self.label(body, tr('ui_06dd1d4a5c9b'), color=MINT, wrap=580)
        status.pack(anchor='w', pady=12)
        cancel = Event()
        self.pending = True

        def report(name, message):
            if status.winfo_exists():
                status.config(text=message)

        def finished(value, error):
            self.pending = False
            if status.winfo_exists() and error:
                status.config(text=error)
            if not error:
                self.refresh()

        def worker():
            error = None
            try:
                asyncio.run(browser_login.import_batch([(None, None)], cancel, lambda name, message: self.events.put((report, name, message))))
            except Exception:
                error = tr('ui_256f2514a9d1')
            self.events.put((finished, None, error))

        def close():
            cancel.set()
            window.destroy()
        self.button(body, tr('ui_c111e0ab9ddb'), close).pack(anchor='w', pady=8)
        window.protocol('WM_DELETE_WINDOW', close)
        Thread(target=worker, daemon=True).start()

    def password_dialog(self):
        import asyncio
        import accounts
        import browser_login
        body = self.dialog(tr('ui_9e77511a41de'))
        window = body.winfo_toplevel()
        window.geometry('700x530')
        self.label(body, tr('ui_0d65d5bd75f8'), color=MUTED, wrap=640).pack(anchor='w')
        self.label(body, tr('ui_87d64705d9e0'), color=MUTED, wrap=640).pack(anchor='w', pady=(8, 3))
        pasted = tk.Text(body, bg=BG, fg=TEXT, insertbackground=TEXT, height=10, wrap='none', font=('Consolas', 10), undo=False)
        pasted.pack(fill='x', pady=(0, 6))
        detected = self.label(body, tr('ui_d6ccf5959d79'), color=MUTED, wrap=640)
        detected.pack(anchor='w')

        def recognize(event=None):
            if not pasted.edit_modified():
                return
            pasted.edit_modified(False)
            text = pasted.get('1.0', 'end-1c')
            if not text.strip():
                detected.config(text=tr('ui_d6ccf5959d79'))
                return
            try:
                rows = browser_login.parse_credentials(text)
                detected.config(text=tr('ui_824c6db4a139', p0=len(rows)))
            except ValueError as error:
                detected.config(text=str(error))
        pasted.tag_configure('invalid', underline=True)
        original_recognize = recognize

        def recognize(event=None):
            original_recognize(event)
            pasted.tag_remove('invalid', '1.0', 'end')
            for index, line in enumerate(pasted.get('1.0', 'end-1c').splitlines(), 1):
                if line.strip():
                    nick, separator, password = line.partition(':')
                    if not separator or not accounts.USERNAME.fullmatch(nick.strip()) or (not password):
                        pasted.tag_add('invalid', f'{index}.0', f'{index}.end')
        pasted.bind('<<Modified>>', recognize)
        pasted.focus_set()
        status = self.label(body, '', color=MINT, wrap=640)
        status.pack(anchor='w', pady=8)
        cancel = Event()
        messages = {}

        def report(nick, message):
            if status.winfo_exists():
                messages[nick] = message
                status.config(text='\n'.join((tr('ui_9482534b8f4b', p0=name, p1=text) for name, text in messages.items())))

        def submit():
            if self.pending:
                status.config(text=tr('ui_44b13386cdc7'))
                return
            try:
                credentials = browser_login.parse_credentials(pasted.get('1.0', 'end-1c'))
            except ValueError as error:
                status.config(text=str(error))
                return
            if not credentials or len(credentials) > 6 or any((not accounts.USERNAME.fullmatch(nick) or not password for nick, password in credentials)):
                status.config(text=tr('ui_1f6d67e3de37'))
                return
            if len({nick.casefold() for nick, _ in credentials}) != len(credentials):
                status.config(text=tr('ui_d7c008e1ada6'))
                return
            pasted.delete('1.0', 'end')
            self.pending = True
            start.config(state='disabled')
            messages.clear()
            status.config(text=tr('ui_8687121b598f'))

            def worker():
                error = None
                try:
                    asyncio.run(browser_login.import_batch(credentials, cancel, lambda nick, message: self.events.put((report, nick, message))))
                except Exception:
                    error = tr('ui_7b099710f8f8')
                self.events.put((finished, None, error))

            def finished(_, error):
                self.pending = False
                if status.winfo_exists():
                    start.config(state='normal')
                    if error:
                        status.config(text=error)
                if not error:
                    self.refresh()
            Thread(target=worker, daemon=True).start()
        start = self.button(body, tr('ui_811469e372ac'), submit, True)
        start.pack(anchor='w')

        def close():
            cancel.set()
            pasted.delete('1.0', 'end')
            window.destroy()
        window.protocol('WM_DELETE_WINDOW', close)
