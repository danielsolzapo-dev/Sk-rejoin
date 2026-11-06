"""Verified GitHub release download and explicit Windows binary replacement."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import urlopen

VERSION = "0.7.3"
LIMIT = 100 * 1024 * 1024

def version(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,5}\.\d{1,5}\.\d{1,5}", value):
        raise ValueError("Versão inválida.")
    return tuple(map(int, value.split(".")))

def manifest(repo):
    if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Informe o repositório no formato dono/repo.")
    with urlopen(f"https://github.com/{repo}/releases/latest/download/rejoin-manifest.json", timeout=15) as response:
        raw = response.read(8193)
    if len(raw) > 8192:
        raise ValueError("Manifesto acima do limite.")
    info = json.loads(raw)
    if not isinstance(info, dict) or info.get("app") != "RejoinDesk":
        raise ValueError("Manifesto não pertence ao Rejoin Desk.")
    remote = info.get("version")
    newer = version(remote) > version(VERSION)
    if type(info.get("size")) is not int or not 0 < info["size"] <= LIMIT:
        raise ValueError("Tamanho de atualização inválido.")
    if not re.fullmatch(r"[a-f0-9]{64}", str(info.get("sha256", ""))):
        raise ValueError("Hash de atualização inválido.")
    return info, newer

def install(repo):
    if os.name != "nt" or not getattr(sys, "frozen", False):
        raise ValueError("Instalação automática disponível na edição autônoma compilada.")
    info, newer = manifest(repo)
    if not newer:
        raise ValueError("Você já está na versão mais recente.")
    executable = Path(sys.executable).resolve()
    staged = executable.with_name(executable.name + ".pending")
    created = False
    digest = hashlib.sha256()
    size = 0
    try:
        with urlopen(f"https://github.com/{repo}/releases/download/v{info['version']}/RejoinDesk.exe", timeout=25) as response, staged.open("xb") as output:
            created = True
            while chunk := response.read(65536):
                size += len(chunk)
                if size > info["size"]:
                    raise ValueError("Download acima do tamanho esperado.")
                digest.update(chunk)
                output.write(chunk)
        if size != info["size"] or digest.hexdigest() != info["sha256"]:
            raise ValueError("A atualização falhou na verificação de integridade.")
        script = """
$ErrorActionPreference = 'Stop'
$target = $env:REJOIN_UPDATE_TARGET
$staged = $target + '.pending'
$backup = $target + '.previous'
for ($i=0; $i -lt 80; $i++) {
  try { [IO.File]::Replace($staged, $target, $backup); $env:PYINSTALLER_RESET_ENVIRONMENT = '1'; Start-Process -FilePath $target; exit 0 }
  catch { Start-Sleep -Milliseconds 500 }
}
"""
        import base64
        encoded = base64.b64encode(script.encode("utf-16-le")).decode()
        subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                         env={**os.environ, "REJOIN_UPDATE_TARGET": str(executable)}, creationflags=0x08000000)
    except Exception:
        if created:
            staged.unlink(missing_ok=True)
        raise
