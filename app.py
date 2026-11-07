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
import startup
import bridge_commands

ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
KEY = accounts.read(accounts.ROOT / "heartbeat-key.json", None) or secrets.token_urlsafe(32)
accounts.write(accounts.ROOT / "heartbeat-key.json", KEY)
ADMIN = secrets.token_urlsafe(32)
TRACKER_KEY = secrets.token_urlsafe(32)
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
            binding = BINDINGS.get(identity)
            process_open = bool(binding and windows.same_process(*binding))
            if beat and age < 20:
                connection = "Erro " + str(beat["errorCode"]) if beat.get("errorCode") else ("Conectado" if beat.get("readyForBlock") else "Carregando")
            else:
                connection = "Roblox aberto · sem sinal" if process_open else ("Sem sinal" if beat else "Sem sessão")
            diag = dict(BLOCK_DIAG.get(identity, {}))
            diag["nextIn"] = max(0, round(diag.pop("next", 0) - now))
            row.update(connection=connection, processOpen=process_open, block=diag, errorCode=beat.get("errorCode") if beat else None,
                       fpsSupported=beat.get("fpsSupported") if beat else None, jobId=beat.get("jobId", "") if beat else "", status=status, age=age, place=beat["place"] if beat else None,
                       connected=round(now - beat["since"]) if beat and age < 20 else None,
                       profile=profiles.get(str(identity), {}), rejoin=bool(policy),
                       attempts=policy["attempts"] if policy else 0,
                       maxAttempts=policy["max_attempts"] if policy else None, nextIn=next_in)
        return {"bridgeProtocol": 2, "bridgeCommands": bridge_commands.snapshot(), "machine": machine_status(), "accounts": rows, "waiting": WAITING, "busy": BUSY, "version": update.VERSION,
                "startupStatus": STARTUP_STATUS, "rejoin": len(REJOIN), "blockACC": block_enabled(), "economy": bool(accounts.read(SETTINGS, {}).get("economy")), "multi": multi_status(), "repo": accounts.read(ASSETS / "distribution.json", {}).get("repo", "")}

HISTORY = accounts.ROOT / "sk-history.json"
SETTINGS = accounts.ROOT / "sk-settings.json"
QUEUE_CANCEL = threading.Event()
WAITING = 0
PROFILES = accounts.ROOT / "sk-account-profiles.json"
BINDINGS = {}
SERVER_TARGETS = {}
BLOCK_DIAG = {}
STARTUP_CANCEL = threading.Event()
STARTUP_STATUS = ""
APP_EXIT = None
MACHINE_CACHE = (0, {})


def startup_sequence():
    settings = accounts.read(SETTINGS, {})
    def log(message):
        global STARTUP_STATUS
        STARTUP_STATUS = message
        record("Inicialização", message)
    def launch_accounts(ids):
        known = {a["userId"] for a in accounts.accounts()}
        profiles = accounts.read(PROFILES, {})
        selected = [i for i in ids if i in known and not (i in BINDINGS and windows.same_process(*BINDINGS[i]))
                    and not (i in LIVE and time.monotonic() - LIVE[i]["received"] < 20)]
        if not selected:
            log("Contas já abertas ou nenhuma conta disponível para iniciar")
            return
        for identity in selected:
            place = profiles.get(str(identity), {}).get("place")
            if type(place) is not int or not 0 < place < 10**16:
                raise ValueError("Salve um perfil com Place ID para cada conta da inicialização.")
        start_job({"ids": selected, "place": profiles[str(selected[0])]["place"], "use_profiles": True})
    try:
        startup.sequence(settings, log, launch_accounts, STARTUP_CANCEL)
    except (ValueError, OSError) as error:
        log("Inicialização interrompida · " + str(error))

def record(identity, event):
    with LOCK:
        entries = accounts.read(HISTORY, [])
        entries.append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "account": identity, "event": event})
        accounts.write(HISTORY, entries[-500:])

def save_profiles():
    profiles = accounts.read(PROFILES, {})
    for identity, policy in REJOIN.items():
        profiles.setdefault(str(identity), {}).update({key: policy[key] for key in ("place", "delay", "max_attempts", "attempts")})
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
    for row in accounts.auth_diagnostics():
        checks.append(f"Autenticação {row['account']}: etapa {row.get('stage', '—')} · ticket HTTP {row.get('ticketHTTP', '—')} · enviado ao launcher: {'sim' if row.get('handedOff') else 'não'}. {row.get('message', '')}")
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


