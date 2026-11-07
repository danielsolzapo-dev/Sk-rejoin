"""Design tokens and ttk styling. No third-party theme or business rules."""
import os

SPACING = (4, 8, 12, 16)
RADII = {'small': 4, 'panel': 8}  # ttk native rectangles stay square for dense tables.
FONT = 'Segoe UI'
FONT_SIZES = {'caption': 8, 'body': 9, 'heading': 12, 'title': 16}
ROW_HEIGHT = 20
DARK = dict(bg='#0d131d', surface='#161f2c', border='#3a485b', text='#edf3fc',
            muted='#aabbd1', accent='#a6caff', success='#91ddb2', warning='#f2d294',
            error='#ffacb5', info='#b9d7ff', field='#0c1420', button='#25354b',
            primary='#295788', selection='#254d77', alternate='#121b28', hover='#354b67')
LIGHT = dict(bg='#eef2f8', surface='#ffffff', border='#9aa9bd', text='#142237',
             muted='#4c5d75', accent='#1f4f8a', success='#17633e', warning='#795000',
             error='#9e2634', info='#244f87', field='#f8faff', button='#e2e9f3',
             primary='#244f80', selection='#d7e7fb', alternate='#f4f7fc', hover='#cad9ec')
PALETTES = {'dark': DARK, 'light': LIGHT}
# Original colors are aliases so existing dialogs can migrate incrementally.
ALIASES = {'#242424':'bg', '#2d2d2d':'surface', '#505050':'border', '#eeeeee':'text',
           '#bcbcbc':'muted', '#82b5f2':'accent', '#383838':'button', '#3b587b':'selection',
           '#303030':'button', '#464646':'hover', '#202020':'field', '#454545':'button',
           '#414141':'button', '#555555':'hover', '#292929':'alternate', '#b4dbb6':'success',
           '#bbbbbb':'muted', '#ffa0a0':'error', '#e9ce8d':'warning', '#47698f':'primary',
           '#739fce':'hover', '#ffffff':'surface'}


def windows_theme():
    if os.name != 'nt': return 'dark'
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            return 'light' if winreg.QueryValueEx(key, 'AppsUseLightTheme')[0] else 'dark'
    except OSError: return 'dark'


def enable_dpi():
    if os.name == 'nt':
        import ctypes
        try: ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError): pass


def resolve(color, palette):
    key = ALIASES.get(str(color).lower())
    if key: return palette[key]
    for source in PALETTES.values():
        for name, value in source.items():
            if str(color).lower() == value: return palette[name]
    return color


def apply(root, palette, scale=1.0):
    from tkinter import ttk
    # Native themed controls keep keyboard/focus behavior and do not grow the EXE.
    style = ttk.Style(root)
    style.configure('Treeview', background=palette['surface'], fieldbackground=palette['surface'],
                    foreground=palette['text'], rowheight=round(ROW_HEIGHT*scale), borderwidth=0,
                    bordercolor=palette['border'], font=(FONT, 9))
    style.configure('Treeview.Heading', background=palette['button'], foreground=palette['text'],
                    relief='flat', padding=(6, 4), font=(FONT, 9, 'bold'))
    style.map('Treeview', background=[('selected',palette['selection'])], foreground=[('selected',palette['text'])])
    style.configure('TNotebook', background=palette['bg'], borderwidth=0)
    style.configure('TNotebook.Tab', background=palette['button'], foreground=palette['text'], padding=(12, 6))
    style.map('TNotebook.Tab', background=[('selected',palette['selection'])], foreground=[('selected',palette['text'])])
    style.configure('TCombobox', fieldbackground=palette['field'], background=palette['button'],
                    foreground=palette['text'], arrowcolor=palette['text'])
    style.map('TCombobox', fieldbackground=[('readonly',palette['field'])], foreground=[('readonly',palette['text'])])
    style.configure('TProgressbar', background=palette['accent'], troughcolor=palette['field'])
    for direction in ('Vertical','Horizontal'):
        style.configure(direction+'.TScrollbar', background=palette['button'], troughcolor=palette['bg'], borderwidth=0)
    def walk(widget):
        for option in ('background','foreground','activebackground','activeforeground',
                       'insertbackground','highlightbackground','highlightcolor','selectcolor','selectbackground','selectforeground'):
            try:
                current = widget.cget(option)
                mapped = palette['text'] if option=='selectforeground' else resolve(current, palette)
                if str(current).lower() in ('systembuttonface','systemwindow','systemwindowtext','systembuttontext','white','black'):
                    mapped=palette['field'] if option=='background' and widget.winfo_class() in ('Entry','Text','Listbox') else palette['surface'] if option.endswith('background') or option in ('background','selectcolor') else palette['text']
                if mapped != current: widget.configure(**{option:mapped})
            except Exception: pass  # ttk options differ by widget; no I/O or business exceptions here.
        if widget.winfo_class() == 'Button':
            primary = getattr(widget, '_sk_primary', False)
            widget.configure(bg=palette['primary'] if primary else palette['button'],
                             fg='#ffffff' if primary else palette['text'],
                             activebackground=palette['primary'] if primary else palette['hover'],
                             activeforeground='#ffffff' if primary else palette['text'],
                             relief='flat', bd=0, highlightthickness=1,
                             highlightbackground=palette['border'], highlightcolor=palette['accent'])
        if widget.winfo_class() == 'Menu':
            widget.configure(bg=palette['surface'],fg=palette['text'],activebackground=palette['selection'],activeforeground=palette['text'])
            try:
                end = widget.index('end')
                for index in range((end or 0)+1):
                    if widget.type(index)=='cascade': walk(widget.nametowidget(widget.entrycget(index,'menu')))
            except Exception: pass
        for child in widget.winfo_children(): walk(child)
    walk(root)
    root.configure(bg=palette['bg'])

def scale_for(root):
    """Use Windows DPI rather than Tk's default points-to-pixels rounding."""
    if os.environ.get('SK_UI_CAPTURE_SCALE') in ('1.0','1.5'):
        return float(os.environ['SK_UI_CAPTURE_SCALE'])
    if os.name=='nt':
        try:
            import ctypes
            fn=ctypes.windll.user32.GetDpiForWindow
            fn.argtypes=[ctypes.c_void_p];fn.restype=ctypes.c_uint
            dpi=fn(root.winfo_id())
            if dpi:return max(1.0,dpi/96)
        except (AttributeError,OSError):pass
    return max(1.0,round(root.winfo_fpixels('1i')/96*4)/4)
