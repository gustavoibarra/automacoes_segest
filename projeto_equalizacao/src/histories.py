"""Reconstrucao do historico cronologico de cada processo e derivacao dos
campos de resumo por processo (secao 7 do prompt).

Importante: esta etapa reconstroi o historico INTEIRO de cada processo,
sem aplicar nenhum filtro de periodo. O filtro de periodo e aplicado
somente depois, em src/filters.py, sobre a tabela ja reconstruida.
"""
from __future__ import annotations

import pandas as pd

from src import anomalies
from src.normalization import (
    INDICADOR_DISTRIBUICAO,
    INDICADOR_REDISTRIBUICAO,
    INDICADOR_RESTITUIDO,
    is_unidade_triagem,
)

COLUNAS_RESUMO_PROCESSOS = [
    "processo", "processo_norm", "data_caso_novo", "unidade_distribuicao_inicial",
    "unidade_distribuicao_inicial_original", "unidade_final_real", "unidade_final_real_original",
    "data_ultimo_movimento", "classe_judicial", "quantidade_movimentos", "quantidade_redistribuicoes",
    "passou_por_triagem", "municipio_sede", "municipio_sede_original", "arquivo_origem_ref",
    "numero_linha_arquivo_ref",
]


def reconstruir_historico(df_dedup: pd.DataFrame, palavra_triagem: str = "TRIAGEM"
                           ) -> tuple[pd.DataFrame, list[dict]]:
    """Ordena as movimentacoes de cada processo cronologicamente e retorna
    a tabela de historico com a coluna 'sequencia_movimento', alem da lista
    de anomalias de ordem cronologica ambigua.

    Criterio de ordenacao: data (coluna Data) -> data extraida do arquivo
    -> ordem do arquivo -> numero da linha no arquivo.
    """
    df = df_dedup.copy()
    df["unidade_e_triagem"] = df["orgao_norm"].apply(lambda v: is_unidade_triagem(v, palavra_triagem))

    data_ordenacao = df["data_dt"].fillna(pd.Timestamp.max)
    df["_data_ordenacao"] = data_ordenacao
    df = df.sort_values(
        by=["processo_norm", "_data_ordenacao", "data_arquivo", "ordem_arquivo", "numero_linha_arquivo"]
    ).reset_index(drop=True)

    df["sequencia_movimento"] = df.groupby("processo_norm").cumcount() + 1

    anomalias_ordem: list[dict] = []
    relevante_para_ambiguidade = df["data_valida"] & (df["indicador_norm"] != INDICADOR_RESTITUIDO)
    for processo_norm, grupo in df[relevante_para_ambiguidade].groupby("processo_norm"):
        datas = grupo["data_dt"].tolist()
        empatadas = False
        for i in range(len(datas) - 1):
            if datas[i] == datas[i + 1]:
                empatadas = True
                break
        if empatadas:
            primeira_linha = grupo.iloc[0]
            anomalias_ordem.append(anomalies.novo(
                anomalies.ORDEM_CRONOLOGICA_AMBIGUA,
                processo=primeira_linha["processo"],
                descricao=(
                    f"Processo {primeira_linha['processo']} possui movimentos com data identica; "
                    "ordem definida por arquivo/linha."
                ),
                arquivo_origem=primeira_linha["arquivo_origem"],
                numero_linha_arquivo=primeira_linha["numero_linha_arquivo"],
            ))

    df = df.drop(columns=["_data_ordenacao"])
    return df, anomalias_ordem


def filtrar_para_analise(historico: pd.DataFrame) -> pd.DataFrame:
    """Remove do historico as movimentacoes com indicador RESTITUIDO
    ('Restituido Por Redistribuicao') antes de qualquer analise (resumo por
    processo, deteccao de equalizacao, metricas etc.).

    Essas movimentacoes permanecem integralmente no historico completo
    (exportado em movimentacoes_consolidadas / na aba Movimentacoes), apenas
    nao influenciam nenhum campo derivado nem contagem."""
    return historico[historico["indicador_norm"] != INDICADOR_RESTITUIDO].reset_index(drop=True)