def choose_server(identity, place, excluded=()):
    with LOCK:
        active_jobs(identity, place)
    options = server_picker.candidates(place)
    with LOCK:
        occupied = active_jobs(identity, place)
        for job in options:
            if job not in occupied and job not in excluded:
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
            BLOCK_DIAG.pop(identity, None)
            if STATUS.get(identity, "").startswith("BLOCK ACC"):
                STATUS[identity] = "Online"
            return {}
        keeper = min(members)[1]
        BLOCK_DIAG[identity] = {"conflictUserId": keeper, "current": beat["jobId"],
                                "target": SERVER_TARGETS.get(identity, {}).get("jobId", ""),
                                "next": time.monotonic() + max(0, 10 - (time.monotonic() - beat.get("joined", beat["since"])))}
        if not beat.get("readyForBlock") or time.monotonic() - beat.get("joined", beat["since"]) < 10:
            STATUS[identity] = "BLOCK ACC · aguardando jogo carregado e 10 s de conexão"
            return {}
        place = beat["place"]
        if beat.get("retryIn", 0) > 0:
            BLOCK_DIAG[identity]["next"] = time.monotonic() + beat["retryIn"]
            STATUS[identity] = "BLOCK ACC · aguardando próxima tentativa"
            return {}
        failed = beat.get("failedJobId", "")
        STATUS[identity] = "BLOCK ACC · procurando outro servidor"
    try:
        job = choose_server(identity, place, excluded={failed} if failed else ())
        with LOCK:
            if not block_enabled():
                SERVER_TARGETS.pop(identity, None)
                return {}
            STATUS[identity] = "BLOCK ACC · troca de servidor solicitada"
            BLOCK_DIAG[identity].update(target=job, next=time.monotonic() + 15)
        return {"relocate": {"placeId": place, "jobId": job}}
    except (ValueError, OSError):
        with LOCK:
            STATUS[identity] = "BLOCK ACC · aguardando outro servidor para rejoin"
            BLOCK_DIAG.setdefault(identity, {}).update(next=time.monotonic() + 15)
        return {"retry": True}


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
                binding = BINDINGS.get(identity)
                if value.get("recover"):
                    if binding and windows.same_process(*binding):
                        windows.close_bound(*binding)
                        deadline = time.monotonic() + 10
                        while windows.same_process(*binding) and time.monotonic() < deadline:
                            if QUEUE_CANCEL.wait(.25):
                                return
                        if windows.same_process(*binding):
                            raise ValueError("A janela anterior ainda está encerrando. Tente novamente.")
                    elif LIVE.get(identity) and time.monotonic() - LIVE[identity]["received"] < 20 and not binding:
                        raise ValueError("Conta sem PID vinculado. Feche apenas essa janela e abra pelo SK Rejoin.")
                    with LOCK:
                        BINDINGS.pop(identity, None)
                        LIVE.pop(identity, None)
                        SERVER_TARGETS.pop(identity, None)
                        BLOCK_DIAG.pop(identity, None)
                    record(row["username"], "Rejoin da janela vinculada solicitado")
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
                dimensions = profile if value.get("use_profiles", True) else {}
                size = windows.compact(pid, dimensions.get("width", settings["width"]), dimensions.get("height", settings["height"]), time.monotonic() + 15)
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


def save_account_profile(value):
    ids = value.get("ids")
    if not isinstance(ids, list) or not ids or len(ids) > 100 or any(type(i) is not int for i in ids):
        raise ValueError("Selecione contas cadastradas.")
    limits = (("place", 1, 10**16-1), ("delay", 10, 3600), ("max_attempts", 1, 20),
              ("width", 160, 1920), ("height", 120, 1080), ("fps", 1, 240))
    profile = {}
    if "rejoin" in value and type(value["rejoin"]) is not bool:
        raise ValueError("Opção de reconexão inválida.")
    for key, lo, hi in limits:
        number = value.get(key)
        if type(number) is not int or not lo <= number <= hi:
            raise ValueError("Confira os valores do perfil.")
        profile[key] = number
    with LOCK:
        if BUSY:
            raise ValueError("Aguarde a fila terminar antes de salvar perfis.")
        profiles = accounts.read(PROFILES, {})
        known = {a["userId"] for a in accounts.accounts()}
        if not set(ids) <= known:
            raise ValueError("Conta não cadastrada.")
        for identity in ids:
            profiles.setdefault(str(identity), {}).update(profile)
            if identity in REJOIN:
                REJOIN[identity].update({k: profile[k] for k in ("place", "delay", "max_attempts")})
            if "rejoin" in value:
                profiles[str(identity)]["enabled"] = value["rejoin"]
                if value["rejoin"]:
                    REJOIN[identity] = {**profile, "attempts": 0, "next": 0}
                else:
                    REJOIN.pop(identity, None)
        accounts.write(PROFILES, profiles)
    return {"message": "Perfil salvo para as contas selecionadas."}

