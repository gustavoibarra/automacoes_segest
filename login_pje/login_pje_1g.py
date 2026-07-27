"""
login_pje_1g.py

Módulo reaproveitável de autenticação no PJE 1º grau (TRT12), equivalente à
cadeia de fluxos PLAUTO:
  - LOGIN_PJE1_PDPJ_PROD      (type: login)
  - LOGIN_PJE1_PDPJ_PROD_MFA  (type: mfa)

Sequência de navegação (função `login_pje_1g`):
   1. Abre https://pje.trt12.jus.br/primeirograu/
   2. Clica no botão de SSO (//button[@id="btnSsoPdpj"])
   3. Informa usuário e senha na tela do Keycloak
   4. Informa o código MFA (OTP)
   5. Navega para o painel: https://pje.trt12.jus.br/pjekz/gigs/meu-painel

Ao final, a `page` recebida fica autenticada e posicionada no painel
("meu-painel"), pronta para qualquer automação específica navegar dali em
diante (ex.: saopje/saopje_download_rel_proc_distribuidos.py).

Credenciais são passadas pelo chamador — nada de variável de ambiente ou
valor hardcoded aqui. O código OTP é pedido no terminal só depois que o
campo aparece na tela, para minimizar o risco de ele expirar antes de ser
usado.

Dependência:
    pip install playwright --break-system-packages
    playwright install chromium
"""

import os

from playwright.sync_api import Page, TimeoutError as PWTimeoutError

APP_ENTRY_URL = "https://pje.trt12.jus.br/primeirograu/"
DASHBOARD_URL = "https://pje.trt12.jus.br/pjekz/gigs/meu-painel"
SSO_BUTTON_SELECTOR = 'xpath=//button[@id="btnSsoPdpj"]'
LOGIN_ERROR_SELECTOR = ".kc-feedback-text"  # comando "error" do fluxo de login
USERNAME_SELECTOR = 'input[name="username"]'
PASSWORD_SELECTOR = 'input[name="password"]'
OTP_SELECTOR = 'input[id="otp"]'
SUBMIT_SELECTOR = 'input[type="submit"], button[type="submit"]'


class PjeLoginError(Exception):
    """Falha de autenticação (credenciais ou MFA) no PJE1G."""


class PjeNavigationError(Exception):
    """Falha ao navegar até uma tela do PJE1G após o login."""


def aguardar_app_estabilizar(page: Page) -> None:
    """
    Dá tempo para o app (Angular) terminar de renderizar/vincular os
    listeners de clique após uma navegação. Interagir cedo demais faz o
    clique "passar em branco": o elemento já existe no DOM e passa nas
    checagens de visibilidade do Playwright, mas o handler ainda não foi
    anexado pelo framework.
    """
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PWTimeoutError:
        pass  # app pode ter polling contínuo; segue com a espera fixa abaixo
    page.wait_for_timeout(1500)


def debug_screenshot(page: Page, label: str, debug_dir: str = "debug_screenshots", enabled: bool = True) -> None:
    """Salva um screenshot de depuração em `debug_dir`, se `enabled`."""
    if not enabled:
        return
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"{label}.png")
    page.screenshot(path=path)
    print(f"[debug] screenshot salvo em {path}")


def login_pje_1g(page: Page, username: str, password: str) -> None:
    """
    Executa a sequência completa de login + MFA. Ao final, `page` está
    autenticada no painel do PJE1G. Lança PjeLoginError se a etapa de
    credenciais ou o MFA falharem.
    """

    # --- 1-2: entrada na aplicação + botão de SSO ---
    page.goto(APP_ENTRY_URL)
    page.wait_for_selector(SSO_BUTTON_SELECTOR, timeout=20000)
    page.click(SSO_BUTTON_SELECTOR)

    # --- 3: LOGIN_PJE1_PDPJ_PROD (usuário e senha no Keycloak) ---
    page.wait_for_selector(USERNAME_SELECTOR, timeout=20000)
    page.fill(USERNAME_SELECTOR, username)
    page.fill(PASSWORD_SELECTOR, password)
    page.click(SUBMIT_SELECTOR)

    error_locator = page.locator(LOGIN_ERROR_SELECTOR)
    try:
        error_locator.wait_for(state="visible", timeout=3000)
        raise PjeLoginError(
            f"Falha no login: {error_locator.inner_text().strip() or 'erro não identificado'}"
        )
    except PWTimeoutError:
        pass  # nenhum erro exibido -> segue para o MFA

    # --- 4: LOGIN_PJE1_PDPJ_PROD_MFA (código do autenticador) ---
    page.wait_for_selector(OTP_SELECTOR, state="visible", timeout=20000)
    otp_code = input("Código do autenticador (OTP): ").strip()
    page.fill(OTP_SELECTOR, otp_code)
    page.click(SUBMIT_SELECTOR)
    page.wait_for_timeout(5000)

    # --- 5: navega para o painel ---
    page.goto(DASHBOARD_URL)
    try:
        page.wait_for_url(DASHBOARD_URL, timeout=15000)
    except PWTimeoutError:
        raise PjeLoginError(f"Não foi possível confirmar o painel. URL atual: {page.url}")