def derivar_resumo_processos(historico: pd.DataFrame, unidades_permanentes_norm: set[str]
                              ) -> tuple[pd.DataFrame, list[dict]]:
    """Deriva, para cada processo, os campos basicos de resumo listados na
    secao 7 (exceto os campos de equalizacao, calculados em equalization.py).
    """
    resumos = []
    anomalias_lista: list[dict] = []

    for processo_norm, grupo in historico.groupby("processo_norm", sort=False):
        grupo = grupo.sort_values("sequencia_movimento")
        primeira = grupo.iloc[0]
        ultima = grupo.iloc[-1]
        processo_original = primeira["processo"]
        arquivo_ref = primeira["arquivo_origem"]
        linha_ref = primeira["numero_linha_arquivo"]

        distribuicoes = grupo[grupo["indicador_norm"] == INDICADOR_DISTRIBUICAO]
        redistribuicoes = grupo[grupo["indicador_norm"] == INDICADOR_REDISTRIBUICAO]

        if not distribuicoes.empty:
            primeira_distribuicao = distribuicoes.sort_values("sequencia_movimento").iloc[0]
            data_caso_novo = primeira_distribuicao["data_dt"]
            unidade_distribuicao_inicial = primeira_distribuicao["orgao_norm"]
            unidade_distribuicao_inicial_original = primeira_distribuicao["orgao_julgador_original"]
        else:
            data_caso_novo = pd.NaT
            unidade_distribuicao_inicial = ""
            unidade_distribuicao_inicial_original = ""

        permanentes = grupo[~grupo["unidade_e_triagem"] & (grupo["orgao_norm"] != "")]
        if not permanentes.empty:
            ultima_permanente = permanentes.sort_values("sequencia_movimento").iloc[-1]
            unidade_final_real = ultima_permanente["orgao_norm"]
            unidade_final_real_original = ultima_permanente["orgao_julgador_original"]
        else:
            unidade_final_real = ""
            unidade_final_real_original = ""

        classes_distintas = set(c for c in grupo["classe_norm"].tolist() if c)
        classe_judicial = ultima["classe_norm"]

        passou_por_triagem = bool(grupo["unidade_e_triagem"].any())

        if primeira["indicador_norm"] != INDICADOR_DISTRIBUICAO:
            anomalias_lista.append(anomalies.novo(
                anomalies.PRIMEIRO_MOVIMENTO_NAO_DISTRIBUICAO, processo=processo_original,
                arquivo_origem=arquivo_ref, numero_linha_arquivo=linha_ref,
            ))
        if len(distribuicoes) > 1:
            anomalias_lista.append(anomalies.novo(
                anomalies.MULTIPLA_DISTRIBUICAO_INICIAL, processo=processo_original,
                arquivo_origem=arquivo_ref, numero_linha_arquivo=linha_ref,
            ))
        if pd.notna(data_caso_novo) and not redistribuicoes.empty:
            anteriores = redistribuicoes[
                redistribuicoes["data_dt"].notna() & (redistribuicoes["data_dt"] < data_caso_novo)
            ]
            if not anteriores.empty:
                anomalias_lista.append(anomalies.novo(
                    anomalies.REDISTRIBUICAO_ANTERIOR_A_DISTRIBUICAO, processo=processo_original,
                    arquivo_origem=arquivo_ref, numero_linha_arquivo=linha_ref,
                ))
        if len(classes_distintas) > 1:
            anomalias_lista.append(anomalies.novo(
                anomalies.CLASSE_JUDICIAL_DIVERGENTE, processo=processo_original,
                descricao=f"Classes divergentes para o processo {processo_original}: {sorted(classes_distintas)}",
                arquivo_origem=arquivo_ref, numero_linha_arquivo=linha_ref,
            ))
        if bool(ultima["unidade_e_triagem"]):
            anomalias_lista.append(anomalies.novo(
                anomalies.ULTIMO_MOVIMENTO_EM_TRIAGEM, processo=processo_original,
                arquivo_origem=arquivo_ref, numero_linha_arquivo=linha_ref,
            ))

        resumos.append({
            "processo": processo_original,
            "processo_norm": processo_norm,
            "data_caso_novo": data_caso_novo,
            "unidade_distribuicao_inicial": unidade_distribuicao_inicial,
            "unidade_distribuicao_inicial_original": unidade_distribuicao_inicial_original,
            "unidade_final_real": unidade_final_real,
            "unidade_final_real_original": unidade_final_real_original,
            "data_ultimo_movimento": ultima["data_dt"],
            "classe_judicial": classe_judicial,
            "quantidade_movimentos": int(len(grupo)),
            "quantidade_redistribuicoes": int(len(redistribuicoes)),
            "passou_por_triagem": passou_por_triagem,
            "municipio_sede": ultima["municipio_norm"],
            "municipio_sede_original": ultima["municipio_sede_original"],
            "arquivo_origem_ref": arquivo_ref,
            "numero_linha_arquivo_ref": linha_ref,
        })

    resumo_df = pd.DataFrame(resumos, columns=COLUNAS_RESUMO_PROCESSOS)
    resumo_df["passou_por_triagem"] = resumo_df["passou_por_triagem"].astype(bool)
    resumo_df["data_caso_novo"] = pd.to_datetime(resumo_df["data_caso_novo"])
    resumo_df["data_ultimo_movimento"] = pd.to_datetime(resumo_df["data_ultimo_movimento"])
    return resumo_df, anomalias_lista
