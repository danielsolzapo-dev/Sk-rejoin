"""MuMu installer view: state rendering and worker dispatch only."""
from pathlib import Path
from threading import Event, Thread
import time
import tkinter as tk
from tkinter import ttk, filedialog
import webbrowser
import accounts
import mumu_installer as installer
from ui_text import tr

class MuMuUI:
    def mumu_dialog(self):
        existing=getattr(self,'mumu_window',None)
        if existing and existing.winfo_exists():existing.deiconify();existing.lift();return
        body=self.dialog(tr('mumu_title'))
        window=body.winfo_toplevel();self.mumu_window=window
        cancel=Event();self._mumu_task_active=getattr(self,'_mumu_task_active',False)
        self.label(body,tr('mumu_intro'),wrap=570,color=self.palette['muted']).pack(anchor='w',pady=(0,8))
        self.label(body,tr('mumu_adb')).pack(anchor='w')
        adb=tk.StringVar(value=self.ui_prefs.get('mumuAdb',''))
        adb_field=ttk.Combobox(body,textvariable=adb);adb_field.pack(fill='x',pady=4)
        row=tk.Frame(body);row.pack(fill='x',pady=4)
        self.label(body,tr('mumu_port')).pack(anchor='w',pady=(8,0))
        endpoint=tk.StringVar(value=self.ui_prefs.get('mumuEndpoint',''))
        field=self.entry(body);field.config(textvariable=endpoint);field.pack(fill='x',pady=4)
        self.label(body,tr('mumu_instance')).pack(anchor='w',pady=(8,0))
        serial=tk.StringVar();selector=ttk.Combobox(body,textvariable=serial,state='readonly')
        selector.pack(fill='x',pady=4)
        status=self.label(body,tr('mumu_idle'),wrap=570,color=self.palette['muted']);status.pack(anchor='w',pady=8)
        progress=ttk.Progressbar(body,mode='determinate',maximum=100);progress.pack(fill='x',pady=4)
        buttons=tk.Frame(body);buttons.pack(fill='x',pady=4)
        action_buttons=[]
        cancel_button=self.button(body,tr('mumu_cancel'),cancel.set);cancel_button.pack(anchor='w',pady=4)
        cancel_button.config(state='disabled');cancel_button._sk_reason=tr('mumu_no_operation')
        self.label(body,tr('mumu_limits'),wrap=570,color=self.palette['muted']).pack(anchor='w',pady=6)
        def alive():return bool(window.winfo_exists())
        def display(message,received=0,total=None):
            if not alive():return
            status.config(text=message)
            if total:progress.config(value=received/total*100)
        last_progress=[0,None]
        def post(message,received=0,total=None):
            now=time.monotonic()
            if message==last_progress[1] and total and received<total and now-last_progress[0]<.15:return
            last_progress[:]=[now,message]
            self.events.put((lambda value,error:display(*value), (message,received,total),None))
        def worker_task(work,finished=None):
            if self._mumu_task_active:
                status.config(text=tr('mumu_busy'));return
            self._mumu_task_active=True;cancel.clear()
            for button in action_buttons:button.config(state='disabled');button._sk_reason=tr('mumu_busy')
            cancel_button.config(state='normal');progress.config(value=0)
            def complete(value,error):
                self._mumu_task_active=False
                if not alive():return
                for button in action_buttons:button.config(state='normal')
                cancel_button.config(state='disabled')
                if error:status.config(text=error,fg=self.palette['error'])
                elif finished:finished(value)
            def run():
                try:value=work();self.events.put((complete,value,None))
                except Exception as error:self.events.put((complete,None,str(error)))
            Thread(target=run,daemon=True).start()
        def remember():
            self.ui_prefs['mumuAdb']=adb.get().strip()
            self.ui_prefs['mumuEndpoint']=endpoint.get().strip()
            self.persist_ui()
        def found_devices(values):
            selector.config(values=values)
            if serial.get() not in values:serial.set(values[0] if len(values)==1 else '')
            status.config(text=tr('mumu_devices',count=len(values)),fg=self.palette['text'])
            remember()
        def list_devices(connect=False):
            chosen_adb=adb.get().strip();chosen_endpoint=endpoint.get().strip()
            def work():
                if connect:installer.connect(chosen_adb,chosen_endpoint)
                return installer.devices(chosen_adb)
            worker_task(work,found_devices)
        def browse_adb():
            value=filedialog.askopenfilename(parent=window,title=tr('mumu_adb'),filetypes=[('ADB','*.exe')])
            if value:adb.set(value);remember()
        for title,action in [(tr('mumu_browse_adb'),browse_adb),(tr('mumu_refresh'),list_devices)]:
            button=self.button(row,title,action);button.pack(side='left',padx=(0,6));action_buttons.append(button)
        connect_button=self.button(row,tr('mumu_connect'),lambda:list_devices(True));connect_button.pack(side='left');action_buttons.append(connect_button)
        def install(local=False):
            chosen_adb=adb.get().strip();chosen_serial=serial.get().strip()
            if not chosen_serial:status.config(text=tr('mumu_select_instance'));return
            local_path=None
            if local:
                local_path=filedialog.askopenfilename(parent=window,title=tr('mumu_local'),filetypes=[('Android APK','*.apk')])
                if not local_path:return
            remember()
            def work():
                target=installer.local_serial(chosen_serial)
                if target not in installer.devices(chosen_adb):raise installer.InstallerError(tr('mumu_not_connected'))
                if local_path:
                    installer.validate_apk(local_path);path=local_path;checksum=None
                else:
                    item=installer.download_delta(accounts.ROOT/'mumu-apks',cancel,post)
                    path=item['path'];checksum=item['sha256']
                installer.check_cancel(cancel)
                post(tr('mumu_installing'))
                result=installer.install_apk(chosen_adb,target,path,cancel)
                return result+(tr('mumu_digest',digest=checksum) if checksum else '')
            worker_task(work,lambda value:(progress.config(value=100),status.config(text=value,fg=self.palette['success'])))
        for title,action in [(tr('mumu_auto'),lambda:install(False)),(tr('mumu_local'),lambda:install(True))]:
            button=self.button(buttons,title,action);button.pack(side='left',padx=(0,6));action_buttons.append(button)
        def open_site(url):
            Thread(target=lambda:webbrowser.open(url),daemon=True).start()
        links=tk.Frame(body);links.pack(fill='x',pady=4)
        self.button(links,tr('mumu_source'),lambda:open_site(installer.SOURCE_PAGE)).pack(side='left',padx=(0,6))
        self.button(links,tr('mumu_get_emulator'),lambda:open_site('https://www.mumuplayer.com/')).pack(side='left')
        def close():cancel.set();window.destroy()
        window.protocol('WM_DELETE_WINDOW',close)
        def discovered(values,error):
            if not alive():return
            if error:status.config(text=error);return
            adb_field.config(values=values)
            if not adb.get() and len(values)==1:adb.set(values[0])
            elif not adb.get():status.config(text=tr('mumu_adb_manual'))
        def find():
            try:self.events.put((discovered,installer.discover_adb(),None))
            except Exception as error:self.events.put((discovered,None,str(error)))
        Thread(target=find,daemon=True).start()
