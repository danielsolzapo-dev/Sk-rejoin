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
import bootstrapper
import optimization
import server_picker

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
MULTI_OBSERVED = False

def multi_status():
    if MULTI_OBSERVED:
        return "Múltiplos processos Roblox observados nesta execução. Confira cada conta pelo heartbeat."
    if not MULTI_HANDLE:
        return "Reserva interna indisponível. Tentativas permitidas com launcher externo, até o limite configurado."
    return MULTI


def public_state():
    now = time.monotonic()
    with LOCK:
        profiles = accounts.read(PROFILES, {})
        rows = accounts.accounts()
        for row in rows:
            identity = row["userId"]
            beat = LIVE.get(identity)
            age = round(now - beat["received"]) if beat else None
            policy = REJOIN.get(identity)
            status = STATUS.get(identity, "Pronta")
            if age is not None and age < 20 and not status.startswith("BLOCK ACC"):
                status = "Online"
            elif beat and status in ("Pronta", "Aguardando heartbeat", "Online"):
                status = "Sem sinal"
            next_in = None
            if policy and beat:
                if policy["attempts"] < policy["max_attempts"]:
                    next_in = max(0, round(max(beat["received"] + policy["delay"], policy["next"]) - now))
            row.update(jobId=beat.get("jobId", "") if beat else "", status=status, age=age, place=beat["place"] if beat else None,
                       connected=round(now - beat["since"]) if beat and age < 20 else None,
                       profile=profiles.get(str(identity), {}), rejoin=bool(policy),
                       attempts=policy["attempts"] if policy else 0,
                       maxAttempts=policy["max_attempts"] if policy else None, nextIn=next_in)
        return {"accounts": rows, "waiting": WAITING, "busy": BUSY, "version": update.VERSION,
                "rejoin": len(REJOIN), "blockACC": block_enabled(), "economy": bool(accounts.read(SETTINGS, {}).get("economy")), "multi": multi_status(), "repo": accounts.read(ASSETS / "distribution.json", {}).get("repo", "")}

HISTORY = accounts.ROOT / "sk-history.json"
SETTINGS = accounts.ROOT / "sk-settings.json"
QUEUE_CANCEL = threading.Event()
WAITING = 0
PROFILES = accounts.ROOT / "sk-account-profiles.json"
BINDINGS = {}
SERVER_TARGETS = {}

def record(identity, event):
    with LOCK:
        entries = accounts.read(HISTORY, [])
        entries.append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "account": identity, "event": event})
        accounts.write(HISTORY, entries[-500:])

def save_profiles():
    profiles = accounts.read(PROFILES, {})
    for identity, policy in REJOIN.items():
        profiles[str(identity)] = {key: policy[key] for key in ("place", "delay", "max_attempts", "attempts")}
        profiles[str(identity)]["enabled"] = True
    accounts.write(PROFILES, profiles)


def restore_profiles():
    known = {a["userId"] for a in accounts.accounts()}
    for key, config in accounts.read(PROFILES, {}).items():
        if not str(key).isdigit() or int(key) not in known or not isinstance(config, dict):
            continue
        if config.get("enabled") and all(type(config.get(k)) is int and lo <= config[k] <= hi
                for k, lo, hi in (("place", 1, 10**16-1), ("delay", 10, 3600), ("max_attempts", 1, 20))):
            identity = int(key)
            REJOIN[identity] = {**config, "attempts": max(0, int(config.get("attempts", 0))), "next": 0}
            STATUS[identity] = "Monitoramento restaurado · aguardando novo heartbeat"


def diagnostic():
    checks = ["Windows: " + ("disponível" if os.name == "nt" else "indisponível"), MULTI]
    try:
        checks.append(f"Processos Roblox abertos: {len(windows.running())}")
    except (ValueError, OSError) as error:
        checks.append(str(error))
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"roblox-player\shell\open\command") as key:
                command = winreg.QueryValueEx(key, "")[0]
            checks.append("Protocolo Roblox registrado" if command else "Protocolo Roblox vazio")
        except OSError:
            checks.append("Protocolo Roblox ausente. Abra um jogo pelo site oficial neste PC.")
    checks.append("Sessões locais cadastradas: " + str(len(accounts.accounts())))
    checks.append("Reconexão aguarda um heartbeat desta execução do app antes de monitorar cada conta.")
    return checks


def block_enabled():
    return accounts.read(SETTINGS, {}).get("blockACC") is True


