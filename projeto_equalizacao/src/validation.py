"""Padronizacao de colunas, normalizacao de linhas, deduplicacao exata e
relatorio de qualidade dos dados.
"""
from __future__ import annotations

import re

import pandas as pd

from src import anomalies
from src.normalization import (
    normalize_indicador,
    normalize_processo_numero,
    normalize_text,
    normalize_unit_name,
)

COLUNAS_RENOMEIO = {
    "#Processo": "processo",
    "Indicador": "indicador",
    "Município Sede": "municipio_sede",
    "Municipio Sede": "municipio_sede",
    "Órgão Julgador": "orgao_julgador",
    "Orgao Julgador": "orgao_julgador",
    "Classe Judicial": "classe_judicial",
    "Data": "data",
}


def padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUNAS_RENOMEIO)
    return df


def normalizar_movimentos(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta colunas normalizadas usadas em comparacoes, deduplicacao e
    deteccao de anomalias. Preserva as colunas originais para exibicao."""
    df = df.copy()

    df["processo_original"] = df["processo"]
    df["processo"] = df["processo"].apply(normalize_processo_numero)
    df["processo_norm"] = df["processo"].apply(lambda v: normalize_text(v))

    df["indicador_original"] = df["indicador"]
    df["indicador_norm"] = df["indicador"].apply(normalize_indicador)

    df["orgao_julgador_original"] = df["orgao_julgador"]
    df["orgao_norm"] = df["orgao_julgador"].apply(normalize_unit_name)

    df["classe_judicial_original"] = df["classe_judicial"]
    df["classe_norm"] = df["classe_judicial"].apply(normalize_text)

    df["municipio_sede_original"] = df["municipio_sede"]
    df["municipio_norm"] = df["municipio_sede"].apply(normalize_text)

    df["data_dt"] = pd.to_datetime(df["data"], errors="coerce", dayfirst=True)
    df["data_valida"] = df["data_dt"].notna()

    return df


_PROCESSO_TEM_DIGITO_RE = re.compile(r"\d")


def detectar_anomalias_linha(df: pd.DataFrame, unidades_permanentes_norm: set[str],
                              palavra_triagem: str = "TRIAGEM") -> list[dict]:
    """Detecta anomalias no nivel da linha (movimentacao individual):
    processo sem numero, formato aparentemente invalido, data invalida,
    unidade vazia e unidade nao classificada."""
    registros = []
    for row in df.itertuples(index=False):
        processo = getattr(row, "processo")
        arquivo = getattr(row, "arquivo_origem")
        linha = getattr(row, "numero_linha_arquivo")

        if processo == "":
            registros.append(anomalies.novo(
                anomalies.PROCESSO_SEM_NUMERO, processo=processo,
                arquivo_origem=arquivo, numero_linha_arquivo=linha,
            ))
        elif not _PROCESSO_TEM_DIGITO_RE.search(processo) or len(processo) < 3:
            registros.append(anomalies.novo(
                anomalies.PROCESSO_FORMATO_INVALIDO, processo=processo,
                descricao=f"Processo com formato aparentemente invalido: '{processo}'",
                arquivo_origem=arquivo, numero_linha_arquivo=linha,
            ))

        if not getattr(row, "data_valida"):
            registros.append(anomalies.novo(
                anomalies.DATA_INVALIDA, processo=processo,
                arquivo_origem=arquivo, numero_linha_arquivo=linha,
            ))

        orgao_norm = getattr(row, "orgao_norm")
        if orgao_norm == "":
            registros.append(anomalies.novo(
                anomalies.UNIDADE_VAZIA, processo=processo,
                arquivo_origem=arquivo, numero_linha_arquivo=linha,
            ))
        elif palavra_triagem not in orgao_norm and orgao_norm not in unidades_permanentes_norm:
            registros.append(anomalies.novo(
                anomalies.UNIDADE_NAO_CLASSIFICADA, processo=processo,
                descricao=f"Unidade nao classificada: '{getattr(row, 'orgao_julgador_original')}'",
                arquivo_origem=arquivo, numero_linha_arquivo=linha,
            ))
    return registros


CHAVE_DEDUP = ["processo_norm", "indicador_norm", "orgao_norm", "data_dt", "classe_norm", "municipio_norm"]


def deduplicar_movimentos(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Remove apenas duplicidades exatas da mesma movimentacao (mesmo
    processo, indicador, orgao julgador, data, classe judicial e municipio
    sede, apos normalizacao). Mantem a primeira ocorrencia na ordem de
    arquivo/linha. Um mesmo numero de processo com atributos diferentes
    (outra linha, outro indicador etc.) NAO e removido."""
    df = df.sort_values(["ordem_arquivo", "numero_linha_arquivo"]).reset_index(drop=True)
    duplicado = df.duplicated(subset=CHAVE_DEDUP, keep="first")

    removidos = df[duplicado]
    anomalias_dup = [
        anomalies.novo(
            anomalies.MOVIMENTACAO_DUPLICADA_REMOVIDA,
            processo=row.processo,
            descricao=(
                f"Movimentacao duplicada removida (arquivo original preservado): "
                f"processo={row.processo}, indicador={row.indicador_norm}, "
                f"orgao={row.orgao_norm}"
            ),
            arquivo_origem=row.arquivo_origem,
            numero_linha_arquivo=row.numero_linha_arquivo,
        )
        for row in removidos.itertuples(index=False)
    ]

    df_dedup = df[~duplicado].reset_index(drop=True)
    return df_dedup, anomalias_dup


def relatorio_qualidade(df_bruto: pd.DataFrame, df_dedup: pd.DataFrame,
                         anomalias_df: pd.DataFrame, nao_classificadas_df: pd.DataFrame,
                         arquivos: list[str]) -> dict:
    """Consolida os indicadores exigidos do relatorio de qualidade."""
    registros_por_arquivo = (
        df_bruto.groupby("arquivo_origem").size().to_dict()
    )
    duplicidades = int((anomalias_df["tipo_anomalia"] == anomalies.MOVIMENTACAO_DUPLICADA_REMOVIDA).sum()) \
        if not anomalias_df.empty else 0
    registros_com_anomalia = int(anomalias_df["processo"].nunique()) if not anomalias_df.empty else 0

    completude = {}
    for coluna in ["processo", "indicador", "orgao_julgador", "classe_judicial", "municipio_sede", "data"]:
        if coluna in df_dedup.columns:
            preenchidos = df_dedup[coluna].astype(str).str.strip().replace({"nan": ""}).ne("").sum()
            completude[coluna] = round(100 * preenchidos / len(df_dedup), 2) if len(df_dedup) else 0.0

    datas_validas = df_dedup.loc[df_dedup["data_valida"], "data_dt"]

    return {
        "quantidade_registros_lidos": int(len(df_bruto)),
        "quantidade_arquivos": len(arquivos),
        "registros_por_arquivo": registros_por_arquivo,
        "duplicidades_removidas": duplicidades,
        "registros_validos": int(len(df_dedup)),
        "registros_com_anomalia": registros_com_anomalia,
        "processos_distintos": int(df_dedup["processo_norm"].nunique()),
        "unidades_nao_classificadas": int(nao_classificadas_df["unidade"].nunique()) if not nao_classificadas_df.empty else 0,
        "data_minima": datas_validas.min() if not datas_validas.empty else None,
        "data_maxima": datas_validas.max() if not datas_validas.empty else None,
        "percentual_completude_por_coluna": completude,
    }
