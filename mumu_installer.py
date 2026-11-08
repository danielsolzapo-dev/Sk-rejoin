"""Explicit, local MuMu APK installation. Never handles Roblox sessions or scripts."""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import NamedTemporaryFile
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

SOURCE_PAGE = 'https://deltaexploits.gg/delta-executor-android'
DOWNLOAD_PAGE = 'https://delta.filenetwork.vip/android.html'
INDEX_URL = 'https://delta.filenetwork.vip/get_files.php'
FILE_BASE = 'https://delta.filenetwork.vip/file/'
MAX_APK = 512 * 1024 * 1024
MAX_INDEX = 256 * 1024

class InstallerError(ValueError): pass
class Cancelled(InstallerError): pass

def check_cancel(cancel):
    if cancel.is_set(): raise Cancelled('Operação cancelada antes de iniciar a próxima etapa.')

def secure_url(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
        raise InstallerError('O download precisa usar HTTPS sem credenciais na URL.')
    host=parsed.hostname.lower()
    if host=='localhost' or host.endswith(('.localhost','.local')):
        raise InstallerError('Endereço de download local recusado.')
    try:
        if not ipaddress.ip_address(host).is_global:raise InstallerError('Endereço de download privado recusado.')
    except ValueError as error:
        if isinstance(error,InstallerError):raise
    return url

class SecureRedirect(HTTPRedirectHandler):
    max_redirections=5
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        secure_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def open_download(url):
    secure_url(url)
    return build_opener(SecureRedirect()).open(Request(url,headers={
        'User-Agent':'Mozilla/5.0 SK-Rejoin/0.12.1','Referer':DOWNLOAD_PAGE}),timeout=25)

def latest_delta(cancel, opener=open_download):
    check_cancel(cancel)
    with opener(INDEX_URL) as response:
        payload=response.read(MAX_INDEX+1)
    if len(payload)>MAX_INDEX:raise InstallerError('A lista de versões ultrapassou o limite.')
    try:data=json.loads(payload)
    except (ValueError,UnicodeError):raise InstallerError('O site não entregou a lista de versões. Abra a página de download para conferir.') from None
    files=data.get('latest_apk') if isinstance(data,dict) else None
    if not isinstance(files,list) or len(files)!=1:
        raise InstallerError('O site não indicou um único APK atual. Use um APK local ou confira a página de download.')
    item=files[0]
    name=item.get('name','') if isinstance(item,dict) else ''
    size=item.get('size') if isinstance(item,dict) else None
    if not re.fullmatch(r'Delta-[A-Za-z0-9._-]{1,100}\.apk',name) or type(size) is not int or not 0<size<=MAX_APK:
        raise InstallerError('Os dados do APK atual são inválidos. Nenhum arquivo foi instalado.')
    return {'name':name,'size':size,'url':FILE_BASE+quote(name),'source':SOURCE_PAGE}

def validate_apk(path):
    path=Path(path)
    size=path.stat().st_size
    if not 0<size<=MAX_APK:raise InstallerError('O APK está vazio ou ultrapassa 512 MiB.')
    try:
        with zipfile.ZipFile(path) as archive:
            infos=archive.infolist()
            names={item.filename for item in infos}
            if len(infos)>100000 or 'AndroidManifest.xml' not in names or not any(re.fullmatch(r'classes\d*\.dex',name) for name in names):
                raise InstallerError('O arquivo não contém a estrutura esperada de um APK Android.')
            manifest=archive.getinfo('AndroidManifest.xml')
            if manifest.flag_bits&1 or not 0<manifest.file_size<=16*1024*1024:
                raise InstallerError('Manifesto Android inválido.')
            # Reading the small manifest checks its CRC without extracting archive paths.
            archive.read('AndroidManifest.xml')
    except (OSError,zipfile.BadZipFile,RuntimeError,KeyError):
        raise InstallerError('APK inválido ou incompleto. Baixe novamente.') from None
    return size

def download_delta(directory,cancel,progress=lambda *args:None,opener=open_download):
    progress('Consultando versão atual…',0,None)
    item=latest_delta(cancel,opener)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    temporary=None
    digest=hashlib.sha256();received=0
    try:
        check_cancel(cancel)
        with opener(item['url']) as response:
            secure_url(response.geturl())
            kind=response.headers.get('Content-Type','').lower()
            if 'text/' in kind or 'html' in kind or 'json' in kind:
                raise InstallerError('O site entregou uma página, não um APK. Conclua o download no navegador e selecione APK local.')
            length=response.headers.get('Content-Length')
            if length and (not length.isdigit() or int(length)!=item['size']):
                raise InstallerError('O tamanho anunciado do download diverge da lista de versões.')
            with NamedTemporaryFile(dir=directory,suffix='.part',delete=False) as output:
                temporary=Path(output.name)
                while True:
                    check_cancel(cancel)
                    chunk=response.read(256*1024)
                    if not chunk:break
                    received+=len(chunk)
                    if received>item['size'] or received>MAX_APK:raise InstallerError('O download ultrapassou o tamanho anunciado.')
                    output.write(chunk);digest.update(chunk)
                    progress('Baixando '+item['name'],received,item['size'])
        if received!=item['size']:raise InstallerError('Download incompleto. Nenhum APK foi instalado.')
        check_cancel(cancel);validate_apk(temporary)
        checksum=digest.hexdigest()
        target=directory/(checksum+'.apk')
        temporary.replace(target);temporary=None
        return {**item,'path':str(target),'sha256':checksum}
    finally:
        if temporary:temporary.unlink(missing_ok=True)

def local_serial(value):
    value=str(value).strip()
    match=re.fullmatch(r'(?:127\.0\.0\.1|localhost):(\d{1,5})',value)
    if match and 0<int(match[1])<=65535:return '127.0.0.1:'+str(int(match[1]))
    if re.fullmatch(r'emulator-\d{1,5}',value):return value
    raise InstallerError('Selecione uma instância local do MuMu ou informe 127.0.0.1:porta.')

def adb_path(path):
    path=Path(path).expanduser().resolve()
    if not path.is_file() or path.name.casefold() not in ('adb.exe','adb_server.exe'):
        raise InstallerError('Selecione o adb.exe do MuMu ou do Android Platform Tools.')
    return path

def discover_adb():
    bases=[os.environ.get('ProgramFiles',''),os.environ.get('ProgramFiles(x86)',''),os.environ.get('LOCALAPPDATA','')]
    patterns=('Netease/MuMuPlayer*/nx_main/adb.exe','Netease/MuMuPlayer*/adb.exe','MuMuPlayer*/nx_main/adb.exe','Netease/MuMuPlayer*/shell/adb.exe','Nemu/vmonitor/bin/adb_server.exe')
    found=[]
    for base in bases:
        if not base:continue
        for pattern in patterns:
            for candidate in Path(base).glob(pattern):
                if candidate.is_file() and str(candidate) not in found:found.append(str(candidate))
    return found

def command(adb,args,timeout=25,runner=subprocess.run):
    exe=adb_path(adb)
    try:
        result=runner([str(exe),*args],capture_output=True,text=True,encoding='utf-8',errors='replace',
                      timeout=timeout,shell=False,creationflags=0x08000000 if os.name=='nt' else 0)
    except subprocess.TimeoutExpired:raise InstallerError('O ADB demorou demais. Confira o MuMu e tente novamente; uma instalação já iniciada pode concluir no Android.') from None
    except OSError:raise InstallerError('Não foi possível executar o ADB escolhido.') from None
    text=(result.stdout+'\n'+result.stderr).strip()
    if result.returncode:raise InstallerError('O ADB retornou erro: '+text[-600:])
    return text

def devices(adb,runner=subprocess.run):
    output=command(adb,['devices','-l'],runner=runner)
    result=[]
    for line in output.splitlines():
        parts=line.split()
        if len(parts)<2 or parts[1]!='device':continue
        try:serial=local_serial(parts[0])
        except InstallerError:continue
        result.append(serial)
    return list(dict.fromkeys(result))

def connect(adb,serial,runner=subprocess.run):
    serial=local_serial(serial)
    if serial.startswith('emulator-'):raise InstallerError('Para conectar, use a porta ADB mostrada no MuMu.')
    command(adb,['connect',serial],runner=runner)
    if serial not in devices(adb,runner):raise InstallerError('A instância não ficou pronta. Ative o ADB no MuMu e confira a porta.')
    return serial

def install_apk(adb,serial,path,cancel,runner=subprocess.run):
    serial=local_serial(serial);validate_apk(path);check_cancel(cancel)
    if serial not in devices(adb,runner):raise InstallerError('A instância selecionada não está conectada. Nenhum APK foi instalado.')
    check_cancel(cancel)
    output=command(adb,['-s',serial,'install','-r',str(Path(path).resolve())],timeout=240,runner=runner)
    if not any(line.strip()=='Success' for line in output.splitlines()):
        if 'UPDATE_INCOMPATIBLE' in output or 'INCONSISTENT_CERTIFICATES' in output:
            raise InstallerError('A assinatura difere da versão instalada. O APP não desinstalou nada; confira a instalação no MuMu.')
        raise InstallerError('O Android não confirmou a instalação: '+output[-600:])
    return 'APK instalado na instância '+serial+'. Abra o aplicativo no MuMu para concluir a configuração.'