def machine_status():
    global MACHINE_CACHE
    now = time.monotonic()
    if now - MACHINE_CACHE[0] < 5:
        return MACHINE_CACHE[1]
    settings = accounts.read(SETTINGS, {})
    web = bootstrapper.state()
    result = {"webLauncherConfigured": web.get("installed") is True,
              "webLauncherRunning": False, "executorConfigured": bool(settings.get("companionPath")),
              "executorRunning": False, "startupStatus": STARTUP_STATUS}
    if os.name == "nt":
        try:
            result["webLauncherRunning"] = bool(web.get("path") and windows.executable_running(web["path"]))
            result["executorRunning"] = bool(settings.get("companionPath") and windows.executable_running(settings["companionPath"]))
        except (ValueError, OSError):
            pass
    MACHINE_CACHE = (now, result)
    return result


def execute_unified(value):
    action = value["action"]
    payload = value.get("payload", {})
    if not isinstance(payload, dict):
        raise ValueError("Dados do comando inválidos.")
    if action == "diagnostic":
        return {"message": "Diagnóstico concluído.", "checks": diagnostic()}
    if action in ("update_check", "update_install"):
        if BUSY or startup.SEQUENCE_LOCK.locked():
            raise ValueError("Aguarde a fila e a preparação deste PC.")
        repo = accounts.read(ASSETS / "distribution.json", {}).get("repo", "")
        info, newer = update.manifest(repo)
        if action == "update_check" or not newer:
            return {"message": "Atualização disponível." if newer else "APP atualizado.", "version": update.VERSION, "available": info["version"]}
        if APP_EXIT is None:
            raise ValueError("Atualização remota requer o APP .exe em execução.")
        update.install(repo)
        threading.Timer(2, APP_EXIT).start()
        return {"message": "Instalação enviada. Aguarde o APP reiniciar e confira a versão.", "available": info["version"]}
    if BUSY or startup.SEQUENCE_LOCK.locked():
        raise ValueError("Aguarde a fila ou a preparação atual deste PC.")
    if action == "prepare":
        STARTUP_CANCEL.clear()
        startup_sequence()
        if STARTUP_STATUS.startswith("Inicialização interrompida"):
            raise ValueError(STARTUP_STATUS)
        return {"message": "Sequência de preparação executada. Consulte a fila de contas do APP.", "stage": STARTUP_STATUS}
    ids = payload.get("ids")
    known = {row["userId"] for row in accounts.accounts()}
    if not isinstance(ids, list) or not ids or len(ids) > 100 or any(type(i) is not int or i not in known for i in ids):
        raise ValueError("Selecione contas salvas neste PC.")
    ids = list(dict.fromkeys(ids))
    if action == "profile":
        return save_account_profile(payload)
    if action == "close":
        # Validate every selected identity before closing any process.
        for identity in ids:
            binding = BINDINGS.get(identity)
            if not binding and LIVE.get(identity) and time.monotonic() - LIVE[identity]["received"] < 20:
                raise ValueError("Conta sem PID seguro. Abra a conta pelo SK Rejoin para controlar a janela.")
        for identity in ids:
            binding = BINDINGS.get(identity)
            if binding and windows.same_process(*binding):
                windows.close_bound(*binding)
            with LOCK:
                REJOIN.pop(identity, None)
                profiles = accounts.read(PROFILES, {})
                profiles.setdefault(str(identity), {})["enabled"] = False
                accounts.write(PROFILES, profiles)
                LIVE.pop(identity, None)
                BINDINGS.pop(identity, None)
                SERVER_TARGETS.pop(identity, None)
                BLOCK_DIAG.pop(identity, None)
                STATUS[identity] = "Fechada pelo painel"
            record(str(identity), "Janela fechada pelo Tracker")
        return {"message": "Fechamento executado para as contas selecionadas."}
    profiles = accounts.read(PROFILES, {})
    place = payload.get("place")
    use_profiles = place is None
    if use_profiles:
        if any(type(profiles.get(str(i), {}).get("place")) is not int for i in ids):
            raise ValueError("Salve o Place ID no perfil de cada conta ou informe um destino.")
        place = profiles[str(ids[0])]["place"]
    if type(place) is not int or not 0 < place < 10**16:
        raise ValueError("Place ID inválido.")
    before = {i: LIVE.get(i, {}).get("session") for i in ids}
    sent = time.monotonic()
    start_job({"ids": ids, "place": place, "use_profiles": use_profiles, "recover": action == "reconnect"})
    deadline = sent + 600
    while BUSY and time.monotonic() < deadline:
        time.sleep(.5)
    if BUSY:
        raise ValueError("A fila continua em andamento. Confira o APP antes de repetir.")
    with LOCK:
        confirmed = [i for i in ids if LIVE.get(i, {}).get("received", 0) >= sent
                     and LIVE[i].get("session") != before[i] and time.monotonic() - LIVE[i]["received"] < 20]
    if len(confirmed) != len(ids):
        raise ValueError("Abertura não confirmada para todas as contas. " + " / ".join(STATUS.get(i, "") for i in ids if i not in confirmed)[:260])
    return {"message": "Nova conexão confirmada pelo Heartbeat para as contas selecionadas."}


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
        expected = KEY if self.path == "/heartbeat" else TRACKER_KEY if self.path in ("/tracker/state", "/tracker/reconnect", "/tracker/command") else ADMIN
        if not secrets.compare_digest(self.headers.get("X-Heartbeat-Key" if self.path == "/heartbeat" else "X-Rejoin-Key", ""), expected):
            return self.reply(401, {"error": "Chave inválida."})
        self.path = {"/tracker/state": "/state", "/tracker/reconnect": "/reconnect"}.get(self.path, self.path)
        try:
            self.connection.settimeout(5)
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 900000:
                raise ValueError("Pedido acima do limite.")
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError("Pedido inválido.")
            if self.path == "/tracker/command":
                return self.reply(200, bridge_commands.submit(value, execute_unified))
            if self.path == "/heartbeat":
                identity, place, session = (value.get(k) for k in ("userId", "placeId", "session"))
                if type(identity) is not int or type(place) is not int or place <= 0 or not isinstance(session, str) or not 1 <= len(session) <= 80:
                    raise ValueError("Heartbeat inválido.")
                job = value.get("jobId", "")
                if not isinstance(job, str) or (job and not server_picker.JOB.fullmatch(job)):
                    raise ValueError("Identificador de servidor inválido.")
                failed_job = value.get("failedJobId", "")
                if not isinstance(failed_job, str) or (failed_job and not server_picker.JOB.fullmatch(failed_job)):
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
                                      "readyForBlock": value.get("readyForBlock") is True, "failedJobId": failed_job,
                                      "errorCode": value.get("errorCode") if type(value.get("errorCode")) is int and value["errorCode"] in (279, 773) else None,
                                      "fpsSupported": value.get("fpsSupported") is True,
                                      "retryIn": min(60, max(0, value.get("retryIn", 0))) if type(value.get("retryIn")) in (int, float) else 0,
                                      "joined": previous.get("joined", now) if previous and previous.get("jobId") == job and previous["session"] == session else now}
                    policy = REJOIN.get(identity)
                    if policy and now - since >= 120 and policy["attempts"] and not LIVE[identity].get("errorCode"):
                        policy["attempts"] = 0
                        policy["next"] = 0
                        save_profiles()
                profile = accounts.read(PROFILES, {}).get(str(identity), {})
                return self.reply(200, {"ok": True, "fps": profile.get("fps"), **collision_action(identity)})
            if self.path == "/startup":
                with LOCK:
                    settings = accounts.read(SETTINGS, {})
                    if value.get("action") == "sequence":
                        if startup.SEQUENCE_LOCK.locked() or BUSY:
                            raise ValueError("Aguarde a sequência ou a fila atual.")
                        STARTUP_CANCEL.clear()
                        threading.Thread(target=startup_sequence, daemon=True).start()
                        return self.reply(200, {"message": "Sequência iniciada. Acompanhe o estado no painel."})
                    if value.get("action") == "cancel":
                        STARTUP_CANCEL.set()
                        return self.reply(200, {"message": "Sequência cancelada. Programas já abertos continuam disponíveis."})
                    if value.get("action") == "open":
                        return self.reply(200, {"message": startup.launch(settings)})
                    enabled = value.get("startWithWindows")
                    companion = value.get("companionEnabled")
                    if type(enabled) is not bool or type(companion) is not bool:
                        raise ValueError("Configuração de inicialização inválida.")
                    path = startup.executable(value.get("companionPath", ""))
                    if companion and not path:
                        raise ValueError("Escolha o aplicativo que será aberto junto.")
                    if startup.SEQUENCE_LOCK.locked():
                        raise ValueError("Cancele a sequência antes de alterar a inicialização.")
                    extra = {}
                    for key in ("startupWebLauncher", "startupAccounts"):
                        extra[key] = value.get(key, settings.get(key, False))
                        if type(extra[key]) is not bool:
                            raise ValueError("Opção de inicialização inválida.")
                    for key, default in (("webLauncherDelay", 10), ("executorDelay", 20)):
                        extra[key] = value.get(key, settings.get(key, default))
                        if type(extra[key]) is not int or not 1 <= extra[key] <= 180:
                            raise ValueError("Use esperas de 1 a 180 segundos.")
                    ids = value.get("startupAccountIds", settings.get("startupAccountIds", []))
                    known = {a["userId"] for a in accounts.accounts()}
                    if not isinstance(ids, list) or len(ids) > 100 or any(type(i) is not int or i not in known for i in ids):
                        raise ValueError("Confira as contas de inicialização.")
                    if extra["startupAccounts"]:
                        profiles = accounts.read(PROFILES, {})
                        if not ids or any(type(profiles.get(str(i), {}).get("place")) is not int for i in ids):
                            raise ValueError("Selecione as contas e salve seus perfis com Place ID primeiro.")
                    extra["startupAccountIds"] = list(dict.fromkeys(ids))
                    startup.set_enabled(enabled)
                    settings.update(startWithWindows=enabled, companionEnabled=companion, companionPath=path)
                    settings.update(extra)
                    accounts.write(SETTINGS, settings)
                return self.reply(200, {"message": "Configurações de inicialização salvas."})
            if self.path == "/profile":
                return self.reply(200, save_account_profile(value))
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
                        BLOCK_DIAG.clear()
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
            if self.path == "/auth-check":
                identity = value.get("id")
                if type(identity) is not int:
                    raise ValueError("Selecione uma conta cadastrada.")
                row = next((row for row in accounts.accounts() if row["userId"] == identity), None)
                if not row:
                    raise ValueError("Conta não cadastrada neste PC.")
                return self.reply(200, {"result": accounts.check_launch_auth(row["username"], value.get("place"))})
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
            if self.path in ("/launch", "/reconnect"):
                if self.path == "/reconnect":
                    value["recover"] = True
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
                        for mapping in (LIVE, REJOIN, STATUS, BINDINGS, SERVER_TARGETS, BLOCK_DIAG):
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
                                profiles.setdefault(str(identity), {}).update({"place": place, "delay": delay,
                                    "max_attempts": maximum, "attempts": 0, "enabled": True})
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
            fault = bool(beat and beat.get("errorCode") in (279, 773) and now - beat["received"] < 20)
            if not beat or (not fault and now - beat["received"] < policy["delay"]) or now < policy["next"]:
                continue
            if policy["attempts"] >= policy["max_attempts"]:
                STATUS[identity] = "Limite de tentativas atingido · reative para tentar novamente"
                continue
            binding = BINDINGS.get(identity)
            if not fault and binding and windows.same_process(*binding):
                STATUS[identity] = "Sem sinal · instância ainda aberta; confira o coletor"
                continue
            policy["attempts"] += 1
            policy["next"] = now + min(3600, policy["delay"] * 2 ** min(policy["attempts"] - 1, 10))
            save_profiles()
            try:
                record(str(identity), f"Reconexão {policy['attempts']}/{policy['max_attempts']}")
                if fault:
                    record(str(identity), "Recuperando erro " + str(beat["errorCode"]))
                payload = {"ids": [identity], "place": policy["place"]}
                if fault:
                    payload["recover"] = True
                start_job(payload, remember_place=False)
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
    global MULTI_HANDLE, MULTI, APP_EXIT
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
        settings = accounts.read(SETTINGS, {})
        if settings.get("startWithWindows"):
            try:
                startup.set_enabled(True)
            except (ValueError, OSError) as error:
                record("Inicialização", str(error))
        desktop = Desktop(root, PORT, ADMIN, ASSETS, settings)
        APP_EXIT = lambda: desktop.events.put((lambda value, error: root.destroy(), None, None))
        accounts.write(accounts.ROOT / "tracker-bridge.json", {"port": PORT, "key": TRACKER_KEY})
        root.after(1500, lambda: threading.Thread(target=startup_sequence, daemon=True).start())
        try:
            desktop.add_tray(tray.attach(root, ASSETS))
        except ImportError:
            desktop.notice.config(text="Instale as dependências para habilitar a bandeja.")
        try:
            root.mainloop()
        finally:
            STARTUP_CANCEL.set()
            server.shutdown()

if __name__ == "__main__":
    main()

