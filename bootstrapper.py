"""Manage the WebLauncher release selected by the user, without handling Roblox sessions."""
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from urllib.request import Request, urlopen

import accounts

REPOSITORY = 'vnnaworks/weblauncher'
RELEASES_URL = 'https://github.com/vnnaworks/weblauncher/releases'
API_URL = 'https://api.github.com/repos/' + REPOSITORY + '/releases/latest'
TOOLS = accounts.ROOT / 'tools' / 'weblauncher'
SETTINGS = accounts.ROOT / 'sk-bootstrapper.json'
LOCK = threading.Lock()
MAX_SIZE = 64 * 1024 * 1024


def release():
    request = Request(API_URL, headers={'User-Agent': 'SK-Rejoin', 'Accept': 'application/vnd.github+json'})
    with urlopen(request, timeout=20) as response:
        raw = response.read(262145)
    if len(raw) > 262144:
        raise ValueError('Resposta do GitHub acima do limite.')
    data = json.loads(raw)
    tag = data.get('tag_name', '')
    if data.get('draft') or data.get('prerelease') or not re.fullmatch(r'[A-Za-z0-9._-]{1,60}', tag):
        raise ValueError('A versão publicada não é compatível.')
    asset = next((item for item in data.get('assets', []) if item.get('name') == 'weblauncher.exe'), None)
    expected = f'https://github.com/{REPOSITORY}/releases/download/{tag}/weblauncher.exe'
    if not asset or asset.get('browser_download_url') != expected:
        raise ValueError('O executável esperado não está disponível nessa versão.')
    digest = asset.get('digest', '')
    if not isinstance(digest, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
        raise ValueError('O GitHub não forneceu SHA-256 para verificar esse download.')
    size = asset.get('size')
    if type(size) is not int or not 0 < size <= MAX_SIZE:
        raise ValueError('Tamanho do WebLauncher fora do limite.')
    return {'version': tag, 'size': size, 'sha256': digest[7:], 'url': expected}


def state():
    saved = accounts.read(SETTINGS, {})
    path = saved.get('path', '')
    return {'path': path, 'installed': bool(path and Path(path).is_file()),
            'version': saved.get('version', ''), 'verified': bool(saved.get('sha256')),
            'releases': RELEASES_URL}


def download():
    if not LOCK.acquire(blocking=False):
        raise ValueError('Aguarde a operação atual do WebLauncher.')
    temporary = None
    try:
        info = release()
        target = TOOLS / info['version'] / 'weblauncher.exe'
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.download')
        digest = hashlib.sha256()
        size = 0
        with urlopen(Request(info['url'], headers={'User-Agent': 'SK-Rejoin'}), timeout=30) as response, temporary.open('wb') as output:
            while chunk := response.read(65536):
                size += len(chunk)
                if size > info['size']:
                    raise ValueError('O download ultrapassou o tamanho publicado.')
                digest.update(chunk)
                output.write(chunk)
        if size != info['size'] or digest.hexdigest() != info['sha256']:
            raise ValueError('Falha na integridade do WebLauncher. O arquivo foi descartado.')
        temporary.replace(target)
        accounts.write(SETTINGS, {'path': str(target), 'version': info['version'], 'sha256': info['sha256']})
        return state()
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        LOCK.release()


def select(path):
    if not isinstance(path, str) or not 1 <= len(path) <= 2048:
        raise ValueError('Escolha o executável do WebLauncher neste PC.')
    file = Path(path)
    if not file.is_absolute() or file.suffix.lower() != '.exe' or not file.is_file():
        raise ValueError('Escolha um arquivo .exe existente.')
    with LOCK:
        accounts.write(SETTINGS, {'path': str(file), 'version': 'Escolhido manualmente'})
    return state()


def open_tool():
    if os.name != 'nt':
        raise ValueError('Disponível no Windows.')
    saved = accounts.read(SETTINGS, {})
    file = Path(saved.get('path', ''))
    if not file.is_file() or file.suffix.lower() != '.exe':
        raise ValueError('Baixe ou escolha o WebLauncher primeiro.')
    expected = saved.get('sha256')
    if expected and hashlib.sha256(file.read_bytes()).hexdigest() != expected:
        raise ValueError('O executável foi alterado. Baixe novamente antes de abrir.')
    os.startfile(str(file))
    return state()
