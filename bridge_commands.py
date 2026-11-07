"""Durable, bounded commands. Accepted IDs are never replayed after restart."""
import re
import threading
import time
import accounts

PATH = accounts.ROOT / 'tracker-commands.json'
LOCK = threading.RLock()
WORK = threading.Lock()
ACTIVE = set()
ACTIONS = {'open', 'reconnect', 'close', 'profile', 'prepare', 'diagnostic', 'update_check', 'update_install'}


def snapshot():
    with LOCK:
        rows = accounts.read(PATH, {})
        changed = False
        for identity, row in rows.items():
            if row['status'] in ('received', 'running') and identity not in ACTIVE:
                row.update(status='uncertain', message='Aplicativo reiniciado antes de confirmar o resultado.')
                changed = True
        if changed:
            accounts.write(PATH, rows)
        return sorted(rows.values(), key=lambda row: row['created'], reverse=True)[:30]


def submit(value, execute):
    identity, action = value.get('id'), value.get('action')
    if not isinstance(identity, str) or not re.fullmatch(r'[a-f0-9]{32}', identity) or action not in ACTIONS:
        raise ValueError('Comando de integração inválido.')
    expires = value.get('expires')
    if type(expires) not in (int, float) or not time.time() < expires <= time.time() + 65:
        raise ValueError('O comando expirou.')
    with LOCK:
        rows = accounts.read(PATH, {})
        if identity in rows:
            return rows[identity]
        if len(ACTIVE) >= 20:
            raise ValueError('Aguarde os comandos pendentes.')
        receipt = {'id': identity, 'action': action, 'status': 'received', 'created': time.time(),
                   'message': 'Pedido recebido pelo SK Rejoin.'}
        rows[identity] = receipt
        # Keep active receipts even if many later commands finish.
        rows = {k: v for k, v in rows.items() if k in ACTIVE or k == identity or k in list(rows)[-200:]}
        accounts.write(PATH, rows)
        ACTIVE.add(identity)

    def mark(status, message, result=None):
        with LOCK:
            rows = accounts.read(PATH, {})
            rows[identity].update(status=status, message=message, updated=time.time())
            if result is not None:
                rows[identity]['result'] = result
            accounts.write(PATH, rows)

    def run():
        try:
            with WORK:
                if time.time() >= expires:
                    mark('failed', 'Pedido expirou antes de iniciar a execução.')
                    return
                mark('running', 'Executando no PC de destino.')
                result = execute(value) or {}
                mark('completed', result.get('message', 'Operação concluída.'), result)
        except (ValueError, OSError) as error:
            mark('failed', str(error)[:400])
        except Exception:
            mark('uncertain', 'Resultado não confirmado. Confira o aplicativo antes de repetir.')
        finally:
            with LOCK:
                ACTIVE.discard(identity)
    threading.Thread(target=run, daemon=True).start()
    return receipt
