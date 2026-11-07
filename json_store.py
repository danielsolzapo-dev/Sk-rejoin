"""Atomic legacy-compatible JSON storage with bounded recovery notices.

No envelope is introduced: Tracker and existing installations keep their layouts.
Locks serialize reads/replacements within this process, not whole read/modify cycles.
"""
from collections import deque
from copy import deepcopy
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
import threading

_LOCK = threading.RLock()
_NOTICES: deque[str] = deque(maxlen=30)


def notices() -> list[str]:
    with _LOCK:
        return list(_NOTICES)


def _decode(path: Path, default: object) -> object:
    value = json.loads(path.read_text(encoding="utf-8-sig"),
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")))
    if default is not None and type(value) is not type(default):
        raise ValueError("Unexpected JSON shape")
    return value


def _replace(path: Path, value: object) -> None:
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                prefix=path.name + ".", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read(path: Path, default: object) -> object:
    path = Path(path)
    with _LOCK:
        backup = path.with_name(path.name + ".bak")
        if not path.exists() and not backup.exists():
            return deepcopy(default)
        try:
            return _decode(path, default)
        except (OSError, ValueError, UnicodeError):
            try:
                restored = _decode(backup, default)
            except (OSError, ValueError, UnicodeError):
                raise ValueError(
                    f"Arquivo {path.name} inválido ou inacessível, sem backup válido. "
                    "Os dados foram preservados. Restaure uma cópia antes de continuar."
                ) from None
            # Do not replace the existing backup with the corrupt primary.
            _replace(path, restored)
            _NOTICES.append(f"Backup de {path.name} restaurado. Confira os dados recuperados.")
            return restored


def write(path: Path, value: object) -> None:
    path = Path(path)
    with _LOCK:
        # Validate serialization before changing either file.
        json.dumps(value, ensure_ascii=False, allow_nan=False)
        if path.exists() or path.with_name(path.name + ".bak").exists():
            previous = read(path, None)
        else:
            previous = value
        _replace(path.with_name(path.name + ".bak"), previous)
        _replace(path, value)
