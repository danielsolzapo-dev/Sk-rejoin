"""BloxTracker's own local session vault, official-site login helper and game launcher."""
import os,sys,json,time,re,uuid,base64,threading,subprocess,secrets
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler,ProxyHandler,getproxies
from urllib.error import HTTPError
from urllib.parse import quote,urlencode
ROOT=Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'RejoinDesk'
ROOT.mkdir(parents=True, exist_ok=True)
VAULT=ROOT/'native-sessions.json'
LOCK=threading.RLock()
SUPPORTED=os.name=='nt'
USERNAME=re.compile(r'[A-Za-z0-9_]{3,20}\Z')

def read(path,default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return default

def write(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');temporary.replace(path)

def protect(raw,decrypt=False):
    if not SUPPORTED:raise ValueError('O gerenciador próprio usa a proteção de sessões do Windows.')
    import ctypes
    from ctypes import wintypes as W
    class Blob(ctypes.Structure):_fields_=[('size',W.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(raw);source=Blob(len(raw),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));target=Blob()
    dll=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    fn=dll.CryptUnprotectData if decrypt else dll.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,W.DWORD,ctypes.POINTER(Blob)];fn.restype=W.BOOL
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):raise ValueError('O Windows não conseguiu acessar a sessão protegida. Adicione a conta novamente neste usuário Windows.')
    try:return ctypes.string_at(target.data,target.size)
    finally:kernel.LocalFree(target.data)

def valid_cookie(cookie):return isinstance(cookie,str) and bool(re.fullmatch(r'[\x21-\x7e]{30,8192}',cookie)) and ';' not in cookie

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Redirecionamento da autenticação recusado. Faça login novamente.')

URLS={'identity':'https://users.roblox.com/v1/users/authenticated','ticket':'https://auth.roblox.com/v1/authentication-ticket/'}
def network_diagnostic():
    # Only report presence; proxy URLs may contain credentials.
    try:
        proxies = getproxies()
        enabled = bool(proxies.get("https") or proxies.get("all"))
        return "Rede da autenticação: configuração padrão do sistema/ambiente; proxy HTTPS detectado: " + ("sim" if enabled else "não") + ". PAC e proxy próprio do launcher podem diferir."
    except Exception:
        return "Rede da autenticação: configuração padrão; não foi possível consultar a presença de proxy."

def request_roblox(kind,cookie,ua='',csrf=None,place=None):
    if kind not in URLS or not valid_cookie(cookie):raise ValueError('Sessão local inválida. Adicione a conta novamente.')
    headers={'Cookie':'.ROBLOSECURITY='+cookie,'User-Agent':ua if isinstance(ua,str) and re.fullmatch(r'[\x20-\x7e]{1,512}',ua) else 'RejoinDesk/0.1','Accept':'application/json'}
    if kind=='ticket':
        # The endpoint requires JSON media type, including for an empty object.
        headers['Content-Type']='application/json'
        headers['Referer']='https://www.roblox.com/games/'+str(place or 0)
        if csrf:headers['X-CSRF-TOKEN']=csrf
    request=Request(URLS[kind],headers=headers,data=b'{}' if kind=='ticket' else None,method='POST' if kind=='ticket' else 'GET')
    try:
        with build_opener(ProxyHandler(),NoRedirect()).open(request,timeout=15) as response:
            raw=response.read(32769)
            if len(raw)>32768:raise ValueError('Resposta de autenticação inválida.')
            return response.status,dict(response.headers),raw
    except HTTPError as exc:
        # Never expose the body, cookies, ticket, URL or challenge details to the dashboard.
        return exc.code,dict(exc.headers),b''
    except ValueError:raise
    except Exception:raise ValueError('Não foi possível falar com o Roblox. Confira a conexão deste PC.') from None

def authenticated(cookie,ua=''):
    code,_,raw=request_roblox('identity',cookie,ua)
    if code!=200:raise ValueError('Validação da sessão recusada pelo Roblox (HTTP '+str(code)+'). Confira o login oficial e a conexão deste PC.')
    try:
        value=json.loads(raw);identity=value['id'];name=value['name'];display=value.get('displayName',name)
        if type(identity) is not int or not 0<identity<10**16 or not isinstance(name,str) or not USERNAME.fullmatch(name) or not isinstance(display,str) or len(display)>100:raise ValueError()
    except (ValueError,KeyError,TypeError):raise ValueError('A identificação retornada pelo Roblox é inválida.') from None
    return {'userId':identity,'username':name,'displayName':display}

def save_session(cookie,ua='',*,expected_username=None):
    identity=authenticated(cookie,ua)
    if expected_username and identity['username'].casefold()!=expected_username.casefold():
        raise ValueError('A sessão recebida pertence a outra conta.')
    encrypted=base64.b64encode(protect(json.dumps({'cookie':cookie,'ua':ua}).encode())).decode()
    with LOCK:
        vault=read(VAULT,{})
        if len(vault)>=100 and str(identity['userId']) not in vault:raise ValueError('Limite de 100 contas neste PC.')
        vault[str(identity['userId'])]={**identity,'session':encrypted,'saved':time.time()};write(VAULT,vault)
    return identity

def accounts():
    result=[]
    for identity,value in read(VAULT,{}).items():
        if not isinstance(value,dict) or not isinstance(value.get('username'),str) or not USERNAME.fullmatch(value['username']):continue
        result.append({k:value.get(k) for k in ('userId','username','displayName','saved')})
    return result

def load_session(username):
    value=next((v for v in read(VAULT,{}).values() if isinstance(v,dict) and v.get('username','').casefold()==username.casefold()),None)
    if not value:raise ValueError('Conta não cadastrada no gerenciador próprio deste PC.')
    try:
        secret=json.loads(protect(base64.b64decode(value['session']),True))
        if not valid_cookie(secret.get('cookie')):raise ValueError()
        return value,secret
    except Exception:raise ValueError('Sessão protegida indisponível. Adicione a conta novamente neste usuário Windows.') from None

def open_game(uri):os.startfile(uri)

class LaunchCancelled(ValueError):pass

AUTH_DIAGNOSTICS = {}


def _store_auth(username, report):
    with LOCK:
        AUTH_DIAGNOSTICS[username.casefold()] = dict(report, account=username, time=time.time())
        if len(AUTH_DIAGNOSTICS) > 100:
            del AUTH_DIAGNOSTICS[next(iter(AUTH_DIAGNOSTICS))]


def auth_diagnostics():
    with LOCK:
        return sorted((dict(row) for row in AUTH_DIAGNOSTICS.values()), key=lambda row: row["time"], reverse=True)[:6]


def _prepare_ticket(username, place, report):
    report["stage"] = "sessão"
    metadata, secret = load_session(username)
    cookie, ua = secret["cookie"], secret.get("ua", "")
    current = authenticated(cookie, ua)
    if current["userId"] != metadata["userId"]:
        raise ValueError("A identidade da sessão mudou. Adicione a conta novamente.")
    report["sessionValid"] = True
    report["stage"] = "ticket"
    code, headers, _ = request_roblox("ticket", cookie, ua, place=place)
    normalized = {key.lower(): value for key, value in headers.items()}
    report["ticketHTTP"] = code
    report["challenge"] = bool(normalized.get("rblx-challenge-id") or normalized.get("rblx-challenge-type"))
    if report["challenge"]:
        raise ValueError("O Roblox solicitou uma verificação adicional. Conclua o login oficial neste PC.")
    csrf = normalized.get("x-csrf-token")
    if code == 403 and isinstance(csrf, str) and re.fullmatch(r"[\x21-\x7e]{1,1024}", csrf):
        report["csrfRetry"] = True
        code, headers, _ = request_roblox("ticket", cookie, ua, csrf=csrf, place=place)
        normalized = {key.lower(): value for key, value in headers.items()}
        report["ticketHTTP"] = code
        report["challenge"] = bool(normalized.get("rblx-challenge-id") or normalized.get("rblx-challenge-type"))
    if report["challenge"]:
        raise ValueError("O Roblox solicitou uma verificação adicional. Conclua o login oficial neste PC.")
    ticket = normalized.get("rbx-authentication-ticket", "")
    if code != 200 or not re.fullmatch(r"[A-Za-z0-9_+/=-]{10,8192}", ticket):
        raise ValueError("Emissão do ticket recusada pelo Roblox (HTTP " + str(code) + "). Confira Testar autenticação.")
    report["ticketIssued"] = True
    return ticket


def check_launch_auth(username, place):
    if not isinstance(username, str) or not USERNAME.fullmatch(username) or type(place) is not int or not 0 < place < 10**16:
        raise ValueError("Selecione uma conta e informe um Place ID válido.")
    report = {"sessionValid": False, "csrfRetry": False, "ticketIssued": False, "handedOff": False}
    try:
        _prepare_ticket(username, place, report)
        report.update(stage="verificado", message="Sessão válida e ticket emitido. O teste não abriu o Roblox.")
    except ValueError as error:
        report["message"] = str(error)
    _store_auth(username, report)
    return dict(report)


def launch(username,place,job='',before_open=None):
    if not SUPPORTED:raise ValueError('A abertura do Roblox está disponível no Windows.')
    if not isinstance(username,str) or not USERNAME.fullmatch(username) or type(place) is not int or not 0<place<10**16 or not isinstance(job,str) or (job and not re.fullmatch('[A-Za-z0-9-]{1,80}',job)):raise ValueError('Conta ou destino inválido.')
    report = {"sessionValid": False, "csrfRetry": False, "ticketIssued": False, "handedOff": False}
    try:
        ticket = _prepare_ticket(username, place, report)
        browser_tracker = str(secrets.randbelow(9_000_000_000) + 1_000_000_000)
        destination='https://assetgame.roblox.com/game/PlaceLauncher.ashx?'+urlencode({'request':'RequestGameJob' if job else 'RequestGame','browserTrackerId':browser_tracker,'placeId':place,'isPlayTogetherGame':'false',**({'gameId':job} if job else {})})
        uri='roblox-player:1+launchmode:play+gameinfo:'+ticket+'+launchtime:'+str(int(time.time()*1000))+'+placelauncherurl:'+quote(destination,safe='')+'+browsertrackerid:'+browser_tracker+'+robloxLocale:pt_br+gameLocale:pt_br+channel:+LaunchExp:InApp'
        if before_open is not None and not before_open():raise LaunchCancelled('Reconexão cancelada após a conferência final.')
        report["stage"] = "launcher"
        try:open_game(uri)
        except Exception:raise ValueError('Windows não abriu o protocolo Roblox. Confira se o cliente oficial está instalado neste PC.') from None
        report.update(handedOff=True, message="Ticket emitido e abertura enviada ao launcher registrado no Windows.")
        return True
    except ValueError as error:
        report["message"] = str(error)
        raise
    finally:
        _store_auth(username, report)


def reserve_multi_instance():
    """Keep a Windows mutex open for the lifetime of this process."""
    if not SUPPORTED:
        return None, "Disponível no Windows."
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateMutexW(None, True, "ROBLOX_singletonMutex")
    if not handle:
        return None, "Windows recusou a reserva para múltiplas instâncias."
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle(handle)
        return None, "Abra o Rejoin Desk antes do Roblox para tentar múltiplas instâncias."
    return handle, "Reserva de múltiplas instâncias ativa. Confirme cada abertura pelo heartbeat."

def remove_accounts(identities):
    with LOCK:
        vault = read(VAULT, {})
        for identity in identities:
            vault.pop(str(identity), None)
        write(VAULT, vault)

