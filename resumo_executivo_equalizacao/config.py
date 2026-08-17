"""Configuracoes centrais do gerador de Resumo Executivo do Sistema de
Equalizacao TRT12. Projeto autocontido: nao importa nada de
projeto_equalizacao/ -- apenas le o arquivo consolidado que aquele projeto
produz.
"""
from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Caminho padrao do consolidado gerado por projeto_equalizacao (pasta irma).
CONSOLIDADO_PADRAO = BASE_DIR.parent / "projeto_equalizacao" / "output" / "consolidado_equalizacao.xlsx"

OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo_trt12.png"

ABAS_NECESSARIAS = ("Processos", "Movimentacoes", "Comparativo_Unidades")

# ---------------------------------------------------------------------------
# Identidade visual (extraida do documento de referencia)
# ---------------------------------------------------------------------------

FONTE_PADRAO = "Arial"

COR_TITULO = "1E3F66"          # azul-marinho: titulo, secoes, nota
COR_SUBTITULO = "6B7280"       # cinza: subtitulo da capa
COR_PERIODO = "2F8492"         # verde-azulado: linha "periodo analisado"
COR_TABELA_CABECALHO = "285B87"  # azul escuro: cabecalho de tabelas de dados
COR_BORDA_TABELA = "1F497D"    # azul-marinho: bordas finas de todas as tabelas
COR_NOTA_FUNDO = "F3F6F8"      # cinza muito claro: caixas de nota
COR_KPI_VOLUME = "4F81BD"      # azul: cards de volume (casos novos, equalizados, %)
COR_KPI_REDUCAO = "45818E"     # teal: cards de reducao de CV
COR_RODAPE_TEXTO = "1F2937"

COR_GRAFICO_SEM_EQ = "9CB3C9"  # cinza-azulado claro: cenario sem equalizacao
COR_GRAFICO_COM_EQ = "285B87"  # azul da marca: cenario com equalizacao

# Faixas de classificacao do coeficiente de variacao (secao 1 do relatorio).
FAIXAS_CV = (
    (0, 10, "Distribuição bastante homogênea", "#d9ead3"),
    (10, 20, "Dispersão relativamente baixa", "#d0e0e3"),
    (20, 30, "Dispersão relevante", "#fff2cc"),
    (30, 40, "Dispersão elevada", "#fce5cd"),
    (40, float("inf"), "Dispersão muito elevada", "#f4cccc"),
)

# Tamanho de pagina Carta/Letter, em cm (igual ao documento de referencia).
PAGINA_LARGURA_CM = 21.59
PAGINA_ALTURA_CM = 27.94

TITULO_RELATORIO = "Relatorio Executivo do Sistema de Equalizacao"
SUBTITULO_RELATORIO = "Quantidade de processos e carga de trabalho por magistrado | Publico externo"
