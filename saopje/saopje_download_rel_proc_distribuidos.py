"""
saopje_download_rel_proc_distribuidos.py

Robô Playwright que baixa, dia a dia, o relatório de processos distribuídos
no primeiro grau (tela de execução SAO99-N991 do SAOADM/PJE), a partir do
painel autenticado (ver login_pje.login_pje_1g).

Sequência de navegação, a partir do painel:
   1. Clica no botão de menu (//*[@id="botao-menu"])
   2. Clica em "Pesquisar" no menu sobreposto
   3. Clica em "Relatórios Gerenciais" no menu sobreposto
   4. Navega para https://pje.trt12.jus.br/sao/execucao/SAO99-N991
   5. Para cada dia do período informado (ver "Parâmetros" abaixo),
      preenche os dois campos de data (localizados pelo rótulo "Data
      Início"/"Data Final", não por ID fixo) com a data daquele dia
   6. Clica no botão de pesquisa do acordeão
   7. Aguarda a mensagem de conclusão do processamento
   8. Clica no botão de ação final da seção
   9. Confirma o popup de diálogo que aparece, o que dispara o download
      do arquivo daquele dia

Parâmetros (linha de comando, formato DD/MM/AAAA):
    python -m saopje.saopje_download_rel_proc_distribuidos [dataInicial] [dataFinal]

    - Sem parâmetros: usa o período padrão, de DATA_INICIAL_PADRAO até
      ontem (a data de hoje costuma vir incompleta no relatório).
    - Só dataInicial informada: consulta de dataInicial até ontem.
    - As duas informadas: consulta o período entre as duas (inclusive).

    Para cada dia do período, os passos 5-9 são repetidos, gerando um
    arquivo "processos_{dia}{extensao}". Dias cujo arquivo já existe na
    pasta de destino (DOWNLOAD_DIR) são pulados, então rodar o script de
    novo sobre um período já processado só busca o que falta.

Dependência:
    pip install playwright --break-system-packages
    playwright install chromium
"""

import argparse
import glob
import os
import sys
import time
from datetime import date, datetime, timedelta
from getpass import getpass
from pathlib import Path

# Permite rodar tanto como módulo do pacote ("python -m saopje.saopje_..."
# — usado pelo main.py da raiz) quanto como script solto
# ("python saopje/saopje_download_rel_proc_distribuidos.py"), cenário em
# que o Python não coloca a raiz do projeto no sys.path por padrão.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import Page, TimeoutError as PWTimeoutError, sync_playwright

from login_pje.login_pje_1g import (
    PjeLoginError,
    PjeNavigationError,
    aguardar_app_estabilizar,
    debug_screenshot,
    login_pje_1g,
)

# --- Navegação pós-login: menu -> Relatórios Gerenciais -> tela de execução ---
MENU_BUTTON_SELECTOR = 'xpath=//*[@id="botao-menu"]'
MENU_PESQUISAR_SELECTOR = (
    'xpath=//*[@id="menu-item-1"]/pje-menu-sobreposto/div[2]/pje-item-menu-sobreposto'
    "/div[6]/div/div/div[2]"
)
MENU_RELATORIOS_GERENCIAIS_SELECTOR = (
    'xpath=//*[@id="menu-item-1"]/pje-menu-sobreposto/div[2]/pje-item-menu-sobreposto'
    "/div[16]/div/a/div[2]"
)
EXECUCAO_URL = "https://pje.trt12.jus.br/sao/execucao/SAO99-N991"

# --- Tela de execução: consulta por período ---
# Não usamos IDs fixos (ex.: "mat-input-2") porque o Angular Material
# gera esses IDs com um contador global que incrementa conforme outros
# campos (selects, autocompletes) são criados durante a navegação da SPA.
# O índice numérico muda de execução para execução e pode acabar
# apontando para o campo errado (ex.: "Classe Processual" em vez de
# "Data Início"), preenchendo o campo errado e deixando "Data Início"
# vazio -- o que faz o botão de pesquisa nunca habilitar. Em vez de um
# xpath estático (que também se mostrou frágil -- a hierarquia real do
# mat-form-field não bateu com a suposta), localizamos o campo em tempo
# de execução via JS: procura o rótulo visível cujo texto contém o termo
# e pega o <input> dentro do mesmo mat-form-field. Ver
# `_localizar_input_por_rotulo`.
DATA_INICIO_ROTULO = "Data Inicial"
DATA_FIM_ROTULO = "Data Final"
BOTAO_PESQUISAR_EXECUCAO_SELECTOR = 'xpath=//*[@id="cdk-accordion-child-1"]/div/div/div/button[1]'
BOTAO_ACAO_FINAL_SELECTOR = (
    'xpath=/html/body/pje-app-root/div/pje-app-execucao/div/div/section[3]/div/button[3]'
)
# "mat-dialog-0" também é um ID de contador global do Angular Material
# (mesmo problema do mat-input-N): a cada popup aberto na sessão o número
# incrementa, então funciona só na primeira consulta e quebra nas
# seguintes. Usamos starts-with para casar "mat-dialog-N" qualquer.
BOTAO_CONFIRMAR_POPUP_SELECTOR = (
    'xpath=//*[starts-with(@id, "mat-dialog-")]/pje-dialog/div/mat-dialog-actions/button'
)
MENSAGENS_CONCLUSAO = (
    "registro(s) encontrado(s)",
    "Esta consulta não retornou nenhum resultado",
)
# Tempo máximo de espera pela conclusão do processamento (passo 7) e
# intervalo entre checagens. Consultas com muitos processos podem demorar
# bastante -- o polling com print periódico evita que pareça travado.
PROCESSAMENTO_TIMEOUT_SEGUNDOS = 300
PROCESSAMENTO_POLL_SEGUNDOS = 5

