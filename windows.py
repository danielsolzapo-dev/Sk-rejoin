"""Count Roblox processes and resize windows owned by newly started PIDs."""
import ctypes as c
import os
import time
from ctypes import wintypes as w


def running(names=None):
    if os.name != "nt":
        raise ValueError("A fila de janelas requer Windows.")
    kernel = c.WinDLL("kernel32", use_last_error=True)
    class Entry(c.Structure):
        _fields_ = [
            ("size", w.DWORD), ("usage", w.DWORD), ("pid", w.DWORD),
            ("heap", c.c_size_t), ("module", w.DWORD), ("threads", w.DWORD),
            ("parent", w.DWORD), ("priority", w.LONG), ("flags", w.DWORD),
            ("exe", w.WCHAR * 260),
        ]
    snapshot = kernel.CreateToolhelp32Snapshot
    snapshot.argtypes, snapshot.restype = [w.DWORD, w.DWORD], w.HANDLE
    close = kernel.CloseHandle
    close.argtypes, close.restype = [w.HANDLE], w.BOOL
    first, next_entry = kernel.Process32FirstW, kernel.Process32NextW
    for fn in (first, next_entry):
        fn.argtypes, fn.restype = [w.HANDLE, c.POINTER(Entry)], w.BOOL
    handle = snapshot(2, 0)
    if handle == c.c_void_p(-1).value:
        raise ValueError("Windows não retornou a lista de processos.")
    try:
        entry = Entry()
        entry.size = c.sizeof(entry)
        if not first(handle, c.byref(entry)):
            raise ValueError("Windows não retornou a lista de processos.")
        result = set()
        while True:
            if names is None and entry.exe.lower() in ("robloxplayerbeta.exe", "windows10universal.exe") or names is not None and entry.exe.lower() in names:
                result.add(entry.pid)
            if not next_entry(handle, c.byref(entry)):
                return result
    finally:
        close(handle)


def compact(pid, width, height, deadline):
    user = c.WinDLL("user32", use_last_error=True)
    callback = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    user.EnumWindows.argtypes, user.EnumWindows.restype = [callback, w.LPARAM], w.BOOL
    user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
    user.IsWindowVisible.argtypes, user.IsWindowVisible.restype = [w.HWND], w.BOOL
    user.SetWindowPos.argtypes = [w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT]
    user.SetWindowPos.restype = w.BOOL
    user.GetWindowRect.argtypes, user.GetWindowRect.restype = [w.HWND, c.POINTER(w.RECT)], w.BOOL
    user.IsZoomed.argtypes, user.IsZoomed.restype = [w.HWND], w.BOOL
    user.ShowWindowAsync.argtypes = [w.HWND, c.c_int]
    while time.monotonic() < deadline and pid in running():
        windows = []

        @callback
        def collect(hwnd, _):
            owner = w.DWORD()
            user.GetWindowThreadProcessId(hwnd, c.byref(owner))
            if owner.value == pid and user.IsWindowVisible(hwnd):
                windows.append(hwnd)
            return True

        user.EnumWindows(collect, 0)
        for hwnd in windows:
            if user.IsZoomed(hwnd):
                user.ShowWindowAsync(hwnd, 9)
            if user.SetWindowPos(hwnd, None, 0, 0, width, height, 0x4016):
                time.sleep(.4)
                rect = w.RECT()
                if user.GetWindowRect(hwnd, c.byref(rect)):
                    return rect.right - rect.left, rect.bottom - rect.top
        time.sleep(.5)
    return None


def process_stamp(pid):
    """Creation time identifies the process even when Windows reuses its PID."""
    kernel = c.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes, kernel.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
    kernel.GetProcessTimes.argtypes = [w.HANDLE] + [c.POINTER(w.FILETIME)] * 4
    kernel.GetProcessTimes.restype = w.BOOL
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [w.HANDLE], w.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ValueError("Sem acesso à identidade do processo Roblox.")
    try:
        times = [w.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(c.byref(t) for t in times)):
            raise ValueError("Não foi possível identificar a criação do processo.")
        return times[0].dwHighDateTime << 32 | times[0].dwLowDateTime
    finally:
        kernel.CloseHandle(handle)


def same_process(pid, created):
    try:
        return pid in running() and process_stamp(pid) == created
    except (ValueError, OSError):
        # Unknown permissions must not admit a duplicate instance.
        return True


def executable_running(path):
    from pathlib import Path
    kernel = c.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes, kernel.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = w.BOOL
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [w.HANDLE], w.BOOL
    for pid in running({Path(path).name.lower()}):
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            continue
        try:
            buffer = c.create_unicode_buffer(32768)
            size = w.DWORD(len(buffer))
            if kernel.QueryFullProcessImageNameW(handle, 0, buffer, c.byref(size)) and os.path.normcase(buffer.value) == os.path.normcase(path):
                return True
        finally:
            kernel.CloseHandle(handle)
    return False


def close_bound(pid, created):
    """Terminate only a Roblox process with the expected creation timestamp."""
    if pid not in running() or process_stamp(pid) != created:
        raise ValueError("O processo mudou. Nenhuma janela foi fechada.")
    kernel = c.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes, kernel.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
    kernel.GetProcessTimes.argtypes = [w.HANDLE] + [c.POINTER(w.FILETIME)] * 4
    kernel.GetProcessTimes.restype = w.BOOL
    kernel.TerminateProcess.argtypes, kernel.TerminateProcess.restype = [w.HANDLE, w.UINT], w.BOOL
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [w.HANDLE], w.BOOL
    handle = kernel.OpenProcess(0x1001, False, pid)
    if not handle:
        raise ValueError("Sem permissão para reiniciar esta janela do Roblox.")
    try:
        times = [w.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(c.byref(t) for t in times)) or (times[0].dwHighDateTime << 32 | times[0].dwLowDateTime) != created:
            raise ValueError("A identidade do processo mudou.")
        if not kernel.TerminateProcess(handle, 0):
            raise ValueError("O Windows não encerrou esta janela.")
    finally:
        kernel.CloseHandle(handle)
