"""Desktop interface for the local Rejoin Desk service."""
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
import accounts
from queue import Empty, Queue
from threading import Event, Thread
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

BG, PANEL, LINE, TEXT, MUTED, MINT = "#242424", "#2d2d2d", "#505050", "#eeeeee", "#bcbcbc", "#82b5f2"


class Desktop:
    def __init__(self, root, port, key, assets, settings):
        self.root, self.port, self.key = root, port, key
        self.events = Queue()
        self.refreshing = False
        self.rows = {}
        self.state = {}
        self.pending = False
        self.economy = bool(settings.get("economy"))
        root.title("SK Rejoin")
        if (assets / "artwork" / "sk.ico").exists():
            root.iconbitmap(str(assets / "artwork" / "sk.ico"))
        width, height = 784, 301
        root.geometry(f"{width}x{height}+20+20")
        root.minsize(720, 285)
        root.configure(bg=BG)
        root.option_add("*Font", ("Segoe UI", 9))
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        rowheight=20, borderwidth=1, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
                        font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#383838", foreground=TEXT, relief="raised",
                        padding=(4, 3), font=("Segoe UI", 9))
        style.map("Treeview", background=[("selected", "#3b587b")], foreground=[("selected", "#ffffff")])
        style.configure("TNotebook", background=BG, borderwidth=0, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
        style.configure("Workspace.TNotebook", background=BG, borderwidth=0, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
        style.configure("TNotebook.Tab", background="#303030", foreground=TEXT, padding=(15, 5))
        style.map("TNotebook.Tab", background=[("selected", "#464646")], foreground=[("selected", TEXT)])
        style.configure("TCombobox", background=LINE, fieldbackground="#202020", foreground=TEXT, arrowcolor=TEXT,
                        bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, padding=3)
        style.map("TCombobox", fieldbackground=[("readonly", "#202020")], foreground=[("readonly", TEXT)])
        for direction in ("Vertical", "Horizontal"):
            style.configure(direction+".TScrollbar", background="#454545", troughcolor=BG, bordercolor=LINE,
                            lightcolor=LINE, darkcolor=LINE, arrowsize=13, borderwidth=0)

        self.compact = True
        self.workspace = workspace = tk.Frame(root, bg=BG)
        workspace.pack(fill="both", expand=True, padx=6, pady=4)
        menubar = tk.Menu(root, tearoff=False, bg=PANEL, fg=TEXT, activebackground="#3b587b", activeforeground="white")
        accounts_menu = tk.Menu(menubar, tearoff=False, bg=PANEL, fg=TEXT)
        for title, action in (("Adicionar por nick e senha", self.password_dialog), ("Importar cookies", self.import_dialog),
                              ("Selecionar todas", self.select_all), ("Remover selecionadas", self.remove)):
            accounts_menu.add_command(label=title, command=action)
        accounts_menu.add_separator()
        accounts_menu.add_command(label="Encerrar", command=root.destroy)
        menubar.add_cascade(label="Contas", menu=accounts_menu)
        utilities = tk.Menu(menubar, tearoff=False, bg=PANEL, fg=TEXT)
        for title, action in (("Heartbeat", self.heartbeat), ("Histórico", self.history), ("Diagnóstico", self.diagnostic),
                              ("Limite de FPS", self.fps_dialog), ("Otimizar", self.show_optimization),
                              ("Atualizações", self.updates)):
            utilities.add_command(label=title, command=action)
        menubar.add_cascade(label="Utilitários", menu=utilities)
        view_menu = tk.Menu(menubar, tearoff=False, bg=PANEL, fg=TEXT)
        view_menu.add_command(label="Alternar altura das linhas", command=self.toggle_compact)
        view_menu.add_command(label="Mostrar / ocultar controles", command=self.toggle_controls)
        self.detail_columns = tk.BooleanVar(value=False)
        view_menu.add_checkbutton(label="Mostrar servidor e tentativas", variable=self.detail_columns, command=self.set_list_columns)
        menubar.add_cascade(label="Exibir", menu=view_menu)
        menubar.add_command(label="Configurações", command=self.show_config)
        self.menubar = menubar

        style.layout("Workspace.TNotebook.Tab", [])
        self.tabs = ttk.Notebook(workspace, style="Workspace.TNotebook")
        self.tabs.pack(fill="both", expand=True)
        sessions = tk.Frame(self.tabs, bg=BG)
        self.settings_window = tk.Toplevel(root, bg=BG)
        self.settings_window.withdraw()
        self.settings_window.title("SK Rejoin — Configurações")
        self.settings_window.geometry("760x600")
        self.settings_window.transient(root)
        self.settings_window.protocol("WM_DELETE_WINDOW", self.settings_window.withdraw)
        config = tk.Frame(self.settings_window, bg=BG)
        config.pack(fill="both", expand=True)
        self.tabs.add(sessions, text="Contas")
        self.build_config(config, settings)
        self.notice = self.label(workspace, "Iniciando…", size=8, color=MUTED, wrap=0)
        self.notice.pack(before=self.tabs, side="bottom", fill="x", pady=(2, 0))
        self.toolbar = toolbar = tk.Frame(sessions, bg=BG)
        toolbar.pack(side="bottom", fill="x", pady=(3, 0))
        add_menu = tk.Menu(toolbar, tearoff=False, bg=PANEL, fg=TEXT)
        add_menu.add_command(label="Nick e senha", command=self.password_dialog)
        add_menu.add_command(label="Importar cookies", command=self.import_dialog)
        add = tk.Menubutton(toolbar, text="Adicionar conta ▾", menu=add_menu, bg="#414141", fg=TEXT,
                            activebackground="#555555", activeforeground=TEXT, relief="raised", bd=1, padx=6, pady=2, cursor="hand2")
        add.pack(side="left", padx=(0, 5))
        for title, action in (("Remover", self.remove), ("Selecionar todas", self.select_all),
                              ("Detalhes", self.connection_details)):
            self.button(toolbar, title, action).pack(side="left", padx=(0, 5))
        self.button(toolbar, "Configurações", self.show_config).pack(side="right")
        metrics = tk.Frame(sessions, bg=BG)
        metrics.pack(side="bottom", fill="x", pady=(2, 0))
        self.metrics = []
        for title in ("Contas:", "Sinais ativos:", "Fila:"):
            self.label(metrics, title, size=8, color=MUTED).pack(side="left", padx=(0, 4))
            value = self.label(metrics, "—", size=8, bold=True)
            value.pack(side="left", padx=(0, 20))
            self.metrics.append(value)

        content = tk.Frame(sessions, bg=BG)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1, minsize=350)
        content.rowconfigure(0, weight=1)
        accounts_panel = tk.Frame(content, bg=BG)
        accounts_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        filters = tk.Frame(accounts_panel, bg=BG)
        self.filters_frame = filters
        self.label(filters, "Buscar", size=9).pack(side="left", padx=(0, 6))
        self.search = tk.StringVar()
        self.search_field = self.entry(filters)
        self.search_field.configure(textvariable=self.search)
        self.search_field.pack(side="left", fill="x", expand=True, ipady=3, padx=(0, 6))
        self.state_filter = tk.StringVar(value="Todas")
        chooser = ttk.Combobox(filters, textvariable=self.state_filter, state="readonly", width=13,
                              values=("Todas", "Conectadas", "Carregando", "Sem sinal", "Com erro", "BLOCK ACC"))
        chooser.pack(side="right")
        info = tk.Frame(accounts_panel, bg=BG)

        self.search_hint = self.label(info, "Contas salvas", size=8, color=MUTED)
        self.search_hint.pack(side="left")
        self.selection_info = self.label(info, "0 selecionadas", size=8, color=MUTED)
        self.selection_info.pack(side="right")
        self.search.trace_add("write", lambda *args: self.filter_accounts())
        chooser.bind("<<ComboboxSelected>>", lambda event: self.filter_accounts())
        table_shell = tk.Frame(accounts_panel, bg=BG)
        table_shell.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_shell, columns=("account", "status", "age", "connected", "retry", "server"),
                                 displaycolumns=("account", "status", "age"),
                                 show="headings", selectmode="extended")
        for column, name, size in (("account", "Conta", 145), ("status", "Estado", 220), ("age", "Sinal", 50),
                                    ("connected", "Tempo", 70), ("retry", "Reconexão", 110), ("server", "Servidor", 100)):
            self.table.heading(column, text=name, anchor="w")
            self.table.column(column, width=size, minwidth=100 if column=="status" else 50, stretch=column=="status")
        scrollbar = ttk.Scrollbar(table_shell, orient="vertical", command=self.table.yview)
        scrollbar.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(fill="both", expand=True)
        horizontal = ttk.Scrollbar(accounts_panel, orient="horizontal", command=self.table.xview)
        horizontal.pack(before=table_shell, side="bottom", fill="x")
        self.table.configure(xscrollcommand=horizontal.set)
        for tag, color in (("even", "#2d2d2d"), ("odd", "#292929")):
            self.table.tag_configure(tag, background=color)
        for tag, color in (("online", "#b4dbb6"), ("offline", "#bbbbbb"), ("error", "#ffa0a0"), ("block", "#e9ce8d")):
            self.table.tag_configure(tag, foreground=color)
        self.selected_summary = self.label(accounts_panel, "Selecione uma conta. Ctrl e Shift permitem selecionar várias.", size=8, color=MUTED, wrap=650)

        self.table.bind("<<TreeviewSelect>>", self.account_selected)
        self.table.bind("<Double-1>", lambda event: self.connection_details())
        self.table.bind("<Button-3>", self.account_context)
        self.table.bind("<Control-c>", lambda event: self.copy_account("username"))
        compact_panel = tk.Frame(content, bg=PANEL, width=252, padx=6, pady=4)
        compact_panel.grid(row=0, column=1, sticky="nsew")
        compact_panel.grid_propagate(False)
        compact_panel.columnconfigure(0, weight=1)
        self.label(compact_panel, "Place ID", size=8, color=MUTED).grid(row=0, column=0, sticky="w")
        self.place = self.entry(compact_panel)
        self.place.insert(0, str(settings.get("place", "")))
        self.place.grid(row=1, column=0, sticky="ew", pady=(1, 4), ipady=1)
        buttons = tk.Frame(compact_panel, bg=PANEL)
        buttons.grid(row=2, column=0, sticky="ew")
        self.button(buttons, "Entrar no jogo", self.launch, True).pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.button(buttons, "Reconectar", lambda: self.action("/reconnect")).pack(side="left", fill="x", expand=True)
        self.current_account = self.label(compact_panel, "Nenhuma conta selecionada", size=9, color=MINT, wrap=230)
        self.current_account.grid(row=3, column=0, sticky="ew", pady=(7, 3))
        self.compact_status = self.label(compact_panel, "Selecione uma conta na lista.", size=8, color=MUTED, wrap=230)
        self.compact_status.grid(row=4, column=0, sticky="nw")
        compact_panel.rowconfigure(5, weight=1)
        self.button(compact_panel, "Perfil / reconexão", self.toggle_controls).grid(row=6, column=0, sticky="ew", pady=(4, 3))
        bottom_tools = tk.Frame(compact_panel, bg=PANEL)
        bottom_tools.grid(row=7, column=0, sticky="ew")
        self.button(bottom_tools, "Heartbeat", self.heartbeat).pack(side="left", fill="x", expand=True, padx=(0, 3))
        tools = tk.Menubutton(bottom_tools, text="Utilitários ▾", bg="#414141", fg=TEXT, relief="raised", bd=1,
                              padx=6, pady=2, cursor="hand2")
        tools_menu = tk.Menu(tools, tearoff=False, bg=PANEL, fg=TEXT)
        for title, action in (("Buscar / filtrar (Ctrl+F)", self.show_search), ("Detalhes da conta", self.connection_details),
                              ("Histórico", self.history), ("Diagnóstico", self.diagnostic), ("FPS", self.fps_dialog),
                              ("Otimizar", self.show_optimization), ("Atualizações", self.updates),
                              ("Selecionar todas", self.select_all), ("Cancelar fila", lambda: self.run("/cancel", {}))):
            tools_menu.add_command(label=title, command=action)
        tools_menu.add_separator()
        tools_menu.add_command(label="Alternar altura das linhas", command=self.toggle_compact)
        tools_menu.add_checkbutton(label="Mostrar servidor e tentativas", variable=self.detail_columns, command=self.set_list_columns)
        tools.configure(menu=tools_menu)
        tools.pack(side="left", fill="x", expand=True)
        root.bind("<Control-f>", lambda event: self.show_search())

        self.profile_window = tk.Toplevel(root, bg=PANEL)
        self.profile_window.withdraw()
        self.profile_window.title("SK Rejoin — Perfil e reconexão")
        self.profile_window.geometry("420x600")
        self.profile_window.transient(root)
        self.profile_window.protocol("WM_DELETE_WINDOW", self.profile_window.withdraw)
        sidebar_shell = tk.Frame(self.profile_window, bg=PANEL)
        sidebar_shell.pack(fill="both", expand=True)
        self.controls_shell = sidebar_shell
        self.controls_visible = False
        canvas = tk.Canvas(sidebar_shell, bg=PANEL, highlightthickness=0)
        scroll = ttk.Scrollbar(sidebar_shell, orient="vertical", command=canvas.yview)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        sidebar = tk.Frame(canvas, bg=PANEL, padx=10, pady=8)
        item = canvas.create_window((0, 0), window=sidebar, anchor="nw")
        sidebar.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
        self.label(sidebar, "Perfil e reconexão", size=12, bold=True).pack(anchor="w", pady=(0, 8))
        self.label(sidebar, "Reconectar após (segundos sem sinal)", wrap=222).pack(anchor="w", pady=(8, 0))
        self.rejoin_delay = self.entry(sidebar)
        self.rejoin_delay.insert(0, str(settings.get("rejoin_delay", 20)))
        self.rejoin_delay.pack(fill="x", ipady=3)
        self.label(sidebar, "Máximo de tentativas", color=MUTED).pack(anchor="w", pady=(8, 0))
        self.max_attempts = self.entry(sidebar)
        self.max_attempts.insert(0, str(settings.get("max_attempts", 3)))
        self.max_attempts.pack(fill="x", ipady=3)
        self.label(sidebar, "Espera dobra entre tentativas, até 1 hora. Contagem zera após 2 minutos de sinal estável.", color=MUTED, wrap=222).pack(anchor="w", pady=5)
        self.use_profiles = tk.BooleanVar(value=True)
        tk.Checkbutton(sidebar, text="Usar destinos salvos por conta", variable=self.use_profiles,
                       bg=PANEL, fg=TEXT, selectcolor=BG, activebackground=PANEL,
                       activeforeground=TEXT).pack(anchor="w")
        self.dimensions = {}
        for key, label, default in (("limit", "Limite de instâncias", 2), ("width", "Largura (px)", 320), ("height", "Altura (px)", 240)):
            row = tk.Frame(sidebar, bg=PANEL)
            row.pack(fill="x", pady=(6, 0))
            self.label(row, label, color=MUTED).pack(side="left")
            entry = self.entry(row)
            entry.config(width=6)
            entry.insert(0, settings.get(key, default))
            entry.pack(side="right", ipady=3)
            self.dimensions[key] = entry
        self.label(sidebar, "FPS por conta (requer suporte do coletor)", color=MUTED, wrap=222).pack(anchor="w", pady=(8, 0))
        self.profile_fps = self.entry(sidebar)
        self.profile_fps.insert(0, "10")
        self.profile_fps.pack(fill="x", ipady=3)
        for title, action in (("Salvar perfil selecionadas", self.save_selected_profile), ("Detalhes da conexão", self.connection_details), ("Cancelar fila", lambda: self.run("/cancel", {})), ("Ativar reconexão", self.rejoin), ("Pausar selecionadas", lambda: self.action("/pause")), ("Selecionar todas", self.select_all), ("Remover selecionadas", self.remove)):
            self.button(sidebar, title, action, title == "Abrir selecionadas").pack(fill="x", pady=(4, 0))
        self.rejoin_status = self.label(sidebar, "", color=MUTED, wrap=222)
        self.rejoin_status.pack(anchor="w", pady=(12, 0))

        self.root.after(80, self.drain)
        self.refresh()
        repo = accounts.read(assets / "distribution.json", {}).get("repo", "")
        if repo:
            self.check_startup_update(repo)

    def build_config(self, parent, settings):
        options = ttk.Notebook(parent)
        self.config_sections = options
        options.pack(fill="both", expand=True)
        def scroll_page(title):
            shell = tk.Frame(options, bg=BG)
            options.add(shell, text=title)
            canvas = tk.Canvas(shell, bg=BG, highlightthickness=0)
            scrollbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
            scrollbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            canvas.configure(yscrollcommand=scrollbar.set)
            body = tk.Frame(canvas, bg=BG)
            item = canvas.create_window((0, 0), window=body, anchor="nw")
            body.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.bind("<Configure>", lambda event: canvas.itemconfigure(item, width=event.width))
            return body
        performance = scroll_page("Desempenho e BLOCK ACC")
        launchers = scroll_page("WebLauncher")
        boot = scroll_page("Inicialização")
        self.build_startup(boot, settings)
        panel = tk.Frame(performance, bg=PANEL, padx=20, pady=16)
        panel.pack(fill="x", padx=18, pady=12)
        self.label(panel, "Otimizar para economizar recursos", size=15, bold=True).pack(anchor="w")
        self.label(panel, "Texturas mínimas, efeitos reduzidos, grama removida e teto de FPS. "
                   "Feche os Roblox antes de aplicar ou restaurar. Alguns ajustes dependem da versão do cliente.", color=MUTED, wrap=650).pack(anchor="w", pady=8)
        self.opt_folder = self.entry(panel)
        self.opt_folder.insert(0, settings.get("optimizationFolder", ""))
        self.opt_folder.pack(fill="x", pady=4)
        self.button(panel, "Escolher pasta do Roblox", self.choose_optimization_folder).pack(anchor="w")
        self.label(panel, "Pasta com RobloxPlayerBeta.exe. Vazio usa a instalação registrada no Windows.", color=MUTED, wrap=650).pack(anchor="w", pady=5)
        line = tk.Frame(panel, bg=PANEL)
        line.pack(fill="x", pady=8)
        self.label(line, "Teto de FPS").pack(side="left", padx=(0, 8))
        self.opt_fps = self.entry(line)
        self.opt_fps.config(width=5)
        self.opt_fps.insert(0, "10")
        self.opt_fps.pack(side="left", padx=(0, 12))
        self.button(line, "OTIMIZAR", lambda: self.optimize("apply"), True).pack(side="left", padx=(0, 8))
        self.button(line, "Restaurar anterior", lambda: self.optimize("restore")).pack(side="left")
        self.opt_status = self.label(panel, "O perfil também reduz a frequência de atualização do painel.", wrap=650)
        self.opt_status.pack(anchor="w")
        block = tk.Frame(performance, bg=PANEL, padx=20, pady=16)
        block.pack(fill="x", padx=18, pady=(0, 12))
        self.label(block, "BLOCK ACC", size=15, bold=True).pack(anchor="w")
        self.block_acc = tk.BooleanVar(value=settings.get("blockACC") is True)
        tk.Checkbutton(block, text="Separar contas em servidores públicos diferentes", variable=self.block_acc,
                       command=self.save_block_acc, bg=PANEL, fg=TEXT, selectcolor=BG,
                       activebackground=PANEL, activeforeground=TEXT).pack(anchor="w", pady=8)
        self.label(block, "Vale para as contas acompanhadas neste app e PC. Use o novo heartbeat no Auto Execute. "
                   "Após carregar e aguardar 10 segundos, o coletor solicita outro servidor em caso de colisão. "
                   "Se falhar, tenta novamente após uma pausa. Confira os detalhes na aba Contas.", color=MUTED, wrap=650).pack(anchor="w")
        box = tk.Frame(launchers, bg=PANEL, padx=20, pady=18)
        box.pack(fill="x", padx=22, pady=15)
        self.label(box, "Multi Roblox", size=16, bold=True).pack(anchor="w")
        self.config_multi = self.label(box, "Conferindo modo de abertura…", color=MINT, wrap=850)
        self.config_multi.pack(anchor="w", pady=8)
        self.label(box, "O limite escolhido na aba Contas vale também com launchers externos. "
                   "Um novo processo é conferido após cada abertura.", color=MUTED, wrap=850).pack(anchor="w")
        tools = tk.Frame(launchers, bg=PANEL, padx=20, pady=18)
        tools.pack(fill="x", padx=22, pady=(0, 15))
        self.label(tools, "Downgrade / WebLauncher", size=16, bold=True).pack(anchor="w")
        self.label(tools, "Baixe ou escolha o WebLauncher. Abra a ferramenta para selecionar e aplicar "
                   "a versão do Roblox. Feche os jogos antes de trocar de versão.", color=MUTED, wrap=850).pack(anchor="w", pady=8)
        self.label(tools, "Fonte · github.com/vnnaworks/weblauncher", color=MUTED).pack(anchor="w")
        self.bootstrap_status = self.label(tools, "Clique Conferir para localizar a versão publicada.", wrap=850)
        self.bootstrap_status.pack(anchor="w", pady=8)
        actions = tk.Frame(tools, bg=PANEL)
        actions.pack(fill="x")
        for title, action in (("Conferir", "check"), ("Baixar WebLauncher", "download"), ("Abrir WebLauncher", "open")):
            self.button(actions, title, lambda a=action: self.bootstrap_action(a), action == "open").pack(side="left", padx=(0, 8))
        self.button(actions, "Escolher existente", self.choose_bootstrapper).pack(side="left")
        self.label(tools, "Depois de configurar, o SK Rejoin abre os jogos pelo launcher associado "
                   "ao protocolo Roblox no Windows.", color=MUTED, wrap=850).pack(anchor="w", pady=(10, 0))

    def show_optimization(self):
        self.show_config()
        self.config_sections.select(0)

    def choose_optimization_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title="Pasta com RobloxPlayerBeta.exe")
        if folder:
            self.opt_folder.delete(0, "end")
            self.opt_folder.insert(0, folder)

    def optimize(self, action):
        try:
            fps = int(self.opt_fps.get()) if action == "apply" else 10
        except ValueError:
            self.opt_status.config(text="Informe um teto de FPS inteiro.")
            return
        def done(result):
            self.opt_status.config(text=result["message"])
            self.economy = action == "apply"
            if self.compact != self.economy:
                self.toggle_compact()
        self.run("/optimization", {"action": action, "fps": fps, "folder": self.opt_folder.get().strip()}, done)

    def save_block_acc(self):
        desired = self.block_acc.get()
        def done(value, error):
            self.pending = False
            if error:
                self.block_acc.set(not desired)
            self.notice.config(text=error or ("BLOCK ACC ativado. Confira o novo heartbeat nas contas abertas." if value["enabled"] else "BLOCK ACC desativado."))
        if self.pending:
            self.block_acc.set(not desired)
            return
        self.pending = True
        self.dispatch("/block-acc", {"enabled": desired}, done)

    def bootstrap_action(self, action, path=None):
        def done(value):
            available = value.get("available")
            text = "WebLauncher " + value.get("version", "") if value.get("installed") else "WebLauncher ainda não escolhido."
            if available:
                text += " · Disponível " + available["version"]
            if value.get("path"):
                text += "\n" + value["path"]
            if action == "download":
                text += "\nDownload verificado com SHA-256. Clique Abrir WebLauncher."
            elif action == "open":
                text += "\nAbertura solicitada. Escolha a versão na ferramenta."
            self.bootstrap_status.config(text=text)
        self.run("/bootstrapper", {"action": action, "path": path}, done)

    def choose_bootstrapper(self):
        path = filedialog.askopenfilename(parent=self.root, title="Escolher WebLauncher", filetypes=[("Executável Windows", "*.exe")])
        if path:
            self.bootstrap_action("select", path)

    def label(self, parent, text, size=10, color=TEXT, bold=False, wrap=0):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color, anchor="w",
                        justify="left", wraplength=wrap, font=("Segoe UI", min(size, 14), "bold" if bold else "normal"))

    def button(self, parent, text, action, primary=False):
        return tk.Button(parent, text=text, command=action, bg="#47698f" if primary else "#414141",
                         fg=TEXT, activebackground="#739fce" if primary else "#505050",
                         activeforeground=TEXT, relief="raised", bd=1, highlightthickness=0,
                         padx=6, pady=2, font=("Segoe UI", 9), cursor="hand2")

    def entry(self, parent):
        return tk.Entry(parent, bg="#202020", fg=TEXT, insertbackground=MINT, relief="flat", bd=0,
                        highlightthickness=1, highlightbackground=LINE, highlightcolor=MINT, selectbackground="#3b587b")

    def dialog(self, title):
        window = tk.Toplevel(self.root, bg=PANEL)
        window.title(title)
        window.geometry("660x520")
        window.minsize(530, 320)
        window.transient(self.root)
        canvas = tk.Canvas(window, bg=PANEL, highlightthickness=0)
        scroll = ttk.Scrollbar(window, orient="vertical", command=canvas.yview)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        body = tk.Frame(canvas, bg=PANEL, padx=24, pady=22)
        item = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(item, width=event.width))
        self.label(body, title, size=17, bold=True).pack(anchor="w", pady=(0, 10))
        return body

    def request(self, path, data):
        request = Request(f"http://127.0.0.1:{self.port}{path}", data=json.dumps(data).encode(),
                          headers={"Content-Type": "application/json", "X-Rejoin-Key": self.key})
        try:
            with build_opener(ProxyHandler({})).open(request, timeout=1600 if path in ("/import", "/install", "/bootstrapper") else 45) as response:
                return json.load(response)
        except HTTPError as error:
            raise ValueError(json.load(error)["error"]) from None

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
            self.notice.config(text="Aguarde a operação atual.")
            return
        self.pending = True
        self.notice.config(text="Processando…")

        def finished(value, error):
            self.pending = False
            self.notice.config(text=error or "Operação concluída.")
            if not error and done:
                done(value)

        self.dispatch(path, data, finished)

    def refresh(self):
        self.dispatch("/state", {}, self.refresh_done)

    def refresh_done(self, state, error):
        if error:
            self.notice.config(text=error)
        else:
            self.state = state
            rows = {str(row["userId"]): row for row in state["accounts"]}
            for identity in self.rows.keys() - rows.keys():
                self.table.delete(identity)
            for index, (identity, row) in enumerate(rows.items()):
                values = (row["username"], self.connection_text(row), "—" if row["age"] is None else f'{row["age"]} s',
                          '—' if row.get('connected') is None else f'{row["connected"]//60} min',
                          ('Pausada' if not row.get('rejoin') else f'{row["attempts"]}/{row["maxAttempts"]}' +
                           (' · limite atingido' if row['attempts'] >= row['maxAttempts'] else ' · aguardando sinal' if row.get('nextIn') is None else f' · {row["nextIn"]}s')),
                          row.get('jobId', '')[:8] or ('Atualizar HB' if state.get('blockACC') and row['age'] is not None else '—'))
                tags = ("even" if index % 2 == 0 else "odd",) + (("error",) if row.get("errorCode") else ("block",) if row["status"].startswith("BLOCK ACC") else ("online",) if row["age"] is not None and row["age"] < 20 else ("offline",))
                if identity in self.rows:
                    self.table.item(identity, values=values, tags=tags)
                else:
                    self.table.insert("", "end", iid=identity, values=values, tags=tags)
            self.rows = rows
            if hasattr(self, "search"):
                self.filter_accounts()
            for label, value in zip(self.metrics, (len(rows), sum(r["age"] is not None and r["age"] < 20 for r in rows.values()), f'{state["waiting"]} na fila' if state["busy"] else "Livre")):
                label.config(text=value)
            self.config_multi.config(text=state["multi"])
            self.rejoin_status.config(text=f'{state["rejoin"]} conta(s) com reconexão ativa\n{state["multi"]}\n{state.get("startupStatus", "")}\nVersão {state["version"]}')
        self.root.after(4000 if self.economy else 2000, self.refresh)

    def show_config(self):
        self.settings_window.deiconify()
        self.settings_window.lift()

    def show_search(self):
        if not self.filters_frame.winfo_manager():
            self.filters_frame.pack(before=self.table.master, fill="x", pady=(0, 3))
        self.search_field.focus_set()

    def toggle_controls(self):
        self.controls_visible = True
        self.profile_window.deiconify()
        self.profile_window.lift()

    @staticmethod
    def connection_text(row):
        status = row.get("status", "")
        connection = row.get("connection", "")
        if status == "Online":
            return "●  " + (connection or "Conectado")
        return (connection + " · " if connection and connection not in status else "") + status

    def filter_accounts(self):
        query = self.search.get().strip().casefold()
        category = self.state_filter.get()
        visible = 0
        for identity, row in self.rows.items():
            fresh = row.get("age") is not None and row["age"] < 20
            match = query in (row.get("username", "") + " " + identity).casefold()
            match = match and (category == "Todas" or
                category == "Conectadas" and fresh and row.get("connection") == "Conectado" or
                category == "Carregando" and fresh and row.get("connection") == "Carregando" or
                category == "Sem sinal" and not fresh or category == "Com erro" and bool(row.get("errorCode")) or
                category == "BLOCK ACC" and row.get("status", "").startswith("BLOCK ACC"))
            if match:
                self.table.move(identity, "", visible)
                visible += 1
            else:
                self.table.selection_remove(identity)
                self.table.detach(identity)
        self.search_hint.config(text=f"{visible} de {len(self.rows)} contas · busque por nick ou ID")
        self.selection_info.config(text=f"{len(self.table.selection())} selecionadas")

    def account_selected(self, event=None):
        self.load_profile(event)
        ids = self.ids()
        if len(ids) == 1:
            row = self.rows.get(str(ids[0]), {})
            self.current_account.config(text=row.get("username", "") + "  /  ID " + str(ids[0]))
            self.compact_status.config(text=self.connection_text(row))
        else:
            self.current_account.config(text=f"{len(ids)} contas selecionadas")
            self.compact_status.config(text="Ações aplicadas às contas selecionadas.")
        self.selection_info.config(text=f"{len(self.ids())} selecionadas")
        if len(self.ids()) == 1:
            row = self.rows.get(str(self.ids()[0]), {})
            self.selected_summary.config(text=row.get("username", "") + "  /  " + self.connection_text(row))
        else:
            self.selected_summary.config(text=f"{len(self.ids())} contas selecionadas · ações e perfis serão aplicados às selecionadas.")

    def select_all(self):
        self.table.selection_set(self.table.get_children())

    def ids(self):
        return [int(identity) for identity in self.table.selection()]

    def action(self, path):
        try:
            place = int(self.place.get().strip())
        except ValueError:
            self.notice.config(text="Informe um Place ID válido.")
            return
        ids = self.ids()
        if not ids:
            self.notice.config(text="Selecione pelo menos uma conta.")
            return
        payload = {"ids": ids, "place": place, "use_profiles": self.use_profiles.get()}
        if path in ("/rejoin", "/pause"):
            payload["disable"] = path == "/pause"
            path = "/rejoin"
            try:
                payload["rejoin_delay"] = int(self.rejoin_delay.get().strip())
                payload["max_attempts"] = int(self.max_attempts.get().strip())
            except ValueError:
                self.notice.config(text="Informe entre 10 e 3600 segundos sem sinal.")
                return
        if path in ("/launch", "/reconnect"):
            try:
                payload.update({key: int(field.get()) for key, field in self.dimensions.items()})
            except ValueError:
                self.notice.config(text="Informe dimensões e limite em números inteiros.")
                return
        self.run(path, payload)

    def build_startup(self, host, settings):
        panel = tk.Frame(host, bg=PANEL, padx=20, pady=18)
        panel.pack(fill="x", padx=18, pady=12)
        self.label(panel, "Rejoin → WebLauncher → Executor → Contas", size=16, bold=True).pack(anchor="w")
        self.start_windows = tk.BooleanVar(value=bool(settings.get("startWithWindows")))
        self.companion_enabled = tk.BooleanVar(value=bool(settings.get("companionEnabled")))
        self.start_weblauncher = tk.BooleanVar(value=bool(settings.get("startupWebLauncher", True)))
        self.start_accounts = tk.BooleanVar(value=bool(settings.get("startupAccounts")))
        self.startup_ids = list(settings.get("startupAccountIds", []))
        for text, variable in (("Iniciar SK Rejoin ao entrar no Windows", self.start_windows),
                               ("2 · Abrir WebLauncher antes do executor", self.start_weblauncher),
                               ("3 · Abrir executor escolhido", self.companion_enabled),
                               ("4 · Abrir contas selecionadas após as esperas", self.start_accounts)):
            tk.Checkbutton(panel, text=text, variable=variable, bg=PANEL, fg=TEXT, selectcolor=BG,
                           activebackground=PANEL, activeforeground=TEXT).pack(anchor="w", pady=8)
        self.companion_path = self.entry(panel)
        self.companion_path.insert(0, settings.get("companionPath", ""))
        self.companion_path.pack(fill="x", pady=6)
        self.button(panel, "Selecionar aplicativo (.exe)", self.choose_companion).pack(anchor="w", pady=5)
        self.start_delays = {}
        for key, text, default in (("webLauncherDelay", "Espera após WebLauncher (segundos)", 10),
                                   ("executorDelay", "Espera após executor (segundos)", 20)):
            self.label(panel, text, color=MUTED).pack(anchor="w", pady=(8, 2))
            field = self.entry(panel)
            field.insert(0, str(settings.get(key, default)))
            field.pack(anchor="w")
            self.start_delays[key] = field
        self.startup_count = self.label(panel, str(len(self.startup_ids)) + " contas para iniciar", color=MINT)
        self.startup_count.pack(anchor="w", pady=8)
        self.button(panel, "Usar contas selecionadas na aba Contas", self.set_startup_accounts).pack(anchor="w", pady=5)
        self.label(panel, "Salve o perfil com Place ID de cada conta antes de ativar. As contas entram na fila habitual. "
                   "Os tempos são esperas configuradas; aumente se o WebLauncher ou executor carregar devagar.", color=MUTED, wrap=700).pack(anchor="w", pady=8)
        self.button(panel, "Salvar inicialização", self.save_startup, True).pack(anchor="w", pady=5)
        self.button(panel, "Testar sequência salva", lambda: self.run("/startup", {"action": "sequence"})).pack(anchor="w", pady=5)
        self.button(panel, "Cancelar sequência", lambda: self.run("/startup", {"action": "cancel"})).pack(anchor="w", pady=5)
        self.button(panel, "Abrir aplicativo agora", lambda: self.run("/startup", {"action": "open"}, lambda v: self.notice.config(text=v["message"]))).pack(anchor="w", pady=5)
        self.label(panel, "A inicialização vale para seu usuário do Windows. Mantenha o Rejoin em uma pasta fixa. "
                   "O aplicativo adicional é aberto como programa independente, sem login ou injeção pelo Rejoin.",
                   color=MUTED, wrap=700).pack(anchor="w", pady=10)

    def choose_companion(self):
        path = filedialog.askopenfilename(parent=self.root, title="Aplicativo para abrir com o SK Rejoin", filetypes=[("Aplicativo Windows", "*.exe")])
        if path:
            self.companion_path.delete(0, "end")
            self.companion_path.insert(0, path)

    def set_startup_accounts(self):
        self.startup_ids = self.ids()
        self.startup_count.config(text=str(len(self.startup_ids)) + " contas para iniciar · salve a configuração")

    def save_startup(self):
        try:
            delays = {key: int(field.get()) for key, field in self.start_delays.items()}
        except ValueError:
            self.notice.config(text="Informe esperas inteiras de 1 a 180 segundos.")
            return
        self.run("/startup", {"startWithWindows": self.start_windows.get(), "companionEnabled": self.companion_enabled.get(),
                             "companionPath": self.companion_path.get().strip(), "startupWebLauncher": self.start_weblauncher.get(),
                             "startupAccounts": self.start_accounts.get(), "startupAccountIds": self.startup_ids, **delays},
                 lambda v: self.notice.config(text=v["message"]))

    def save_selected_profile(self):
        try:
            payload = {"ids": self.ids(), "place": int(self.place.get()), "delay": int(self.rejoin_delay.get()),
                       "max_attempts": int(self.max_attempts.get()), "fps": int(self.profile_fps.get())}
            payload.update({k: int(self.dimensions[k].get()) for k in ("width", "height")})
        except ValueError:
            self.notice.config(text="Preencha o perfil com números inteiros.")
            return
        self.run("/profile", payload, lambda v: self.notice.config(text=v["message"]))

    def connection_details(self):
        selected = [self.rows.get(str(i), {}) for i in self.ids()]
        if not selected:
            self.notice.config(text="Selecione uma conta para consultar os detalhes.")
            return
        body = self.dialog("Conexão e BLOCK ACC")
        text = tk.Text(body, bg=BG, fg=TEXT, width=75, height=22, wrap="word")
        text.pack(fill="both", expand=True)
        for row in selected:
            diag = row.get("block", {})
            other = self.rows.get(str(diag.get("conflictUserId")), {}).get("username", "—")
            text.insert("end", f'{row.get("username")}\n{row.get("connection", "—")} · {row.get("status")}\n'
                        f'Servidor atual: {row.get("jobId") or "Não informado"}\n'
                        f'Conflito com: {other}\nDestino: {diag.get("target") or "Aguardando destino"}\n'
                        f'Próxima tentativa BLOCK ACC: {diag.get("nextIn", 0)} s\n'
                        f'FPS por conta: {"suportado" if row.get("fpsSupported") else "aguardando suporte do coletor"}\n\n')
        text.config(state="disabled")

    def toggle_compact(self):
        self.compact = not self.compact
        ttk.Style(self.root).configure("Treeview", rowheight=20 if self.compact else 28)

    def set_list_columns(self):
        self.table.configure(displaycolumns=("account", "status", "age", "connected", "retry", "server") if self.detail_columns.get() else ("account", "status", "age"))

    def copy_account(self, field):
        text = "\n".join(str(self.rows.get(str(identity), {}).get(field, identity if field=="userId" else "")) for identity in self.ids())
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

    def account_context(self, event):
        identity = self.table.identify_row(event.y)
        if identity and identity not in self.table.selection():
            self.table.selection_set(identity)
        menu = tk.Menu(self.root, tearoff=False, bg=PANEL, fg=TEXT)
        for title, action in (("Entrar no jogo", self.launch), ("Reconectar", lambda: self.action("/reconnect")),
                              ("Copiar nick", lambda: self.copy_account("username")), ("Copiar UserId", lambda: self.copy_account("userId")),
                              ("Detalhes", self.connection_details), ("Remover", self.remove)):
            menu.add_command(label=title, command=action)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def load_profile(self, event=None):
        ids = self.ids()
        if len(ids) != 1:
            return
        row = self.rows.get(str(ids[0]), {})
        profile = row.get("profile", {})
        for key, field in (("place", self.place), ("delay", self.rejoin_delay), ("max_attempts", self.max_attempts), ("fps", self.profile_fps), ("width", self.dimensions["width"]), ("height", self.dimensions["height"])):
            if key in profile:
                field.delete(0, "end")
                field.insert(0, str(profile[key]))

    def diagnostic(self):
        def show(value):
            body = self.dialog("Diagnóstico de abertura")
            self.label(body, "\n\n".join(value["checks"]), wrap=520).pack(anchor="w")
        self.run("/diagnostic", {}, show)

    def launch(self):
        self.action("/launch")

    def rejoin(self):
        self.action("/rejoin")

    def remove(self):
        ids = self.ids()
        if ids and messagebox.askyesno("Remover sessões", "Remover as sessões selecionadas deste PC?", parent=self.root):
            self.run("/remove", {"ids": ids})

    def import_dialog(self):
        body = self.dialog("Importar sessões")
        self.label(body, "Cole um cookie .ROBLOSECURITY por linha.", color=MUTED).pack(anchor="w")
        field = tk.Text(body, height=5, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", wrap="word")
        field.pack(fill="x", pady=8)
        results = tk.Text(body, height=5, bg=BG, fg=TEXT, relief="flat", state="disabled", wrap="word")

        def submit():
            cookies = field.get("1.0", "end-1c")
            field.delete("1.0", "end")
            self.run("/import", {"cookies": cookies}, show)

        def show(value):
            if results.winfo_exists():
                results.config(state="normal")
                results.delete("1.0", "end")
                results.insert("1.0", "\n".join(value["results"]))
                results.config(state="disabled")

        self.button(body, "Validar e importar", submit, True).pack(anchor="w", pady=(0, 8))
        results.pack(fill="both", expand=True)

    def heartbeat(self):
        def show(value):
            body = self.dialog("Conectar heartbeat")
            field = tk.Text(body, bg=BG, fg=TEXT, relief="flat", height=9)
            field.insert("1.0", value["script"])
            field.config(state="disabled")
            field.pack(fill="both", expand=True)
            def copy():
                self.root.clipboard_clear()
                self.root.clipboard_append(value["script"])
                button.config(text="Script copiado")
            button = self.button(body, "Copiar script", copy, True)
            button.pack(anchor="w", pady=(8, 0))
        self.run("/script", {}, show)

    def check_startup_update(self, repo):
        self.pending = True
        self.notice.config(text="Buscando atualizações no GitHub…")

        def checked(value, error):
            self.pending = False
            if error:
                self.notice.config(text=f"Não foi possível verificar a atualização: {error}")
            elif value["newer"] and value["installable"]:
                self.run("/install", {"repo": repo}, lambda _: self.root.destroy())
            else:
                self.notice.config(text="Versão atualizada." if not value["newer"] else
                                   "Atualização disponível para a edição compilada.")

        self.dispatch("/check", {"repo": repo}, checked)

    def fps_dialog(self):
        import winreg

        body = self.dialog("Limite de FPS")
        self.label(body, "Aplica ao Roblox Player deste PC na próxima abertura. "
                   "Feche todas as janelas do Roblox antes de testar.", wrap=500).pack(anchor="w")
        field = self.entry(body)
        field.insert(0, "10")
        field.pack(fill="x", pady=8)
        status = self.label(body, "", wrap=500)
        status.pack(anchor="w")

        def change(remove=False):
            if self.pending:
                status.config(text="Aguarde a operação atual.")
                return
            try:
                fps = None if remove else int(field.get().strip())
                if fps is not None and not 1 <= fps <= 240:
                    raise ValueError("Informe um limite entre 1 e 240 FPS.")
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"roblox\DefaultIcon") as key:
                    icon = winreg.QueryValueEx(key, "")[0]
                folder = Path(os.path.expandvars(icon.rsplit(",", 1)[0].strip().strip('"'))).parent
                if not folder.name.lower().startswith("version-") or not (folder / "RobloxPlayerBeta.exe").is_file():
                    raise ValueError("Instalação do Roblox Player não localizada.")
                target = folder / "ClientSettings" / "ClientAppSettings.json"
                settings = json.loads(target.read_text(encoding="utf-8-sig")) if target.exists() else {}
                if not isinstance(settings, dict):
                    raise ValueError("O arquivo de configuração do Roblox não contém um objeto JSON.")
                name = "DFIntTaskSchedulerTargetFps"
                if remove and name not in settings:
                    status.config(text="Nenhum limite configurado por esse ajuste.")
                    return
                if remove:
                    settings.pop(name)
                else:
                    settings[name] = fps
                target.parent.mkdir(exist_ok=True)
                temporary = None
                try:
                    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as output:
                        temporary = Path(output.name)
                        json.dump(settings, output, indent=2)
                    temporary.replace(target)
                finally:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
                status.config(text="Limite removido. Reabra o Roblox." if remove else
                              f"{fps} FPS configurados. Reabra o Roblox e confira com Shift + F5.")
            except OSError:
                status.config(text="Não foi possível acessar a instalação ou gravar a configuração do Roblox.")
            except ValueError as error:
                status.config(text=str(error))

        self.button(body, "Aplicar limite", change, True).pack(anchor="w", pady=8)
        self.button(body, "Remover limite", lambda: change(True)).pack(anchor="w")

    def updates(self):
        body = self.dialog("Atualizações")
        self.label(body, "Repositório GitHub no formato dono/repo", color=MUTED).pack(anchor="w")
        repo = self.entry(body)
        repo.insert(0, self.state.get("repo", ""))
        repo.pack(fill="x", ipady=5, pady=8)
        status = self.label(body, "", color=MUTED, wrap=520)
        status.pack(anchor="w")
        install = self.button(body, "Instalar e reiniciar", lambda: None, True)
        install.config(state="disabled")

        def check():
            source = repo.get().strip()
            install.config(state="disabled")
            def checked(value):
                if not install.winfo_exists():
                    return
                status.config(text=f'Versão disponível: {value["available"]}' if value["newer"] else "Versão atualizada.")
                if value["newer"] and value["installable"]:
                    install.config(state="normal", command=lambda: self.run("/install", {"repo": source}, lambda _: self.root.destroy()))
                elif value["newer"]:
                    status.config(text="Compile a edição autônoma para instalar pelo app.")
            self.run("/check", {"repo": source}, checked)

        self.button(body, "Verificar versão", check).pack(anchor="w", pady=8)
        install.pack(anchor="w")

    def add_tray(self, hide):
        self.button(self.toolbar, "Bandeja", hide).pack(side="right", padx=6)

    def history(self):
        def show(value):
            body = self.dialog("Histórico de sessões")
            field = tk.Text(body, bg=BG, fg=TEXT, relief="flat", wrap="word")
            for entry in reversed(value["entries"]):
                field.insert("end", f'{entry["time"]}  ·  {entry["account"]}\n{entry["event"]}\n\n')
            if not value["entries"]:
                field.insert("end", "Nenhum evento registrado.")
            field.config(state="disabled")
            field.pack(fill="both", expand=True)
        self.run("/history", {}, show)

    def password_dialog(self):
        import asyncio
        import accounts
        import browser_login

        body = self.dialog("Adicionar por nick e senha")
        window = body.winfo_toplevel()
        window.geometry("700x500")
        self.label(body, "Preencha até 6 contas. O app abre até 3 janelas do Chrome por vez.",
                   color=MUTED, wrap=640).pack(anchor="w")
        fields = []
        for _ in range(6):
            row = tk.Frame(body, bg=PANEL)
            row.pack(fill="x", pady=3)
            self.label(row, "Nick").pack(side="left", padx=5)
            nick = self.entry(row)
            nick.pack(side="left", fill="x", expand=True, ipady=3)
            self.label(row, "Senha").pack(side="left", padx=5)
            password = self.entry(row)
            password.config(show="•")
            password.pack(side="left", fill="x", expand=True, ipady=3)
            fields.append((nick, password))
        status = self.label(body, "", color=MINT, wrap=640)
        status.pack(anchor="w", pady=8)
        cancel = Event()
        messages = {}

        def report(nick, message):
            if status.winfo_exists():
                messages[nick] = message
                status.config(text="\n".join(f"{name} · {text}" for name, text in messages.items()))

        def submit():
            if self.pending:
                status.config(text="Aguarde a operação atual.")
                return
            rows = [(nick.get().strip(), password.get()) for nick, password in fields]
            credentials = [(nick, password) for nick, password in rows if nick or password]
            if not credentials or any(not accounts.USERNAME.fullmatch(nick) or not password for nick, password in credentials):
                status.config(text="Preencha um nick válido e a senha em cada linha usada.")
                return
            if len({nick.casefold() for nick, _ in credentials}) != len(credentials):
                status.config(text="Cada nick deve aparecer uma vez.")
                return
            for _, password in fields:
                password.delete(0, "end")
            self.pending = True
            start.config(state="disabled")
            messages.clear()
            status.config(text="Iniciando o lote…")

            def worker():
                try:
                    asyncio.run(browser_login.import_batch(credentials, cancel,
                        lambda nick, message: self.events.put((report, nick, message))))
                    error = None
                except ValueError as exc:
                    error = str(exc)
                except Exception:
                    error = "Falha ao iniciar o login pelo Chrome."
                self.events.put((finished, None, error))

            def finished(_, error):
                self.pending = False
                if status.winfo_exists():
                    start.config(state="normal")
                    if error:
                        status.config(text=error)

            Thread(target=worker, daemon=True).start()

        start = self.button(body, "Entrar e adicionar contas", submit, True)
        start.pack(anchor="w")
        def close():
            cancel.set()
            window.destroy()
        window.protocol("WM_DELETE_WINDOW", close)



