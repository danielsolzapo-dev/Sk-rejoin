"""Reversible low-resource rendering settings for the selected Roblox installation."""
import json
import os
from pathlib import Path
import re
import threading

import accounts

LOCK = threading.RLock()
RECEIPT = accounts.ROOT / 'sk-optimization.json'
FLAGS = {
    'DFFlagTextureQualityOverrideEnabled': True,
    'DFIntTextureQualityOverride': 0,
    'FIntDebugForceMSAASamples': 1,
    'DFIntDebugFRMQualityLevelOverride': 1,
    'FIntFRMMinGrassDistance': 0,
    'FIntFRMMaxGrassDistance': 0,
    'DFIntCSGLevelOfDetailSwitchingDistance': 0,
    'DFIntCSGLevelOfDetailSwitchingDistanceL12': 0,
    'DFIntCSGLevelOfDetailSwitchingDistanceL23': 0,
    'DFIntCSGLevelOfDetailSwitchingDistanceL34': 0,
}


def installation(folder=''):
    if folder:
        path = Path(folder).expanduser().resolve()
        if not (path / 'RobloxPlayerBeta.exe').is_file():
            raise ValueError('Escolha a pasta que contém RobloxPlayerBeta.exe.')
        return path
    if os.name == 'nt':
        import winreg
        for key in (r'roblox-player\shell\open\command', r'roblox\DefaultIcon'):
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key) as handle:
                    command = os.path.expandvars(winreg.QueryValueEx(handle, '')[0])
                match = re.search(r'"([^"]+\.exe)"|^(.+?\.exe)(?:\s|,|$)', command, re.I)
                if match:
                    path = Path(match.group(1) or match.group(2)).parent
                    if (path / 'RobloxPlayerBeta.exe').is_file():
                        return path.resolve()
            except OSError:
                continue
    raise ValueError('Escolha a pasta do Roblox usada pelo WebLauncher para aplicar os ajustes.')


def load_flags(target):
    if not target.exists():
        return {}
    if target.stat().st_size > 1024 * 1024:
        raise ValueError('Arquivo de flags acima de 1 MiB. Confira a instalação.')
    try:
        value = json.loads(target.read_text(encoding='utf-8-sig'))
    except ValueError:
        raise ValueError('ClientAppSettings.json inválido. Corrija o arquivo antes de otimizar.') from None
    if not isinstance(value, dict):
        raise ValueError('ClientAppSettings.json precisa conter um objeto JSON.')
    return value


def apply(folder='', fps=10):
    if type(fps) is not int or not 1 <= fps <= 240:
        raise ValueError('Informe um teto de 1 a 240 FPS.')
    path = installation(folder)
    target = path / 'ClientSettings' / 'ClientAppSettings.json'
    with LOCK:
        values = load_flags(target)
        updates = {**FLAGS, 'DFIntTaskSchedulerTargetFps': fps}
        receipt = accounts.read(RECEIPT, {'installs': {}})
        key = str(path)
        saved = receipt.setdefault('installs', {}).get(key)
        if not saved or saved.get('state') == 'restored':
            saved = {'before': {name: {'present': name in values, 'value': values.get(name)} for name in updates},
                     'state': 'prepared'}
            receipt['installs'][key] = saved
        receipt['last'] = key
        accounts.write(RECEIPT, receipt)
        target.parent.mkdir(parents=True, exist_ok=True)
        accounts.write(target, {**values, **updates})
        saved.update(state='applied', fps=fps)
        accounts.write(RECEIPT, receipt)
    return {'folder': key, 'fps': fps, 'applied': True,
            'message': f'Perfil econômico gravado em {target}. Reabra o Roblox para testar.'}


def restore():
    with LOCK:
        receipt = accounts.read(RECEIPT, {})
        key = receipt.get('last')
        saved = receipt.get('installs', {}).get(key)
        if not saved or saved.get('state') == 'restored':
            raise ValueError('Nenhuma otimização pendente de restauração.')
        target = Path(key) / 'ClientSettings' / 'ClientAppSettings.json'
        if not target.exists():
            raise ValueError('A instalação otimizada não está mais disponível.')
        values = load_flags(target)
        for name, old in saved['before'].items():
            if old['present']:
                values[name] = old['value']
            else:
                values.pop(name, None)
        accounts.write(target, values)
        saved['state'] = 'restored'
        accounts.write(RECEIPT, receipt)
    return {'folder': key, 'applied': False, 'message': 'Flags anteriores restauradas. Reabra o Roblox.'}
