"""Compara a base consolidada do Sistema de Equalizacao com uma relacao de
processos do log do sistema (arquivo externo), para identificar:

- processos do log que nao aparecem em lugar nenhum da base consolidada;
- processos que aparecem na base mas nao foram equalizados validamente,
  com o motivo (situacao calculada + anomalias associadas).

Usado pelo script de linha de comando comparar_processos.py.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.filters import situacao_processo
from src.normalization import normalize_processo_numero, normalize_text

COLUNAS_LOG_ESPERADAS = (
    "Processo",
    "Unidade de Origem",
    "Situação",
    "Fase",
    "Observação",
    "Ocorrências Triagem",
    "Erros Triagem",
    "Ocorrências Territorial",
    "Erros Territorial",
)

SITUACAO_PROCESSO_NAO_ENCONTRADO = "NAO_ENCONTRADO_NA_BASE"


class ComparacaoError(Exception):
    """Erro de estrutura de arquivo que deve interromper o processamento
    com uma mensagem objetiva para o usuario."""


def _processo_norm(valor) -> str:
    return normalize_text(normalize_processo_numero(valor))


def _encontrar_coluna(colunas_originais: list[str], nome_esperado: str) -> str | None:
    alvo = normalize_text(nome_esperado)
    for coluna in colunas_originais:
        if normalize_text(coluna) == alvo:
            return coluna
    return None


def carregar_consolidado(caminho: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Le as abas 'Processos' e 'Anomalias' do consolidado_equalizacao.xlsx
    gerado pelo main.py/app.py."""
    if not caminho.exists():
        raise ComparacaoError(
            f"Arquivo consolidado nao encontrado: {caminho}. Gere-o primeiro com "
            "'python main.py' (ele fica em output/consolidado_equalizacao.xlsx)."
        )
    try:
        planilhas = pd.read_excel(caminho, sheet_name=["Processos", "Anomalias"])
    except ValueError as erro:
        raise ComparacaoError(
            f"O arquivo {caminho.name} nao contem as abas 'Processos' e 'Anomalias' esperadas "
            f"do consolidado_equalizacao.xlsx. Detalhe: {erro}"
        )
    processos_df = planilhas["Processos"]
    anomalias_df = planilhas["Anomalias"]

    if "processo_norm" not in processos_df.columns or "processo" not in processos_df.columns:
        raise ComparacaoError(
            f"A aba 'Processos' de {caminho.name} nao contem as colunas esperadas 'processo' e "
            f"'processo_norm'. Colunas encontradas: {list(processos_df.columns)}"
        )

    anomalias_df = anomalias_df.copy()
    anomalias_df["processo_norm"] = anomalias_df["processo"].apply(_processo_norm)
    return processos_df, anomalias_df


def carregar_log_processos(caminho: Path) -> pd.DataFrame:
    """Le o arquivo XLS/XLSX com a relacao de processos do log do sistema
    de equalizacao, tolerando pequenas variacoes no nome das colunas
    (mesma normalizacao usada no restante do sistema)."""
    if not caminho.exists():
        raise ComparacaoError(f"Arquivo de log de processos nao encontrado: {caminho}.")

    bruto = pd.read_excel(caminho, dtype=str)
    bruto.columns = [str(c).strip() for c in bruto.columns]
    colunas_originais = list(bruto.columns)

    renomeio = {}
    faltantes = []
    for esperada in COLUNAS_LOG_ESPERADAS:
        encontrada = _encontrar_coluna(colunas_originais, esperada)
        if encontrada is None:
            faltantes.append(esperada)
        elif encontrada != esperada:
            renomeio[encontrada] = esperada

    if faltantes:
        raise ComparacaoError(
            f"O arquivo de log {caminho.name} nao contem as colunas esperadas {faltantes}. "
            f"Colunas encontradas: {colunas_originais}"
        )

    df = bruto.rename(columns=renomeio)
    df["processo_norm"] = df["Processo"].apply(_processo_norm)

    vazios = df["processo_norm"] == ""
    if vazios.any():
        df = df[~vazios].reset_index(drop=True)

    return df


