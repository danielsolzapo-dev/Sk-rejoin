"""Shared redaction at diagnostic/history boundaries; never a credential exporter."""
import re

_PATTERNS = (
    (re.compile(r"(?i)roblox-(?:player|studio):\S+"), "[protocolo omitido]"),
    (re.compile(r"(?i)(?:https?|wss?)://\S+"), "[URL omitida]"),
    (re.compile(r"(?i)\bBearer\s+[^\s,;]+"), "Bearer [omitido]"),
    (re.compile(r"(?im)\.ROBLOSECURITY\s*[:=]\s*[^\r\n]+"), ".ROBLOSECURITY=[omitido]"),
    (re.compile(r'''(?ix)(["']?(?:password|senha|cookie|token|ticket|authorization|x-csrf-token|rbx-authentication-ticket|x-rejoin-key|x-heartbeat-key)["']?\s*[:=]\s*)(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;]+)'''), r"\1[omitido]"),
)


def redact(value: object) -> str:
    text = str(value)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