def active_jobs(identity, place):
    now = time.monotonic()
    occupied = set()
    for other, beat in LIVE.items():
        fresh = now - beat["received"] < max(120, REJOIN.get(other, {}).get("delay", 20))
        if other != identity and beat["place"] == place and fresh:
            if not beat.get("jobId"):
                raise ValueError("BLOCK ACC: atualize o heartbeat das contas abertas para informar o servidor.")
            occupied.add(beat["jobId"])
    for other, target in SERVER_TARGETS.items():
        if other != identity and target["place"] == place and target["expires"] > now:
            occupied.add(target["jobId"])
    return occupied


def choose_server(identity, place):
    with LOCK:
        active_jobs(identity, place)
    options = server_picker.candidates(place)
    with LOCK:
        occupied = active_jobs(identity, place)
        for job in options:
            if job not in occupied:
                SERVER_TARGETS[identity] = {"place": place, "jobId": job, "expires": time.monotonic() + 180}
                return job
    raise ValueError("BLOCK ACC: nenhum servidor diferente disponível na consulta. Tente novamente depois.")


def server_confirmed(identity, beat):
    """Confirm the observed server after normal matchmaking or relocation."""
    if not block_enabled():
        return True
    if not beat.get("jobId"):
        return False
    try:
        return beat["jobId"] not in active_jobs(identity, beat["place"])
    except ValueError:
        return False