_COLUNAS_PROCESSO_PARA_JUNTAR = [
    "processo_norm", "processo", "data_caso_novo", "unidade_distribuicao_inicial_original",
    "unidade_final_real_original", "data_ultimo_movimento", "classe_judicial",
    "quantidade_movimentos", "quantidade_redistribuicoes", "passou_por_triagem",
    "equalizacao_detectada", "equalizacao_valida", "quantidade_episodios_triagem",
    "unidade_cedente_equalizacao_original", "unidade_destinataria_equalizacao_original",
    "motivo_invalidade_equalizacao", "unidade_simulada_sem_equalizacao_original", "tem_anomalia",
]

_RENOMEIO_PROCESSO = {
    "processo": "processo_na_base",
    "unidade_distribuicao_inicial_original": "unidade_distribuicao_inicial",
    "unidade_final_real_original": "unidade_final_real",
    "unidade_cedente_equalizacao_original": "unidade_cedente_equalizacao",
    "unidade_destinataria_equalizacao_original": "unidade_destinataria_equalizacao",
    "unidade_simulada_sem_equalizacao_original": "unidade_simulada_sem_equalizacao",
}


def _situacao_calculada(row) -> str:
    if not row.get("_encontrado", False):
        return SITUACAO_PROCESSO_NAO_ENCONTRADO
    return situacao_processo(row)


def comparar(processos_df: pd.DataFrame, anomalias_df: pd.DataFrame, log_df: pd.DataFrame) -> dict:
    """Compara os processos do log com a base consolidada.

    Retorna um dict com:
      - tabela_completa: uma linha por processo do log, com as colunas
        originais do log + os campos calculados da base;
      - nao_encontrados: subconjunto sem correspondencia na base;
      - encontrados_nao_equalizados: subconjunto presente na base mas com
        equalizacao_valida = falso;
      - encontrados_equalizados: subconjunto presente na base e com
        equalizacao_valida = verdadeiro;
      - resumo: contadores.
    """
    colunas_disponiveis = [c for c in _COLUNAS_PROCESSO_PARA_JUNTAR if c in processos_df.columns]
    base = processos_df[colunas_disponiveis].rename(columns=_RENOMEIO_PROCESSO)

    tabela = log_df.merge(base, on="processo_norm", how="left", indicator=True)
    tabela["_encontrado"] = tabela["_merge"] == "both"
    tabela = tabela.drop(columns=["_merge"])

    if not anomalias_df.empty:
        anomalias_agrupadas = (
            anomalias_df.groupby("processo_norm")["tipo_anomalia"]
            .apply(lambda serie: "; ".join(sorted(set(serie))))
            .rename("anomalias_encontradas")
        )
        tabela = tabela.merge(anomalias_agrupadas, on="processo_norm", how="left")
    else:
        tabela["anomalias_encontradas"] = pd.NA
    tabela["anomalias_encontradas"] = tabela["anomalias_encontradas"].fillna("")

    tabela["situacao_calculada"] = tabela.apply(_situacao_calculada, axis=1)
    tabela = tabela.drop(columns=["_encontrado"])

    nao_encontrados = tabela[tabela["situacao_calculada"] == SITUACAO_PROCESSO_NAO_ENCONTRADO].reset_index(drop=True)
    encontrados = tabela[tabela["situacao_calculada"] != SITUACAO_PROCESSO_NAO_ENCONTRADO]
    encontrados_equalizados = encontrados[encontrados["equalizacao_valida"] == True].reset_index(drop=True)  # noqa: E712
    encontrados_nao_equalizados = encontrados[encontrados["equalizacao_valida"] != True].reset_index(drop=True)  # noqa: E712

    resumo = pd.DataFrame([
        {"indicador": "Processos no arquivo de log", "valor": int(len(log_df))},
        {"indicador": "Nao encontrados na base consolidada", "valor": int(len(nao_encontrados))},
        {"indicador": "Encontrados na base, mas nao equalizados validamente", "valor": int(len(encontrados_nao_equalizados))},
        {"indicador": "Encontrados na base e equalizados validamente", "valor": int(len(encontrados_equalizados))},
    ])

    return {
        "tabela_completa": tabela.reset_index(drop=True),
        "nao_encontrados": nao_encontrados,
        "encontrados_nao_equalizados": encontrados_nao_equalizados,
        "encontrados_equalizados": encontrados_equalizados,
        "resumo": resumo,
    }
