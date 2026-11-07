"""Manual login, User:Pass parser, isolated browser capture and native split button."""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock,patch

with tempfile.TemporaryDirectory() as folder:
    os.environ['LOCALAPPDATA']=folder
    root_path=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root_path))
    import browser_login as login
    assert login.parse_credentials('first_one:secret:with:colons\nsecond_two:other')==[
        ('first_one','secret:with:colons'),('second_two','other')]
    for text in ('','bad format','first_one:','first_one:a\nFIRST_ONE:b'):
        try:login.parse_credentials(text);raise AssertionError('Invalid credentials accepted')
        except ValueError:pass
    def run(credentials,fallback=False,url=login.LOGIN):
        cancel=threading.Event();reports=[]
        locator=SimpleNamespace(fill=AsyncMock(),click=AsyncMock())
        page=SimpleNamespace(url=url,goto=AsyncMock(),evaluate=AsyncMock(return_value="fixture-browser-user-agent"),locator=Mock(return_value=locator),is_closed=lambda:False)
        context=SimpleNamespace(new_page=AsyncMock(return_value=page),cookies=AsyncMock(return_value=[
            {'name':'.ROBLOSECURITY','domain':'.roblox.com','secure':True,'value':'fixture-cookie-not-real'}]))
        browser=SimpleNamespace(new_context=AsyncMock(return_value=context),is_connected=lambda:True,close=AsyncMock())
        launch=AsyncMock(side_effect=[OSError('chrome unavailable'),browser] if fallback else None,
                         return_value=browser)
        driver=SimpleNamespace(chromium=SimpleNamespace(launch=launch))
        class Playwright:
            async def __aenter__(self):return driver
            async def __aexit__(self,*args):pass
        module=SimpleNamespace(async_playwright=lambda:Playwright())
        with patch.dict(sys.modules,{'playwright.async_api':module}),patch.object(login.accounts,'save_session') as save:
            asyncio.run(login.import_batch(credentials,cancel,lambda *args:reports.append(args)))
            saved=save.call_args_list
        return locator,launch,saved,reports,browser
    locator,launch,saved,reports,browser=run([(None,None)])
    locator.fill.assert_not_called()
    assert saved[0].kwargs['expected_username'] is None
    assert saved[0].kwargs['ua']=='fixture-browser-user-agent'
    browser.close.assert_awaited_once()
    locator,launch,saved,reports,browser=run([('first_one','fixture-password')],fallback=True)
    assert [c.kwargs['channel'] for c in launch.call_args_list]==['chrome','msedge']
    assert saved[0].kwargs['expected_username']=='first_one'
    assert locator.fill.await_count==2
    _,_,saved,_,_=run([(None,None)],url='https://example.invalid/login')
    assert not saved,'Only official Roblox login may provide a session'
    if os.name=='nt':
        import tkinter as tk
        from desktop import Desktop
        real_manual,real_password,real_cookies=Desktop.manual_dialog,Desktop.password_dialog,Desktop.import_dialog
        window=tk.Tk()
        window.withdraw()
        try:
            with patch.object(Desktop,'refresh'),patch.object(Desktop,'check_startup_update'),patch.object(Desktop,'manual_dialog') as manual,patch.object(Desktop,'password_dialog') as password,patch.object(Desktop,'import_dialog') as cookies:
                ui=Desktop(window,49327,'fixture',root_path,{})
                window.deiconify();window.update()
                assert [ui.add_menu.entrycget(i,'label') for i in range(3)]==['Login manual','Nick e senha (User:Pass)','Cookies']
                assert str(ui.add_menu).startswith(str(ui.add_arrow)+'.')
                ui.add_button.invoke()
                ui.add_menu.invoke(0);ui.add_menu.invoke(1);ui.add_menu.invoke(2)
                assert manual.call_count==2 and password.call_count==1 and cookies.call_count==1
                ui.add_arrow.event_generate('<ButtonPress-1>',x=5,y=5)
                window.update()
                ui.add_menu.unpost()
                ui.add_menu.grab_release()
                assert window.winfo_width()==784 and window.winfo_height()==380,(window.winfo_width(),window.winfo_height(),window.winfo_fpixels('1i'))
                real_cookies(ui)
                real_password(ui)
                titles=[child.title() for child in window.winfo_children() if isinstance(child,tk.Toplevel)]
                assert 'Importar sessões' in titles and 'Adicionar por nick e senha' in titles
                password_window=next(child for child in window.winfo_children() if isinstance(child,tk.Toplevel) and child.title()=='Adicionar por nick e senha')
                def children(widget):
                    result=[]
                    for child in widget.winfo_children():
                        result.append(child)
                        result.extend(children(child))
                    return result
                widgets=children(password_window)
                text_fields=[widget for widget in widgets if isinstance(widget,tk.Text)]
                assert len(text_fields)==1 and not any(isinstance(widget,tk.Entry) for widget in widgets)
                pasted=text_fields[0]
                pasted.insert('1.0','first_one:fixture:colon\nsecond_two:fixture-two')
                start=next(widget for widget in widgets if isinstance(widget,tk.Button) and widget.cget('text')=='Entrar e adicionar contas')
                with patch.object(login,'import_batch',new=AsyncMock(return_value=None)) as imported:
                    start.invoke()
                    deadline=time.monotonic()+3
                    while ui.pending and time.monotonic()<deadline:
                        window.update()
                        time.sleep(.02)
                    assert not ui.pending
                    assert imported.await_args.args[0]==[('first_one','fixture:colon'),('second_two','fixture-two')]
                    assert pasted.get('1.0','end-1c')==''
                with patch.object(login,'import_batch',new=AsyncMock(return_value=None)):
                    real_manual(ui)
                    deadline=time.monotonic()+3
                    while ui.pending and time.monotonic()<deadline:
                        window.update()
                        time.sleep(.02)
                    assert not ui.pending
                assert any(isinstance(child,tk.Toplevel) and child.title()=='Adicionar conta — Login manual' for child in window.winfo_children())
        finally:window.destroy()
    print('PASS manual login without credential filling, Chrome/Edge fallback, User:Pass parser, account identity check, official-domain guard and Windows add-account split button')