# --- Depuração ---
DEBUG_SCREENSHOTS = True
DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_screenshots")

# --- Download do relatório final ---
# Pasta própria deste projeto. O projeto_equalizacao lê os CSVs daqui (ver
# projeto_equalizacao/config.py, Settings.downloads_dir).
DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")

# Nome final do arquivo salvo, um por dia consultado. Troque livremente --
# os únicos cuidados são manter `{extensao}` no final (preserva o tipo do
# arquivo baixado: xlsx, csv, pdf etc., o que o PJE mandar) e manter
# `{dia}` em algum lugar (usado também para checar se o dia já foi
# processado, ver `_arquivo_do_dia_existe`).
DOWNLOAD_NOME_ARQUIVO = "processos_{dia}{extensao}"
DOWNLOAD_DATA_FORMATO = "%d-%m-%Y"  # usado para formatar {dia} acima

# Período padrão quando nenhuma data é passada na linha de comando.
DATA_INICIAL_PADRAO = date(2026, 7, 1)


def _arquivo_do_dia_existe(dia: date) -> bool:
    """
    Verifica se já existe, em DOWNLOAD_DIR, um arquivo baixado para `dia`.
    Usa glob (não um caminho exato) porque a extensão só é conhecida
    depois do download (xlsx, csv, pdf etc.), então checamos por
    "processos_{dia}.*" independente da extensão.
    """
    dia_str = dia.strftime(DOWNLOAD_DATA_FORMATO)
    padrao = os.path.join(DOWNLOAD_DIR, f"processos_{dia_str}.*")
    return len(glob.glob(padrao)) > 0


def _parse_data_cli(valor: str) -> date:
    try:
        return datetime.strptime(valor, "%d/%m/%Y").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f'Data inválida: "{valor}". Use o formato DD/MM/AAAA.')


def _parse_argumentos(argv=None) -> tuple[date, date]:
    """
    Lê dataInicial/dataFinal da linha de comando (formato DD/MM/AAAA).
    Datas não informadas usam o padrão: início em DATA_INICIAL_PADRAO,
    fim em ontem (a data de hoje costuma vir incompleta no relatório).
    """
    parser = argparse.ArgumentParser(description="Consulta de execuções no PJE1G, por período.")
    parser.add_argument("data_inicial", nargs="?", type=_parse_data_cli, default=None)
    parser.add_argument("data_final", nargs="?", type=_parse_data_cli, default=None)
    args = parser.parse_args(argv)

    ontem = date.today() - timedelta(days=1)
    data_inicial = args.data_inicial if args.data_inicial is not None else DATA_INICIAL_PADRAO
    data_final = args.data_final if args.data_final is not None else ontem
    return data_inicial, data_final


def _intervalo_datas(inicio: date, fim: date):
    dia = inicio
    while dia <= fim:
        yield dia
        dia += timedelta(days=1)


def _localizar_input_por_rotulo(page: Page, rotulo_substr: str) -> str:
    """
    Encontra, em tempo de execução, o <input> associado ao rótulo visível
    que contém `rotulo_substr` (ex.: "Data Início") e devolve um seletor
    CSS ("#id") para ele.

    Faz isso via JS em vez de um xpath estático porque: (a) precisa
    ignorar rótulos/campos iguais que existam ocultos em outros painéis
    do acordeão (usa getBoundingClientRect para checar visibilidade real)
    e (b) usa closest('mat-form-field'), que não depende de acertar a
    profundidade exata da hierarquia de elementos do Angular Material.
    """
    input_id = page.evaluate(
        """(rotuloSubstr) => {
            const labels = Array.from(document.querySelectorAll('mat-label, label'));
            for (const lbl of labels) {
                const texto = (lbl.textContent || '').trim();
                if (!texto.includes(rotuloSubstr)) continue;
                const rect = lbl.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                const formField = lbl.closest('mat-form-field');
                if (!formField) continue;
                const input = formField.querySelector('input');
                if (input && input.id) return input.id;
            }
            return null;
        }""",
        rotulo_substr,
    )
    if not input_id:
        raise PjeNavigationError(
            f'Não foi possível localizar o campo com rótulo contendo "{rotulo_substr}".'
        )
    return f"#{input_id}"


