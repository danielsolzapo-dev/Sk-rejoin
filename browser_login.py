"""Import sessions from separate Chrome windows on the official Roblox login page."""
import asyncio
from time import monotonic
from urllib.parse import urlsplit

import accounts

LOGIN = "https://www.roblox.com/login"


def parse_credentials(text):
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError("Use uma conta por linha no formato nick:senha.")
        nick, password = line.split(":", 1)
        nick = nick.strip()
        if not accounts.USERNAME.fullmatch(nick) or not password:
            raise ValueError("Cada linha precisa de nick válido e senha.")
        rows.append((nick, password))
    if not 1 <= len(rows) <= 6:
        raise ValueError("Cole de 1 a 6 contas por lote.")
    if len({nick.casefold() for nick, _ in rows}) != len(rows):
        raise ValueError("Cada nick deve aparecer uma vez.")
    return rows


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
            label = nick or "Login manual"
            browser = None
            try:
                report(label, "Abrindo navegador…")
                for channel in ("chrome", "msedge"):
                    try:
                        browser = await driver.chromium.launch(channel=channel, headless=False)
                        break
                    except Exception:
                        if cancel.is_set():
                            return
                if browser is None:
                    raise ValueError("Instale Chrome ou Edge para adicionar a conta.")
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(LOGIN, wait_until="domcontentloaded", timeout=25000)
                if cancel.is_set():
                    return
                address = urlsplit(page.url)
                if address.scheme != "https" or address.hostname not in {"www.roblox.com", "roblox.com"}:
                    report(label, "O navegador saiu do site oficial. Login interrompido.")
                    return
                if nick is not None:
                    try:
                        await page.locator("#login-username").fill(nick, timeout=5000)
                        await page.locator("#login-password").fill(password, timeout=5000)
                        if cancel.is_set():
                            return
                        await page.locator("#login-button").click(timeout=5000)
                    except Exception:
                        report(label, "Conclua o login na janela do navegador.")
                    else:
                        report(label, "Aguardando login. Conclua a verificação no navegador se solicitada.")
    
                else:
                    report(label, "Entre na sua conta e conclua a verificação na janela do navegador.")
                try:
                    user_agent = await page.evaluate("navigator.userAgent")
                except Exception:
                    user_agent = ""
                deadline = monotonic() + (300 if nick is None else 180)
                while not cancel.is_set() and monotonic() < deadline and browser.is_connected() and not page.is_closed():
                    cookies = await context.cookies(LOGIN)
                    for cookie in cookies:
                        if cookie["name"] == ".ROBLOSECURITY" and cookie["domain"].lstrip(".") in {"roblox.com", "www.roblox.com"} and cookie["secure"]:
                            try:
                                await asyncio.to_thread(accounts.save_session, cookie["value"], ua=user_agent, expected_username=nick)
                            except ValueError as error:
                                report(label, str(error))
                            else:
                                report(label, "Conta adicionada.")
                            return
                    await asyncio.sleep(1)
                report(label, "Importação cancelada." if cancel.is_set() else "Login não confirmado.")
            except Exception:
                report(label, "Não foi possível concluir o login. Confira Chrome ou Edge e tente novamente.")
            finally:
                if browser and browser.is_connected():
                    await browser.close()

    async with async_playwright() as driver:
        await asyncio.gather(*(login(driver, nick, password) for nick, password in credentials))

