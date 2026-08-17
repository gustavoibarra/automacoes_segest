"""Carrega o arquivo consolidado (gerado por projeto_equalizacao) e prepara
os dois universos de processos usados no resumo executivo:

- casos_novos_periodo: processos cuja data_caso_novo cai dentro do periodo
  analisado -- usado para os indicadores "casos novos" / "processos
  equalizados";
- processos_movimentados_periodo: processos com QUALQUER movimentacao
  (exceto RESTITUIDO) dentro do periodo -- usado nas tabelas comparativas
  por unidade (inclui processos cuja distribuicao inicial e anterior ao
  periodo, mas que tiveram uma redistribuicao dentro dele).

Os dois universos podem divergir; essa diferenca e intencional e explicada
no proprio relatorio (secao "Resultado geral do periodo").
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

INDICADOR_RESTITUIDO = "RESTITUIDO"


class DadosError(Exception):
    """Erro de estrutura do arquivo consolidado que deve interromper o
    processamento com uma mensagem objetiva para o usuario."""


def carregar_consolidado(caminho: Path) -> dict[str, pd.DataFrame]:
    caminho = Path(caminho)
    if not caminho.exists():
        raise DadosError(
            f"Arquivo consolidado nao encontrado: {caminho}. Gere-o primeiro em projeto_equalizacao "
            "com 'python main.py' (ele fica em output/consolidado_equalizacao.xlsx), ou informe outro "
            "caminho com --arquivo."
        )

    try:
        planilhas = pd.read_excel(caminho, sheet_name=["Processos", "Movimentacoes", "Comparativo_Unidades"])
    except ValueError as erro:
        raise DadosError(
            f"O arquivo {caminho.name} nao contem as abas esperadas 'Processos', 'Movimentacoes' e "
            f"'Comparativo_Unidades' (formato do consolidado_equalizacao.xlsx). Detalhe: {erro}"
        )

    processos_df = planilhas["Processos"]
    movimentacoes_df = planilhas["Movimentacoes"]
    comparativo_df = planilhas["Comparativo_Unidades"]

    for coluna in ("data_caso_novo", "data_ultimo_movimento"):
        if coluna not in processos_df.columns:
            raise DadosError(f"A aba 'Processos' nao contem a coluna '{coluna}' esperada.")
        processos_df[coluna] = pd.to_datetime(processos_df[coluna], errors="coerce")

    if "data_dt" not in movimentacoes_df.columns:
        raise DadosError("A aba 'Movimentacoes' nao contem a coluna 'data_dt' esperada.")
    movimentacoes_df["data_dt"] = pd.to_datetime(movimentacoes_df["data_dt"], errors="coerce")

    return {
        "processos": processos_df,
        "movimentacoes": movimentacoes_df,
        "comparativo": comparativo_df,
    }


def unidades_mestre(comparativo_df: pd.DataFrame) -> pd.DataFrame:
    """Extrai a lista unica de unidades permanentes (nome, classificacao,
    quantidade de magistrados) a partir da aba Comparativo_Unidades -- essas
    informacoes sao estaticas e identicas nos dois cenarios (COM/SEM
    equalizacao), entao um dos dois basta."""
    colunas = ["unidade_norm", "unidade_original", "classificacao", "quantidade_magistrados"]
    faltantes = [c for c in colunas if c not in comparativo_df.columns]
    if faltantes:
        raise DadosError(
            f"A aba 'Comparativo_Unidades' nao contem as colunas esperadas {faltantes}. "
            "Regenere o consolidado_equalizacao.xlsx com uma versao atual do projeto_equalizacao."
        )
    return (
        comparativo_df[colunas]
        .drop_duplicates(subset=["unidade_norm"])
        .reset_index(drop=True)
    )


def resolver_periodo(processos_df: pd.DataFrame, inicio: pd.Timestamp | None = None,
                      fim: pd.Timestamp | None = None) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Resolve o periodo do relatorio. Quando inicio/fim nao sao informados,
    usa o intervalo integral disponivel na base: da primeira data_caso_novo
    ate a ultima data_ultimo_movimento."""
    if inicio is None:
        datas_iniciais = processos_df["data_caso_novo"].dropna()
        inicio = datas_iniciais.min() if not datas_iniciais.empty else pd.Timestamp.today().normalize()
    if fim is None:
        datas_finais = processos_df["data_ultimo_movimento"].dropna()
        fim = datas_finais.max() if not datas_finais.empty else inicio
    inicio = pd.Timestamp(inicio).normalize()
    fim = pd.Timestamp(fim).normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
    return inicio, fim


def casos_novos_periodo(processos_df: pd.DataFrame, inicio: pd.Timestamp, fim: pd.Timestamp) -> pd.DataFrame:
    """Processos cuja data_caso_novo cai dentro do periodo."""
    mascara = processos_df["data_caso_novo"].notna() & \
        (processos_df["data_caso_novo"] >= inicio) & (processos_df["data_caso_novo"] <= fim)
    return processos_df[mascara].reset_index(drop=True)


def processos_movimentados_periodo(processos_df: pd.DataFrame, movimentacoes_df: pd.DataFrame,
                                    inicio: pd.Timestamp, fim: pd.Timestamp) -> pd.DataFrame:
    """Processos com qualquer movimentacao (exceto RESTITUIDO) dentro do
    periodo -- universo usado nas tabelas comparativas por unidade."""
    relevante = movimentacoes_df
    if "indicador_norm" in movimentacoes_df.columns:
        relevante = relevante[relevante["indicador_norm"] != INDICADOR_RESTITUIDO]
    mascara = relevante["data_dt"].notna() & (relevante["data_dt"] >= inicio) & (relevante["data_dt"] <= fim)
    processos_com_movimento = set(relevante.loc[mascara, "processo_norm"])
    return processos_df[processos_df["processo_norm"].isin(processos_com_movimento)].reset_index(drop=True)
