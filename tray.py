"""Tray presentation. OS/file work is outside Tk; menu actions use its event queue."""
from ui_text import tr
from queue import Empty, Queue
from threading import Thread

def attach(root, assets, callbacks=None, state=None, preferences=None):
    callbacks = callbacks or {}
    events = Queue()
    holder = {}
    last_status = None

    def worker():
        try:
            import pystray
            from PIL import Image
            image = Image.open(assets / 'artwork' / 'portrait.png').convert('RGBA')

            def post(name):
                return lambda *_: events.put(name)
            items = [(tr('ui_25de7deebb0e'), 'toggle'), (tr('ui_d98fa42977b6'), 'pause'), (tr('ui_240f5d622131'), 'reconnect'), (tr('ui_7b5d3cf0ada7'), 'config'), (tr('ui_dbdc71231635'), 'updates'), (tr('ui_3ffa2a9e9b4d'), 'exit')]
            icon = pystray.Icon('sk-rejoin', image, tr('ui_4176882510c1'), pystray.Menu(*[pystray.MenuItem(label, post(action), default=action == 'toggle') for label, action in items]))
            holder['icon'] = icon
            holder['image'] = image
            icon.run_detached()
        except Exception:
            events.put('unavailable')
    Thread(target=worker, daemon=True).start()

    def hide():
        if holder.get('icon') and (preferences is None or preferences().get('minimizeToTray', True)):
            root.withdraw()
        else:
            root.iconify()

    def poll():
        nonlocal last_status
        try:
            while True:
                action = events.get_nowait()
                if action == 'exit':
                    if holder.get('icon'):
                        holder['icon'].stop()
                    root.destroy()
                    return
                if action == 'toggle':
                    if root.state() == 'withdrawn':
                        root.deiconify()
                        root.lift()
                    else:
                        root.withdraw()
                elif action in callbacks:
                    callbacks[action]()
        except Empty:
            pass
        if state and holder.get('icon'):
            rows = state().get('accounts', [])
            summary = tr('ui_c9701a7da6bb') if any((row.get('errorCode') for row in rows)) else tr('ui_5c2ce717bc1e') if state().get('busy') else tr('ui_eb72a691665b')
            if summary != last_status:
                last_status = summary
                icon = holder['icon']
                Thread(target=lambda: setattr(icon, 'title', tr('ui_3b34fef83c49') + summary), daemon=True).start()

                def update_icon(value=summary):
                    from PIL import ImageDraw
                    image = holder['image'].copy()
                    color = '#ba3346' if value == tr('ui_c9701a7da6bb') else '#9b6a10' if value == tr('ui_5c2ce717bc1e') else '#287545'
                    draw = ImageDraw.Draw(image)
                    size = image.width
                    draw.ellipse((size * 0.64, size * 0.64, size * 0.96, size * 0.96), fill=color, outline='white', width=max(1, size // 40))
                    icon.icon = image
                    if preferences and preferences().get('notifications') and (value == tr('ui_c9701a7da6bb')):
                        try:
                            icon.notify(tr('ui_e77ce596f92d'), tr('ui_91a76a81ddea'))
                        except Exception:
                            pass
                Thread(target=update_icon, daemon=True).start()
        root.after(200, poll)

    def stop(event):
        if event.widget is root and holder.get('icon'):
            holder['icon'].stop()
    root.protocol('WM_DELETE_WINDOW', hide)
    root.bind('<Destroy>', stop, add='+')
    root.after(200, poll)
    return hide
