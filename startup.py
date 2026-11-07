"""Opt-in Windows startup and one explicitly selected companion executable."""
import os
from pathlib import Path
import subprocess
import sys

NAME = "SKRejoin"
RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


def executable(value):
    if not isinstance(value, str) or not value.strip():
        return ""
    path = Path(value)
    if not path.is_absolute() or path.suffix.lower() != ".exe" or not path.is_file():
        raise ValueError("Escolha um arquivo .exe existente com caminho completo.")
    path = path.resolve()
    if path == Path(sys.executable).resolve():
        raise ValueError("Escolha outro aplicativo, diferente do SK Rejoin.")
    return str(path)


def set_enabled(enabled):
    if type(enabled) is not bool:
        raise ValueError("Opção de inicialização inválida.")
    if os.name != "nt" or not getattr(sys, "frozen", False):
        if enabled:
            raise ValueError("Inicialização com Windows disponível no aplicativo .exe.")
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN) as key:
        if enabled:
            winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, subprocess.list2cmdline([sys.executable]))
        else:
            try:
                winreg.DeleteValue(key, NAME)
            except FileNotFoundError:
                pass


def launch(settings):
    if not settings.get("companionEnabled"):
        return "Aplicativo adicional desativado."
    path = executable(settings.get("companionPath", ""))
    if not path:
        raise ValueError("Selecione o aplicativo adicional nas configurações.")
    if os.name != "nt":
        raise ValueError("Abertura de aplicativo adicional disponível no Windows.")
    import windows
    if windows.executable_running(path):
        return "Aplicativo adicional já está aberto."
    subprocess.Popen([path], cwd=str(Path(path).parent), shell=False)
    return "Aplicativo adicional iniciado."