def navegar_ate_execucao(page: Page) -> None:
    """
    A partir do painel autenticado, abre o menu principal, navega até
    "Pesquisar" > "Relatórios Gerenciais" e então vai para a tela de
    execução (EXECUCAO_URL).
    """
    aguardar_app_estabilizar(page)

    debug_screenshot(page, "00_antes_clique_menu", DEBUG_DIR, DEBUG_SCREENSHOTS)
    print(f"[debug] botao-menu encontrados: {page.locator(MENU_BUTTON_SELECTOR).count()}")

    # --- botão de menu ---
    page.click(MENU_BUTTON_SELECTOR)
    page.wait_for_timeout(500)
    debug_screenshot(page, "01_apos_clique_menu", DEBUG_DIR, DEBUG_SCREENSHOTS)

    # --- "Pesquisar" ---
    page.wait_for_selector(MENU_PESQUISAR_SELECTOR, state="visible", timeout=10000)
    page.click(MENU_PESQUISAR_SELECTOR)
    page.wait_for_timeout(500)
    debug_screenshot(page, "02_apos_clique_pesquisar", DEBUG_DIR, DEBUG_SCREENSHOTS)

    # --- "Relatórios Gerenciais" ---
    page.wait_for_selector(MENU_RELATORIOS_GERENCIAIS_SELECTOR, state="visible", timeout=10000)
    page.click(MENU_RELATORIOS_GERENCIAIS_SELECTOR)
    page.wait_for_timeout(500)
    debug_screenshot(page, "03_apos_clique_relatorios", DEBUG_DIR, DEBUG_SCREENSHOTS)

    # --- navega para a tela de execução ---
    page.goto(EXECUCAO_URL)
    try:
        page.wait_for_url(EXECUCAO_URL, timeout=15000)
    except PWTimeoutError:
        raise PjeNavigationError(f"Não foi possível confirmar a tela de execução. URL atual: {page.url}")


