"""Import sessions from separate Chrome windows on the official Roblox login page."""
import asyncio
from time import monotonic
from urllib.parse import urlsplit

import accounts

LOGIN = "https://www.roblox.com/login"


async def import_batch(credentials, cancel, report):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise ValueError("Execute Instalar-bandeja.bat para instalar também o login pelo Chrome.") from None

    slots = asyncio.Semaphore(3)

    async def login(driver, nick, password):
        async with slots:
            if cancel.is_set():
                return
            browser = None
            try:
                report(nick, "Abrindo Chrome…")
                browser = await driver.chromium.launch(channel="chrome", headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(LOGIN, wait_until="domcontentloaded", timeout=25000)
                if cancel.is_set():
                    return
                address = urlsplit(page.url)
                if address.scheme != "https" or address.hostname not in {"www.roblox.com", "roblox.com"}:
                    report(nick, "O Chrome saiu do site oficial. Login interrompido.")
                    return
                try:
                    await page.locator("#login-username").fill(nick, timeout=5000)
                    await page.locator("#login-password").fill(password, timeout=5000)
                    if cancel.is_set():
                        return
                    await page.locator("#login-button").click(timeout=5000)
                except Exception:
                    report(nick, "Conclua o login na janela do Chrome.")
                else:
                    report(nick, "Aguardando login. Conclua a verificação no Chrome se solicitada.")
                deadline = monotonic() + 180
                while not cancel.is_set() and monotonic() < deadline and browser.is_connected() and not page.is_closed():
                    cookies = await context.cookies(LOGIN)
                    for cookie in cookies:
                        if cookie["name"] == ".ROBLOSECURITY" and cookie["domain"].lstrip(".") in {"roblox.com", "www.roblox.com"} and cookie["secure"]:
                            try:
                                await asyncio.to_thread(accounts.save_session, cookie["value"], expected_username=nick)
                            except ValueError as error:
                                report(nick, str(error))
                            else:
                                report(nick, "Conta adicionada.")
                            return
                    await asyncio.sleep(1)
                report(nick, "Importação cancelada." if cancel.is_set() else "Login não confirmado.")
            except Exception:
                report(nick, "Não foi possível concluir no Chrome. Confira se ele está instalado e tente novamente.")
            finally:
                if browser and browser.is_connected():
                    await browser.close()

    async with async_playwright() as driver:
        await asyncio.gather(*(login(driver, nick, password) for nick, password in credentials))
