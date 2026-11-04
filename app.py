"""Local Windows account dashboard and authenticated heartbeat receiver."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time

import accounts
import update
import windows

ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
KEY = accounts.read(accounts.ROOT / "heartbeat-key.json", None) or secrets.token_urlsafe(32)
accounts.write(accounts.ROOT / "heartbeat-key.json", KEY)
ADMIN = secrets.token_urlsafe(32)
LOCK = threading.RLock()
LIVE = {}
STATUS = {}
BUSY = False
REJOIN = {}
PORT = 49327
MULTI = "Preparando modo de instâncias."
MULTI_HANDLE = None

def public_state():
    now = time.monotonic()
    with LOCK:
        rows = accounts.accounts()
        for row in rows:
            identity = row["userId"]
            beat = LIVE.get(identity)
            age = round(now - beat["received"]) if beat else None
            status = STATUS.get(identity, "Pronta")
            if age is not None and age < 20:
                status = "Online"
            elif beat and status in ("Pronta", "Aguardando heartbeat"):
                status = "Sem sinal"
            row.update(status=status, age=age, place=beat["place"] if beat else None)
        return {"accounts": rows, "waiting": WAITING, "busy": BUSY, "version": update.VERSION, "rejoin": len(REJOIN), "multi": MULTI, "repo": accounts.read(ASSETS / "distribution.json", {}).get("repo", "")}

HISTORY = accounts.ROOT / "sk-history.json"
SETTINGS = accounts.ROOT / "sk-settings.json"
QUEUE_CANCEL = threading.Event()
WAITING = 0

def record(identity, event):
    with LOCK:
        entries = accounts.read(HISTORY, [])
        entries.append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "account": identity, "event": event})
        accounts.write(HISTORY, entries[-500:])

def wait_new_pid(before):
    deadline = time.monotonic() + 50
    while time.monotonic() < deadline and not QUEUE_CANCEL.is_set():
        new = windows.running() - before
        if len(new) == 1:
            return new.pop()
        if len(new) > 1:
            raise ValueError("Vários processos do Roblox surgiram ao mesmo tempo. Instância não identificada.")
        QUEUE_CANCEL.wait(.5)
    if QUEUE_CANCEL.is_set():
        raise ValueError("Fila cancelada.")
    raise ValueError("Windows recebeu o pedido, mas nenhum novo processo Roblox apareceu em 50 s.")

def start_job(value, *, remember_place=True):
    global BUSY, WAITING
    with LOCK:
        if BUSY:
            raise ValueError("Aguarde ou cancele a fila atual.")
        ids, place = value.get("ids"), value.get("place")
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100 or any(type(i) is not int for i in ids):
            raise ValueError("Selecione até 100 contas.")
        if type(place) is not int or not 0 < place < 10**16:
            raise ValueError("Informe um Place ID válido.")
        settings = {"limit": 2, "width": 320, "height": 240, **accounts.read(SETTINGS, {})}
        for key, minimum, maximum in (("limit", 1, 20), ("width", 160, 1920), ("height", 120, 1080)):
            number = value.get(key, settings[key])
            if type(number) is not int or not minimum <= number <= maximum:
                raise ValueError("Confira o limite e as dimensões da janela.")
            settings[key] = number
        rows = {a["userId"]: a for a in accounts.accounts()}
        targets = [rows[i] for i in dict.fromkeys(ids) if i in rows]
        if not targets:
            raise ValueError("Selecione contas cadastradas.")
        if not MULTI_HANDLE and len(targets) > 1:
            raise ValueError(MULTI)
        if remember_place:
            settings["place"] = place
        accounts.write(SETTINGS, settings)
        QUEUE_CANCEL.clear()
        BUSY = True
        WAITING = len(targets)

    def run():
        global BUSY, WAITING
        try:
            for row in targets:
                identity = row["userId"]
                if QUEUE_CANCEL.is_set():
                    break
                with LOCK:
                    STATUS[identity] = "Na fila"
                limit = settings["limit"] if MULTI_HANDLE else 1
                while len(windows.running()) >= limit:
                    with LOCK:
                        STATUS[identity] = f"Aguardando vaga ({limit} instâncias permitidas)"
                    if QUEUE_CANCEL.wait(1):
                        return
                before = windows.running()
                if QUEUE_CANCEL.is_set():
                    return
                with LOCK:
                    STATUS[identity] = "Abrindo"
                    WAITING -= 1
                    previous_session = LIVE.get(identity, {}).get("session")
                sent_at = time.monotonic()
                record(row["username"], "Abertura solicitada")
                try:
                    accounts.launch(row["username"], place, before_open=lambda: not QUEUE_CANCEL.is_set())
                    pid = wait_new_pid(before)
                except (ValueError, OSError) as error:
                    with LOCK:
                        STATUS[identity] = str(error)
                    record(row["username"], str(error))
                    break
                size = windows.compact(pid, settings["width"], settings["height"], time.monotonic() + 15)
                with LOCK:
                    STATUS[identity] = "Aguardando heartbeat"
                record(row["username"], f"Janela medida em {size[0]} × {size[1]} px" if size else "Janela compacta não confirmada")
                deadline = time.monotonic() + 30
                confirmed = False
                while time.monotonic() < deadline and not QUEUE_CANCEL.is_set():
                    with LOCK:
                        beat = LIVE.get(identity)
                        confirmed = bool(beat and beat["received"] >= sent_at and beat["place"] == place and beat["session"] != previous_session)
                    if confirmed:
                        break
                    QUEUE_CANCEL.wait(.5)
                if not confirmed:
                    if QUEUE_CANCEL.is_set():
                        message = "Fila cancelada"
                    elif pid in windows.running():
                        message = "Roblox aberto, mas sem heartbeat confirmado"
                    else:
                        message = "Roblox encerrou antes de confirmar o heartbeat"
                    with LOCK:
                        STATUS[identity] = message
                    record(row["username"], message)
                    if QUEUE_CANCEL.is_set():
                        break

        except (ValueError, OSError) as error:
            record("Fila", str(error))
        finally:
            with LOCK:
                for row in targets:
                    if STATUS.get(row["userId"], "").startswith(("Na fila", "Aguardando vaga")):
                        STATUS[row["userId"]] = "Pronta"
                WAITING = 0
                BUSY = False
    threading.Thread(target=run, daemon=True).start()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, value, mime="application/json"):
        data = json.dumps(value, ensure_ascii=False).encode() if mime == "application/json" else value
        self.send_response(code)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def local(self):
        return self.headers.get("Host") == f"127.0.0.1:{PORT}" and self.headers.get("Origin") in (None, f"http://127.0.0.1:{PORT}")

    def do_POST(self):
        if not self.local():
            return self.reply(403, {"error": "Origem inválida."})
        expected = KEY if self.path == "/heartbeat" else ADMIN
        if not secrets.compare_digest(self.headers.get("X-Heartbeat-Key" if self.path == "/heartbeat" else "X-Rejoin-Key", ""), expected):
            return self.reply(401, {"error": "Chave inválida."})
        try:
            self.connection.settimeout(5)
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 900000:
                raise ValueError("Pedido acima do limite.")
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError("Pedido inválido.")
            if self.path == "/heartbeat":
                identity, place, session = (value.get(k) for k in ("userId", "placeId", "session"))
                if type(identity) is not int or type(place) is not int or place <= 0 or not isinstance(session, str) or not 1 <= len(session) <= 80:
                    raise ValueError("Heartbeat inválido.")
                with LOCK:
                    if not any(a["userId"] == identity for a in accounts.accounts()):
                        return self.reply(404, {"error": "Conta não cadastrada."})
                    if identity in REJOIN:
                        REJOIN[identity]["attempts"] = 0
                    previous = LIVE.get(identity)
                    if not previous or time.monotonic() - previous["received"] >= 20:
                        record(str(identity), "Heartbeat recebido")
                    LIVE[identity] = {"received": time.monotonic(), "place": place, "session": session}
                return self.reply(200, {"ok": True})
            if self.path == "/state":
                return self.reply(200, public_state())
            if self.path == "/script":
                script = (ASSETS / "heartbeat.luau").read_text(encoding="utf-8")
                return self.reply(200, {"script": script.replace("__HEARTBEAT_URL__", f"http://127.0.0.1:{PORT}/heartbeat").replace("__HEARTBEAT_KEY__", KEY)})
            if self.path == "/import":
                lines = value.get("cookies", "").splitlines()
                cookies = [line.strip().removeprefix(".ROBLOSECURITY=") for line in lines if line.strip()]
                if not 1 <= len(cookies) <= 100:
                    raise ValueError("Cole de 1 a 100 sessões, uma por linha.")
                results = []
                for index, cookie in enumerate(dict.fromkeys(cookies), 1):
                    try:
                        row = accounts.save_session(cookie)
                        results.append(f"Linha {index} · {row['username']} adicionada")
                    except ValueError as error:
                        results.append(f"Linha {index} · {error}")
                return self.reply(200, {"results": results})
            if self.path == "/history":
                return self.reply(200, {"entries": accounts.read(HISTORY, [])[-100:]})
            if self.path == "/cancel":
                QUEUE_CANCEL.set()
                return self.reply(200, {"ok": True})
            if self.path == "/launch":
                start_job(value)
                return self.reply(200, {"ok": True})
            if self.path == "/remove":
                ids = value.get("ids")
                if not isinstance(ids, list) or not 1 <= len(ids) <= 100 or any(type(i) is not int for i in ids):
                    raise ValueError("Seleção inválida.")
                with LOCK:
                    if BUSY:
                        raise ValueError("Aguarde a fila terminar.")
                    accounts.remove_accounts(ids)
                    for identity in ids:
                        for mapping in (LIVE, REJOIN, STATUS):
                            mapping.pop(identity, None)
                return self.reply(200, {"ok": True})
            if self.path == "/rejoin":
                ids, place = value.get("ids"), value.get("place")
                if not isinstance(ids, list) or len(ids) > 100 or any(type(i) is not int for i in ids):
                    raise ValueError("Seleção inválida.")
                if ids and (type(place) is not int or not 0 < place < 10**16):
                    raise ValueError("Informe um Place ID válido.")
                delay = value.get("rejoin_delay", 20)
                if ids and (type(delay) is not int or not 10 <= delay <= 3600):
                    raise ValueError("Informe entre 10 e 3600 segundos sem sinal.")
                known = {a["userId"] for a in accounts.accounts()}
                with LOCK:
                    if ids:
                        settings = accounts.read(SETTINGS, {})
                        settings["place"] = place
                        settings["rejoin_delay"] = delay
                        accounts.write(SETTINGS, settings)
                    REJOIN.clear()
                    REJOIN.update({i: {"place": place, "delay": delay, "attempts": 0, "next": 0} for i in ids if i in known})
                return self.reply(200, {"ok": True})
            if self.path == "/check":
                info, newer = update.manifest(value.get("repo", ""))
                return self.reply(200, {"available": info["version"], "newer": newer, "installable": bool(getattr(sys, "frozen", False))})
            if self.path == "/install":
                if BUSY:
                    raise ValueError("Aguarde a fila de abertura terminar.")
                update.install(value.get("repo", ""))
                self.reply(200, {"ok": True})
                threading.Timer(.5, self.server.shutdown).start()
                return
            if self.path == "/exit":
                self.reply(200, {"ok": True})
                threading.Timer(.2, self.server.shutdown).start()
                return
            self.reply(404, {"error": "Rota indisponível."})
        except (ValueError, TypeError, AttributeError, OSError):
            error = sys.exc_info()[1]
            self.reply(400, {"error": str(error) if type(error) is ValueError else "Operação indisponível. Confira a configuração e a conexão."})

def watch():
    while True:
        time.sleep(2)
        with LOCK:
            if BUSY:
                continue
            now = time.monotonic()
            for identity, policy in REJOIN.items():
                beat = LIVE.get(identity)
                if not beat or now - beat["received"] < policy["delay"] or now < policy["next"] or policy["attempts"] >= 3:
                    continue
                try:
                    record(str(identity), "Tentativa de reconexão")
                    start_job({"ids": [identity], "place": policy["place"]}, remember_place=False)
                except ValueError:
                    continue
                policy["attempts"] += 1
                policy["next"] = now + 60
                break

def main():
    global MULTI_HANDLE, MULTI
    import tkinter as tk
    from tkinter import messagebox
    from desktop import Desktop
    import tray

    root = tk.Tk()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        root.withdraw()
        messagebox.showerror("SK Rejoin", f"Feche a versão anterior do Rejoin Desk ou libere a porta local {PORT}.", parent=root)
        root.destroy()
        return
    with server:
        MULTI_HANDLE, MULTI = accounts.reserve_multi_instance()
        Thread = threading.Thread
        Thread(target=server.serve_forever, daemon=True).start()
        Thread(target=watch, daemon=True).start()
        desktop = Desktop(root, PORT, ADMIN, ASSETS, accounts.read(SETTINGS, {}))
        try:
            desktop.add_tray(tray.attach(root, ASSETS))
        except ImportError:
            desktop.notice.config(text="Instale as dependências para habilitar a bandeja.")
        try:
            root.mainloop()
        finally:
            server.shutdown()

if __name__ == "__main__":
    main()
