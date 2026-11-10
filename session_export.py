"""Explicit local session export. No HTTP, persistence, logging or password recovery."""
import accounts
from ui_text import tr


def export_session(username, mode='cookie', password='', *, loader=None):
    if mode not in ('cookie', 'combined'):
        raise ValueError(tr('export_invalid'))
    if not isinstance(username, str) or not accounts.USERNAME.fullmatch(username):
        raise ValueError(tr('export_invalid'))
    if mode == 'combined' and (not isinstance(password, str) or not password or '\n' in password or '\r' in password or '\x00' in password):
        raise ValueError(tr('export_password_required'))
    try:
        identity, secret = (loader or accounts.load_session)(username)
        name = identity['username']
        cookie = secret['cookie']
        if not isinstance(name, str) or not accounts.USERNAME.fullmatch(name) or name.casefold() != username.casefold() or not accounts.valid_cookie(cookie):
            raise ValueError()
    except Exception:
        # Upstream exceptions can contain arbitrary data. Never display their contents.
        raise ValueError(tr('export_unavailable')) from None
    return cookie if mode == 'cookie' else f'{name}:{password}:{cookie}'


class SessionClipboard:
    """Tk-thread only: expire our latest copy without deleting a user's later copy."""
    def __init__(self, root, seconds=30):
        self.root = root
        self.seconds = seconds
        self.value = None
        self.timer = None
        self.revision = 0

    def copy(self, value):
        self.revision += 1
        revision = self.revision
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        # If append fails after clear, no old value should remain retained here.
        self.value = None
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.value = value
        self.timer = self.root.after(self.seconds * 1000, lambda: self.expire(revision))

    def expire(self, revision):
        if revision != self.revision:
            return
        self.timer = None
        try:
            if self.value is not None and self.root.clipboard_get() == self.value:
                self.root.clipboard_clear()
        except Exception:
            pass
        finally:
            self.value = None