def collision_action(identity):
    if not block_enabled():
        return {}
    with LOCK:
        beat = LIVE[identity]
        if not beat.get("jobId"):
            return {}
        members = [(other_beat.get("joined", other_beat["since"]), other) for other, other_beat in LIVE.items()
                   if other_beat["place"] == beat["place"] and other_beat.get("jobId") == beat["jobId"]
                   and time.monotonic() - other_beat["received"] < 35]
        if len(members) < 2 or min(members)[1] == identity:
            if STATUS.get(identity, "").startswith("BLOCK ACC"):
                STATUS[identity] = "Online"
            return {}
        place = beat["place"]
        STATUS[identity] = "BLOCK ACC · procurando outro servidor"
    try:
        job = choose_server(identity, place)
        with LOCK:
            if not block_enabled():
                SERVER_TARGETS.pop(identity, None)
                return {}
            STATUS[identity] = "BLOCK ACC · troca de servidor solicitada"
        return {"relocate": {"placeId": place, "jobId": job}}
    except (ValueError, OSError):
        with LOCK:
            STATUS[identity] = "BLOCK ACC · colisão sem destino disponível; confira a conta"
        return {"stop": "BLOCK ACC: outro cliente gerenciado já está neste servidor. Aguarde um destino disponível no app."}


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
        if remember_place:
            settings["place"] = place
        accounts.write(SETTINGS, settings)
        if not MULTI_HANDLE:
            record("Multi Roblox", "Reserva interna indisponível. Tentando a abertura com o launcher registrado no Windows.")
        QUEUE_CANCEL.clear()
        BUSY = True
        WAITING = len(targets)

    def run():
        global BUSY, WAITING, MULTI_OBSERVED
        try:
            for row in targets:
                identity = row["userId"]
                if QUEUE_CANCEL.is_set():
                    break
                with LOCK:
                    STATUS[identity] = "Na fila"
                limit = settings["limit"]
                while len(windows.running()) >= limit:
                    with LOCK:
                        STATUS[identity] = f"Limite configurado atingido ({limit} instâncias)"
                    if QUEUE_CANCEL.wait(1):
                        return
                before = windows.running()
                if QUEUE_CANCEL.is_set():
                    return
                with LOCK:
                    STATUS[identity] = "Abrindo"
                    WAITING -= 1
                    previous_session = LIVE.get(identity, {}).get("session")
                binding = BINDINGS.get(identity)
                if binding and windows.same_process(*binding):
                    with LOCK:
                        STATUS[identity] = "Instância anterior ainda aberta · confira antes de abrir novamente"
                    continue
                profile = accounts.read(PROFILES, {}).get(str(identity), {})
                target_place = profile.get("place", place) if remember_place and value.get("use_profiles") else place
                if type(target_place) is not int or not 0 < target_place < 10**16:
                    raise ValueError("Destino salvo inválido. Reconfigure a conta.")
                sent_at = time.monotonic()
                record(row["username"], "Abertura solicitada")
                try:
                    # Use normal matchmaking for the installed client.
                    # Public job IDs can be stale or incompatible with that version.
                    with LOCK:
                        SERVER_TARGETS.pop(identity, None)
                    job = ""
                    accounts.launch(row["username"], target_place, job=job, before_open=lambda: not QUEUE_CANCEL.is_set())
                    pid = wait_new_pid(before)
                    BINDINGS[identity] = (pid, windows.process_stamp(pid))
                    if before:
                        for _ in range(3):
                            if QUEUE_CANCEL.wait(1):
                                break
                        current = windows.running()
                        if pid in current and before.intersection(current):
                            MULTI_OBSERVED = True
                            record(row["username"], "Novo processo e instância anterior presentes · multi observado")
                        else:
                            record(row["username"], "Abertura enviada; múltiplas instâncias não confirmadas")
                except (ValueError, OSError) as error:
                    with LOCK:
                        STATUS[identity] = str(error)
                    record(row["username"], str(error))
                    break
                size = windows.compact(pid, settings["width"], settings["height"], time.monotonic() + 15)
                with LOCK:
                    STATUS[identity] = "Aguardando heartbeat"
                record(row["username"], f"Janela medida em {size[0]} × {size[1]} px" if size else "Janela compacta não confirmada")
                deadline = time.monotonic() + (90 if block_enabled() else 30)
                confirmed = False
                while time.monotonic() < deadline and not QUEUE_CANCEL.is_set():
                    with LOCK:
                        beat = LIVE.get(identity)
                        confirmed = bool(beat and beat["received"] >= sent_at and beat["place"] == target_place and beat["session"] != previous_session and
                                         server_confirmed(identity, beat))
                    if confirmed:
                        break
                    QUEUE_CANCEL.wait(.5)
                if confirmed:
                    with LOCK:
                        STATUS[identity] = "Online"
                    record(row["username"], "Nova sessão confirmada pelo heartbeat")
                if not confirmed:
                    if block_enabled() and not QUEUE_CANCEL.is_set():
                        message = "BLOCK ACC: servidor não confirmado. Atualize o heartbeat e confira a conta."
                        QUEUE_CANCEL.set()
                    elif QUEUE_CANCEL.is_set():
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
                    if STATUS.get(row["userId"], "").startswith(("Na fila", "Limite configurado")):
                        STATUS[row["userId"]] = "Pronta"
                if not remember_place:
                    for row in targets:
                        policy = REJOIN.get(row["userId"])
                        if policy:
                            policy["next"] = time.monotonic() + min(3600, policy["delay"] * 2 ** min(max(0, policy["attempts"] - 1), 10))
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
                job = value.get("jobId", "")
                if not isinstance(job, str) or (job and not server_picker.JOB.fullmatch(job)):
                    raise ValueError("Identificador de servidor inválido.")
                with LOCK:
                    if not any(a["userId"] == identity for a in accounts.accounts()):
                        return self.reply(404, {"error": "Conta não cadastrada."})
                    previous = LIVE.get(identity)
                    if not previous or time.monotonic() - previous["received"] >= 20:
                        record(str(identity), "Heartbeat recebido")
                    now = time.monotonic()
                    continuous = previous and previous["session"] == session and now - previous["received"] < 20
                    since = previous["since"] if continuous else now
                    LIVE[identity] = {"received": now, "place": place, "session": session, "since": since, "jobId": job,
                                      "joined": previous.get("joined", now) if previous and previous.get("jobId") == job and previous["session"] == session else now}
                    policy = REJOIN.get(identity)
                    if policy and now - since >= 120 and policy["attempts"]:
                        policy["attempts"] = 0
                        policy["next"] = 0
                        save_profiles()
                return self.reply(200, {"ok": True, **collision_action(identity)})
            if self.path == "/optimization":
                with LOCK:
                    if BUSY or windows.running():
                        raise ValueError("Cancele a fila e feche os Roblox antes de alterar o perfil gráfico.")
                    action = value.get("action")
                    if action == "apply":
                        folder = value.get("folder", "")
                        if not isinstance(folder, str) or len(folder) > 2048:
                            raise ValueError("Pasta da instalação inválida.")
                        result = optimization.apply(folder, value.get("fps", 10))
                    elif action == "restore":
                        result = optimization.restore()
                    else:
                        raise ValueError("Ação de otimização inválida.")
                    settings = accounts.read(SETTINGS, {})
                    settings["economy"] = action == "apply"
                    settings["optimizationFolder"] = result["folder"]
                    accounts.write(SETTINGS, settings)
                return self.reply(200, result)
            if self.path == "/block-acc":
                enabled = value.get("enabled")
                if type(enabled) is not bool:
                    raise ValueError("Estado do BLOCK ACC inválido.")
                with LOCK:
                    if BUSY:
                        raise ValueError("Cancele a fila antes de mudar BLOCK ACC.")
                    settings = accounts.read(SETTINGS, {})
                    settings["blockACC"] = enabled
                    accounts.write(SETTINGS, settings)
                    if not enabled:
                        SERVER_TARGETS.clear()
                        for identity, status in list(STATUS.items()):
                            if status.startswith("BLOCK ACC"):
                                STATUS[identity] = "Pronta"
                return self.reply(200, {"enabled": enabled})
            if self.path == "/bootstrapper":
                action = value.get("action", "state")
                if action == "state":
                    result = bootstrapper.state()
                elif action == "check":
                    result = {**bootstrapper.state(), "available": bootstrapper.release()}
                elif action == "download":
                    result = bootstrapper.download()
                elif action == "select":
                    result = bootstrapper.select(value.get("path"))
                elif action == "open":
                    if BUSY:
                        raise ValueError("Cancele a fila de abertura antes de abrir o WebLauncher.")
                    result = bootstrapper.open_tool()
                else:
                    raise ValueError("Ação do WebLauncher inválida.")
                return self.reply(200, result)
            if self.path == "/diagnostic":
                return self.reply(200, {"checks": diagnostic()})
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
                        profiles = accounts.read(PROFILES, {})
                        profiles.pop(str(identity), None)
                        accounts.write(PROFILES, profiles)
                return self.reply(200, {"ok": True})
            if self.path == "/rejoin":
                ids, place = value.get("ids"), value.get("place")
                if not isinstance(ids, list) or len(ids) > 100 or any(type(i) is not int for i in ids):
                    raise ValueError("Seleção inválida.")
                if ids and (type(place) is not int or not 0 < place < 10**16):
                    raise ValueError("Informe um Place ID válido.")
                delay = value.get("rejoin_delay", 20)
                maximum = value.get("max_attempts", 3)
                if ids and (type(delay) is not int or not 10 <= delay <= 3600):
                    raise ValueError("Informe entre 10 e 3600 segundos sem sinal.")
                if ids and (type(maximum) is not int or not 1 <= maximum <= 20):
                    raise ValueError("Use de 1 a 20 tentativas.")
                known = {a["userId"] for a in accounts.accounts()}
                with LOCK:
                    profiles = accounts.read(PROFILES, {})
                    if not ids:
                        for config in profiles.values():
                            config["enabled"] = False
                        REJOIN.clear()
                    else:
                        settings = accounts.read(SETTINGS, {})
                        settings.update(place=place, rejoin_delay=delay, max_attempts=maximum)
                        accounts.write(SETTINGS, settings)
                        for identity in ids:
                            if identity not in known:
                                continue
                            if value.get("disable"):
                                REJOIN.pop(identity, None)
                                profiles.setdefault(str(identity), {})["enabled"] = False
                            else:
                                REJOIN[identity] = {"place": place, "delay": delay,
                                    "max_attempts": maximum, "attempts": 0, "next": 0}
                                profiles[str(identity)] = {"place": place, "delay": delay,
                                    "max_attempts": maximum, "attempts": 0, "enabled": True}
                    accounts.write(PROFILES, profiles)
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

def watch_once():
    with LOCK:
        if BUSY:
            return
        now = time.monotonic()
        for identity, policy in REJOIN.items():
            beat = LIVE.get(identity)
            if not beat or now - beat["received"] < policy["delay"] or now < policy["next"]:
                continue
            if policy["attempts"] >= policy["max_attempts"]:
                STATUS[identity] = "Limite de tentativas atingido · reative para tentar novamente"
                continue
            binding = BINDINGS.get(identity)
            if binding and windows.same_process(*binding):
                STATUS[identity] = "Sem sinal · instância ainda aberta; confira o coletor"
                continue
            policy["attempts"] += 1
            policy["next"] = now + min(3600, policy["delay"] * 2 ** min(policy["attempts"] - 1, 10))
            save_profiles()
            try:
                record(str(identity), f"Reconexão {policy['attempts']}/{policy['max_attempts']}")
                start_job({"ids": [identity], "place": policy["place"]}, remember_place=False)
            except (ValueError, OSError) as error:
                STATUS[identity] = str(error)
                record(str(identity), str(error))
            break


def watch():
    while True:
        time.sleep(2)
        try:
            watch_once()
        except (ValueError, OSError) as error:
            record("Monitor", str(error))

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
        restore_profiles()
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