def executar_consulta_execucao(page: Page, dia: date) -> None:
    """
    Na tela de execução (EXECUCAO_URL): preenche o período com `dia` (mesma
    data nos dois campos), dispara a pesquisa, aguarda o processamento
    (pode demorar) e confirma a ação final via popup, o que dispara o
    download do arquivo daquele dia.
    """
    aguardar_app_estabilizar(page)

    data_str = dia.strftime("%d/%m/%Y")
    dia_str = dia.strftime(DOWNLOAD_DATA_FORMATO)

    # --- preenche as datas ---
    for label, rotulo in (("início", DATA_INICIO_ROTULO), ("fim", DATA_FIM_ROTULO)):
        selector = _localizar_input_por_rotulo(page, rotulo)
        print(f"[debug] campo de {label} localizado: {selector}")
        page.wait_for_selector(selector, state="visible", timeout=10000)
        campo = page.locator(selector)
        campo.click()
        campo.fill("")
        # Campos mat-input com máscara de data reagem melhor a digitação
        # tecla-a-tecla do que a um fill() direto.
        campo.press_sequentially(data_str, delay=50)
        print(f"[debug] data de {label} preenchida: {data_str}")

    debug_screenshot(page, f"04_datas_preenchidas_{dia_str}", DEBUG_DIR, DEBUG_SCREENSHOTS)

    # --- dispara a pesquisa ---
    botao_pesquisar = page.locator(BOTAO_PESQUISAR_EXECUCAO_SELECTOR)
    try:
        botao_pesquisar.wait_for(state="visible", timeout=10000)
        page.wait_for_function(
            """(sel) => {
                const el = document.evaluate(
                    sel, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
                ).singleNodeValue;
                return el && !el.disabled;
            }""",
            arg=BOTAO_PESQUISAR_EXECUCAO_SELECTOR.removeprefix("xpath="),
            timeout=10000,
        )
    except PWTimeoutError:
        debug_screenshot(page, f"04b_botao_pesquisar_desabilitado_{dia_str}", DEBUG_DIR, DEBUG_SCREENSHOTS)
        raise PjeNavigationError(
            f"Botão de pesquisa continua desabilitado após preencher as datas de {data_str} "
            "-- verifique se algum campo do formulário ficou inválido "
            f"(veja {DEBUG_DIR}/04b_botao_pesquisar_desabilitado_{dia_str}.png)."
        )
    botao_pesquisar.click()
    debug_screenshot(page, f"04c_apos_clique_pesquisar_{dia_str}", DEBUG_DIR, DEBUG_SCREENSHOTS)

    # --- aguarda a conclusão do processamento (pode demorar) ---
    # Polling manual (em vez de um único wait_for_function) para dar
    # feedback periódico no terminal -- sem isso, uma consulta legitimamente
    # lenta parece travada e é fácil confundir com um clique que falhou.
    print(f"[info] aguardando conclusão do processamento de {data_str}...")
    prazo = time.monotonic() + PROCESSAMENTO_TIMEOUT_SEGUNDOS
    concluido = False
    while time.monotonic() < prazo:
        concluido = page.evaluate(
            """(mensagens) => mensagens.some((m) => document.body.innerText.includes(m))""",
            list(MENSAGENS_CONCLUSAO),
        )
        if concluido:
            break
        page.wait_for_timeout(PROCESSAMENTO_POLL_SEGUNDOS * 1000)
        print(f"[debug] ainda processando {data_str}...")

    if not concluido:
        debug_screenshot(page, f"05b_processamento_nao_concluido_{dia_str}", DEBUG_DIR, DEBUG_SCREENSHOTS)
        raise PjeNavigationError(
            f"Processamento de {data_str} não concluiu em "
            f"{PROCESSAMENTO_TIMEOUT_SEGUNDOS}s "
            f"(veja {DEBUG_DIR}/05b_processamento_nao_concluido_{dia_str}.png)."
        )
    debug_screenshot(page, f"05_processamento_concluido_{dia_str}", DEBUG_DIR, DEBUG_SCREENSHOTS)

    # --- botão de ação final + confirmação do popup (dispara o download).
    # `expect_download` fica escutando o evento de download durante todo o
    # bloco `with`, então funciona independente de qual dos dois cliques
    # efetivamente inicia o download.
    with page.expect_download(timeout=60000) as download_info:
        page.click(BOTAO_ACAO_FINAL_SELECTOR)

        page.wait_for_selector(BOTAO_CONFIRMAR_POPUP_SELECTOR, state="visible", timeout=10000)
        page.click(BOTAO_CONFIRMAR_POPUP_SELECTOR)

    download = download_info.value
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    extensao = os.path.splitext(download.suggested_filename)[1] or ".xlsx"
    nome_arquivo = DOWNLOAD_NOME_ARQUIVO.format(dia=dia_str, extensao=extensao)
    destino = os.path.join(DOWNLOAD_DIR, nome_arquivo)
    download.save_as(destino)
    print(f"[debug] arquivo baixado salvo em {destino}")

    debug_screenshot(page, f"06_popup_confirmado_{dia_str}", DEBUG_DIR, DEBUG_SCREENSHOTS)


def main(argv=None) -> int:
    data_inicial, data_final = _parse_argumentos(argv)
    if data_inicial > data_final:
        print(
            f"[ERRO] Data inicial ({data_inicial:%d/%m/%Y}) é posterior "
            f"à data final ({data_final:%d/%m/%Y})."
        )
        return 1

    username = input("CPF (login): ").strip()
    password = getpass("Senha: ")

    with sync_playwright() as p:
        # headless=False por padrão: o PJE costuma reagir mal a navegação
        # totalmente headless (detecção anti-bot).
        browser = p.chromium.launch(headless=False)
        page = browser.new_context().new_page()

        try:
            login_pje_1g(page, username, password)
            print(f"Login efetuado com sucesso. URL atual: {page.url}")

            navegar_ate_execucao(page)
            print(f"Tela de execução aberta. URL atual: {page.url}")

            for dia in _intervalo_datas(data_inicial, data_final):
                if _arquivo_do_dia_existe(dia):
                    print(f"[info] {dia:%d/%m/%Y}: arquivo já existe em {DOWNLOAD_DIR}, pulando.")
                    continue
                print(f"[info] {dia:%d/%m/%Y}: consultando...")
                executar_consulta_execucao(page, dia)
                print(f"[info] {dia:%d/%m/%Y}: concluído.")
        except (PjeLoginError, PjeNavigationError, PWTimeoutError) as e:
            # Captura também PWTimeoutError (não só nossas exceções) para
            # garantir que browser.close() sempre rode antes de sair do
            # bloco `with sync_playwright()`; sem isso, um timeout durante
            # o loop escapava do except e a limpeza da conexão do
            # Playwright quebrava com "This event loop is already running".
            print(f"[ERRO] {e}")
            browser.close()
            return 1

        # Sessão fica aberta em `page` para o restante do robô continuar daqui.
        input("Pressione Enter para encerrar...")
        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
