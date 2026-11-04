"""Desktop interface for the local Rejoin Desk service."""
import json
import accounts
from queue import Empty, Queue
from threading import Event, Thread
import tkinter as tk
from tkinter import messagebox, ttk
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

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=26, pady=(22, 12))
        self.banner = tk.PhotoImage(file=assets / "artwork" / "banner.png").subsample(2, 2)
        self.portrait = tk.PhotoImage(file=assets / "artwork" / "portrait.png").subsample(4, 4)
        hero = tk.Canvas(header, bg="#000000", height=182, highlightthickness=0)
        hero.pack(fill="x")
        art = hero.create_image(0, 0, image=self.banner, anchor="ne")
        hero.bind("<Configure>", lambda event: hero.coords(art, event.width, 0))
        hero.create_text(22, 28, text="01   /   CONTROLE DE SESSÕES", anchor="w", fill=MINT, font=("Consolas", 10))
        hero.create_text(19, 83, text="SK REJOIN", anchor="w", fill=TEXT, font=("Segoe UI Black", 38))
        hero.create_text(23, 141, text="Fila de abertura e reconexão", anchor="w", fill=MUTED, font=("Segoe UI", 12))
        toolbar = tk.Frame(header, bg=BG)
        toolbar.pack(fill="x", pady=(8, 0))
        tk.Label(toolbar, image=self.portrait, bg=BG).pack(side="left", padx=(0, 8))
        self.toolbar = toolbar
        for title, action in (("Nick e senha", self.password_dialog), ("Importar contas", self.import_dialog), ("Heartbeat", self.heartbeat), ("Histórico", self.history), ("Atualizações", self.updates)):
            self.button(toolbar, title, action, title == "Importar contas").pack(side="left", padx=(0, 6))
        self.button(toolbar, "Encerrar", root.destroy).pack(side="right")
        
        metrics = tk.Frame(root, bg=BG)
        metrics.pack(fill="x", padx=26, pady=(0, 14))
        self.metrics = []
        for title in ("Contas salvas", "Heartbeat ativo", "Fila de abertura"):
            card = tk.Frame(metrics, bg=PANEL, padx=15, pady=10)
            card.pack(side="left", fill="x", expand=True, padx=(0, 7))
            self.label(card, title, color=MUTED).pack(anchor="w")
            value = self.label(card, "—", size=18, bold=True)
            value.pack(anchor="w")
            self.metrics.append(value)

        content = tk.Frame(root, bg=BG)
        content.pack(fill="both", expand=True, padx=26)
        accounts_panel = tk.Frame(content, bg=PANEL, padx=12, pady=12)
        accounts_panel.pack(side="left", fill="both", expand=True, padx=(0, 12))
        self.label(accounts_panel, "Suas contas", size=14, bold=True).pack(anchor="w", pady=(0, 9))
        self.table = ttk.Treeview(accounts_panel, columns=("account", "status", "age"), show="headings", selectmode="extended")
        for column, name, width in (("account", "CONTA", 145), ("status", "ESTADO", 190), ("age", "ÚLTIMO SINAL", 100)):
            self.table.heading(column, text=name, anchor="w")
            self.table.column(column, width=width, minwidth=75)
        scrollbar = ttk.Scrollbar(accounts_panel, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.table.pack(fill="both", expand=True)
        self.table.tag_configure("online", foreground=MINT)
        self.table.tag_configure("offline", foreground="#ffc693")

        sidebar = tk.Frame(content, bg=PANEL, padx=15, pady=12, width=260)
        sidebar.pack(side="right", fill="y")
        self.label(sidebar, "Abrir no Roblox", size=14, bold=True).pack(anchor="w")
        self.label(sidebar, "Place ID", color=MUTED).pack(anchor="w", pady=(12, 4))
        self.place = self.entry(sidebar)
        self.place.insert(0, str(settings.get("place", "")))
        self.place.pack(fill="x", ipady=5)
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
        for title, action in (("Abrir selecionadas", self.launch), ("Cancelar fila", lambda: self.run("/cancel", {})), ("Ativar reconexão", self.rejoin), ("Desativar reconexão", lambda: self.run("/rejoin", {"ids": []})), ("Selecionar todas", self.select_all), ("Remover selecionadas", self.remove)):
            self.button(sidebar, title, action, title == "Abrir selecionadas").pack(fill="x", pady=(7, 0))
        self.rejoin_status = self.label(sidebar, "", color=MUTED, wrap=222)
        self.rejoin_status.pack(anchor="w", pady=(12, 0))
        self.notice = self.label(root, "Iniciando…", color=MINT, wrap=950)
        self.notice.pack(fill="x", padx=26, pady=12)
        self.root.after(80, self.drain)
        self.refresh()
        repo = accounts.read(assets / "distribution.json", {}).get("repo", "")
        if repo:
            self.check_startup_update(repo)

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
            with build_opener(ProxyHandler({})).open(request, timeout=1600 if path in ("/import", "/install") else 45) as response:
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
                values = (row["username"], row["status"], "—" if row["age"] is None else f'{row["age"]} s')
                tags = ("online",) if row["status"] == "Online" else ("offline",) if row["status"] == "Sem sinal" else ()
                if identity in self.rows:
                    self.table.item(identity, values=values, tags=tags)
                else:
                    self.table.insert("", "end", iid=identity, values=values, tags=tags)
            self.rows = rows
            for label, value in zip(self.metrics, (len(rows), sum(r["status"] == "Online" for r in rows.values()), f'{state["waiting"]} na fila' if state["busy"] else "Livre")):
                label.config(text=value)
            self.rejoin_status.config(text=f'{state["rejoin"]} conta(s) com reconexão ativa\n{state["multi"]}\nVersão {state["version"]}')
        self.root.after(2000, self.refresh)

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
        payload = {"ids": ids, "place": place}
        if path == "/launch":
            try:
                payload.update({key: int(field.get()) for key, field in self.dimensions.items()})
            except ValueError:
                self.notice.config(text="Informe dimensões e limite em números inteiros.")
                return
        self.run(path, payload)

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
