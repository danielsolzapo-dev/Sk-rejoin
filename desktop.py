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

BG, PANEL, LINE, TEXT, MUTED, MINT = "#090909", "#171717", "#303030", "#f7f4ed", "#b8b6b1", "#e9bd78"


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
        root.geometry("1100x805")
        root.minsize(840, 550)
        root.configure(bg=BG)
        root.option_add("*Font", ("Segoe UI", 10))
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=34, borderwidth=0)
        style.configure("Treeview.Heading", background=LINE, foreground=TEXT, relief="flat")
        style.map("Treeview", background=[("selected", "#51402b")], foreground=[("selected", TEXT)])

        self.compact = False
        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=26, pady=(22, 12))
        self.banner = tk.PhotoImage(file=assets / "artwork" / "banner.png").subsample(2, 2)
        self.portrait = tk.PhotoImage(file=assets / "artwork" / "portrait.png").subsample(4, 4)
        hero = tk.Canvas(header, bg="#000000", height=182, highlightthickness=0)
        hero.pack(fill="x")
        self.hero = hero
        art = hero.create_image(0, 0, image=self.banner, anchor="ne")
        hero.bind("<Configure>", lambda event: hero.coords(art, event.width, 0))
        hero.create_text(22, 28, text="01   /   CONTROLE DE SESSÕES", anchor="w", fill=MINT, font=("Consolas", 10))
        hero.create_text(19, 83, text="SK REJOIN", anchor="w", fill=TEXT, font=("Segoe UI Black", 38))
        hero.create_text(23, 141, text="Fila de abertura e reconexão", anchor="w", fill=MUTED, font=("Segoe UI", 12))
        toolbar = tk.Frame(header, bg=BG)
        toolbar.pack(fill="x", pady=(8, 0))
        tk.Label(toolbar, image=self.portrait, bg=BG).pack(side="left", padx=(0, 8))
        self.toolbar = toolbar
        toolsbar = tk.Frame(header, bg=BG)
        toolsbar.pack(fill="x", pady=(6, 0))
        for title, action in (("Nick e senha", self.password_dialog), ("Importar contas", self.import_dialog), ("Heartbeat", self.heartbeat), ("Histórico", self.history), ("Otimizar", self.show_optimization), ("Diagnóstico", self.diagnostic), ("Compacto", self.toggle_compact), ("FPS", self.fps_dialog), ("Atualizações", self.updates)):
            host = toolbar if title in ("Nick e senha", "Importar contas", "Heartbeat", "Histórico") else toolsbar
            self.button(host, title, action, title == "Importar contas").pack(side="left", padx=(0, 6))
        self.button(toolbar, "Encerrar", root.destroy).pack(side="right")
        
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=12)
        sessions = tk.Frame(self.tabs, bg=BG)
        config = tk.Frame(self.tabs, bg=BG)
        self.tabs.add(sessions, text="Contas")
        self.tabs.add(config, text="Config")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(20, 8), background=LINE, foreground=TEXT)
        style.map("TNotebook.Tab", background=[("selected", "#51402b")])
        self.build_config(config, settings)
        metrics = tk.Frame(sessions, bg=BG)
        metrics.pack(fill="x", padx=26, pady=(0, 14))
        self.metrics = []
        for title in ("Contas salvas", "Heartbeat ativo", "Fila de abertura"):
            card = tk.Frame(metrics, bg=PANEL, padx=15, pady=10)
            card.pack(side="left", fill="x", expand=True, padx=(0, 7))
            self.label(card, title, color=MUTED).pack(anchor="w")
            value = self.label(card, "—", size=18, bold=True)
            value.pack(anchor="w")
            self.metrics.append(value)

        content = tk.Frame(sessions, bg=BG)
        content.pack(fill="both", expand=True, padx=26)
        accounts_panel = tk.Frame(content, bg=PANEL, padx=12, pady=12)
        accounts_panel.pack(side="left", fill="both", expand=True, padx=(0, 12))
        self.label(accounts_panel, "Suas contas", size=14, bold=True).pack(anchor="w", pady=(0, 9))
        self.table = ttk.Treeview(accounts_panel, columns=("account", "status", "age", "connected", "retry", "server"), show="headings", selectmode="extended")
        for column, name, width in (("account", "CONTA", 145), ("status", "ESTADO", 190), ("age", "ÚLTIMO SINAL", 90), ("connected", "CONECTADA", 85), ("retry", "RECONEXÃO", 110), ("server", "SERVIDOR", 85)):
            self.table.heading(column, text=name, anchor="w")
            self.table.column(column, width=width, minwidth=75)
        scrollbar = ttk.Scrollbar(accounts_panel, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self.load_profile)
        self.table.tag_configure("online", foreground=MINT)
        self.table.tag_configure("offline", foreground="#ffc693")

        sidebar_shell = tk.Frame(content, bg=PANEL, width=290)
        sidebar_shell.pack(side="right", fill="y")
        sidebar_shell.pack_propagate(False)
        canvas = tk.Canvas(sidebar_shell, bg=PANEL, highlightthickness=0)
        scroll = ttk.Scrollbar(sidebar_shell, orient="vertical", command=canvas.yview)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        sidebar = tk.Frame(canvas, bg=PANEL, padx=15, pady=12)
        item = canvas.create_window((0, 0), window=sidebar, anchor="nw")
        sidebar.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
        self.label(sidebar, "Abrir no Roblox", size=14, bold=True).pack(anchor="w")
        self.label(sidebar, "Place ID", color=MUTED).pack(anchor="w", pady=(12, 4))
        self.place = self.entry(sidebar)
        self.place.insert(0, str(settings.get("place", "")))
        self.place.pack(fill="x", ipady=5)
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
        for title, action in (("Abrir selecionadas", self.launch), ("Cancelar fila", lambda: self.run("/cancel", {})), ("Ativar reconexão", self.rejoin), ("Pausar selecionadas", lambda: self.action("/pause")), ("Selecionar todas", self.select_all), ("Remover selecionadas", self.remove)):
            self.button(sidebar, title, action, title == "Abrir selecionadas").pack(fill="x", pady=(7, 0))
        self.rejoin_status = self.label(sidebar, "", color=MUTED, wrap=222)
        self.rejoin_status.pack(anchor="w", pady=(12, 0))
        self.notice = self.label(root, "Iniciando…", color=MINT, wrap=950)
        self.notice.pack(fill="x", padx=26, pady=12)
        self.root.after(80, self.drain)
        if self.economy:
            self.toggle_compact()
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
        self.opt_status = self.label(panel, "O perfil também reduz a frequência de atualização do painel e recolhe o banner.", wrap=650)
        self.opt_status.pack(anchor="w")
        block = tk.Frame(performance, bg=PANEL, padx=20, pady=16)
        block.pack(fill="x", padx=18, pady=(0, 12))
        self.label(block, "BLOCK ACC", size=15, bold=True).pack(anchor="w")
        self.block_acc = tk.BooleanVar(value=settings.get("blockACC") is True)
        tk.Checkbutton(block, text="Separar contas em servidores públicos diferentes", variable=self.block_acc,
                       command=self.save_block_acc, bg=PANEL, fg=TEXT, selectcolor=BG,
                       activebackground=PANEL, activeforeground=TEXT).pack(anchor="w", pady=8)
        self.label(block, "Vale para as contas acompanhadas neste app e PC. Use o novo heartbeat no Auto Execute. "
                   "Se uma colisão for detectada, o coletor solicita outro servidor. Sem destino disponível, "
                   "a conta duplicada é desconectada para interromper a disputa.", color=MUTED, wrap=650).pack(anchor="w")
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
        self.tabs.select(1)
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
                        justify="left", wraplength=wrap, font=("Segoe UI", size, "bold" if bold else "normal"))

    def button(self, parent, text, action, primary=False):
        return tk.Button(parent, text=text, command=action, bg=MINT if primary else LINE,
                         fg=BG if primary else TEXT, activebackground="#f5d5a6" if primary else "#444444",
                         activeforeground=BG if primary else TEXT, relief="flat", padx=10, pady=6, cursor="hand2")

    def entry(self, parent):
        return tk.Entry(parent, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat")

    def dialog(self, title):
        window = tk.Toplevel(self.root, bg=PANEL)
        window.title(title)
        window.geometry("600x345")
        window.transient(self.root)
        body = tk.Frame(window, bg=PANEL, padx=18, pady=14)
        body.pack(fill="both", expand=True)
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
            for identity, row in rows.items():
                values = (row["username"], row["status"], "—" if row["age"] is None else f'{row["age"]} s',
                          '—' if row.get('connected') is None else f'{row["connected"]//60} min',
                          ('Pausada' if not row.get('rejoin') else f'{row["attempts"]}/{row["maxAttempts"]}' +
                           (' · limite atingido' if row['attempts'] >= row['maxAttempts'] else ' · aguardando sinal' if row.get('nextIn') is None else f' · {row["nextIn"]}s')),
                          row.get('jobId', '')[:8] or ('Atualizar HB' if state.get('blockACC') and row['age'] is not None else '—'))
                tags = ("online",) if row["status"] == "Online" else ("offline",) if row["status"] == "Sem sinal" else ()
                if identity in self.rows:
                    self.table.item(identity, values=values, tags=tags)
                else:
                    self.table.insert("", "end", iid=identity, values=values, tags=tags)
            self.rows = rows
            for label, value in zip(self.metrics, (len(rows), sum(r["status"] == "Online" for r in rows.values()), f'{state["waiting"]} na fila' if state["busy"] else "Livre")):
                label.config(text=value)
            self.config_multi.config(text=state["multi"])
            self.rejoin_status.config(text=f'{state["rejoin"]} conta(s) com reconexão ativa\n{state["multi"]}\nVersão {state["version"]}')
        self.root.after(4000 if self.economy else 2000, self.refresh)

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
        if path == "/launch":
            try:
                payload.update({key: int(field.get()) for key, field in self.dimensions.items()})
            except ValueError:
                self.notice.config(text="Informe dimensões e limite em números inteiros.")
                return
        self.run(path, payload)

    def toggle_compact(self):
        self.compact = not self.compact
        self.hero.configure(height=0 if self.compact else 182)
        if self.compact:
            self.hero.pack_forget()
        else:
            self.hero.pack(fill="x", before=self.toolbar)

    def load_profile(self, event=None):
        ids = self.ids()
        if len(ids) != 1:
            return
        row = self.rows.get(str(ids[0]), {})
        profile = row.get("profile", {})
        for key, field in (("place", self.place), ("delay", self.rejoin_delay), ("max_attempts", self.max_attempts)):
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
