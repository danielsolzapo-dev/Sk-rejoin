"""Windows notification icon with callbacks posted to the Tk thread."""
from queue import Queue


def attach(root, assets):
    import pystray
    from PIL import Image
    actions = Queue()
    icon = pystray.Icon(
        "sk-rejoin", Image.open(assets / "artwork" / "portrait.png"), "SK Rejoin",
        pystray.Menu(
            pystray.MenuItem("Mostrar", lambda *_: actions.put("show"), default=True),
            pystray.MenuItem("Encerrar", lambda *_: actions.put("exit")),
        ),
    )

    def poll():
        if not actions.empty():
            if actions.get() == "exit":
                icon.stop()
                root.destroy()
                return
            root.deiconify()
            root.lift()
        root.after(150, poll)

    def hide():
        root.withdraw()

    def stop(event):
        if event.widget is root:
            icon.stop()

    icon.run_detached()
    root.protocol("WM_DELETE_WINDOW", hide)
    root.bind("<Destroy>", stop, add="+")
    root.after(150, poll)
    return hide
