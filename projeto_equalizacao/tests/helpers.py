"""Utilitarios compartilhados pelos testes: constroem DataFrames minimos de
movimentacoes e de classificacao de unidades, e executam a pipeline real
(sem passar por arquivos em disco) para os testes de aceitacao.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from src import equalization, histories, metrics, validation
from src.normalization import INDICADOR_RESTITUIDO, normalize_unit_name


_COLUNAS_MOVIMENTO = [
    "#Processo", "Indicador", "Município Sede", "Órgão Julgador", "Classe Judicial", "Data",
    "arquivo_origem", "data_arquivo", "ordem_arquivo", "numero_linha_arquivo", "data_processamento",
]


def construir_movimentos(linhas: list[dict]) -> pd.DataFrame:
    """Cada linha aceita: processo, indicador, unidade, data (str dd/mm/yyyy
    ou datetime), classe (opcional), municipio (opcional), arquivo (opcional),
    ordem_arquivo (opcional), linha (opcional)."""
    if not linhas:
        return pd.DataFrame(columns=_COLUNAS_MOVIMENTO)
    registros = []
    for i, linha in enumerate(linhas):
        data = linha["data"]
        if isinstance(data, str):
            data_dt = datetime.strptime(data, "%d/%m/%Y")
        else:
            data_dt = data
        registros.append({
            "#Processo": linha["processo"],
            "Indicador": linha["indicador"],
            "Município Sede": linha.get("municipio", "FLORIANOPOLIS"),
            "Órgão Julgador": linha["unidade"],
            "Classe Judicial": linha.get("classe", "ATSUM"),
            "Data": data_dt,
            "arquivo_origem": linha.get("arquivo", "processos_01-01-2026.csv"),
            "data_arquivo": datetime.strptime(linha.get("data_arquivo", "01-01-2026"), "%d-%m-%Y"),
            "ordem_arquivo": linha.get("ordem_arquivo", 0),
            "numero_linha_arquivo": linha.get("linha", i + 1),
            "data_processamento": datetime.now(),
        })
    return pd.DataFrame(registros)


def construir_unidades(mapa_classificacao: dict, mapa_magistrados: dict | None = None) -> pd.DataFrame:
    registros = []
    for nome, classificacao in mapa_classificacao.items():
        registros.append({
            "unidade_original": nome,
            "unidade_norm": normalize_unit_name(nome),
            "classificacao": classificacao,
            "quantidade_magistrados": float((mapa_magistrados or {}).get(nome, float("nan"))),
        })
    return pd.DataFrame(registros)


def executar_pipeline_em_memoria(linhas_movimento: list[dict], mapa_unidades: dict, mapa_magistrados: dict | None = None):
    """Executa o caminho real do pipeline (validation -> histories ->
    equalization) sobre dados construidos em memoria, retornando
    (processos_df, historico_df, episodios_df, anomalias)."""
    unidades_df = construir_unidades(mapa_unidades, mapa_magistrados)
    unidades_norm = set(unidades_df["unidade_norm"])

    bruto = construir_movimentos(linhas_movimento)
    bruto = validation.padronizar_colunas(bruto)
    bruto = validation.normalizar_movimentos(bruto)

    bruto_analise = bruto[bruto["indicador_norm"] != INDICADOR_RESTITUIDO]
    anomalias_linha = validation.detectar_anomalias_linha(bruto_analise, unidades_norm)
    dedup, anomalias_dup = validation.deduplicar_movimentos(bruto)

    historico_df, anomalias_ordem = histories.reconstruir_historico(dedup)
    historico_analise_df = histories.filtrar_para_analise(historico_df)
    resumo_df, anomalias_resumo = histories.derivar_resumo_processos(historico_analise_df, unidades_norm)

    episodios_df, campos_eq_df, anomalias_eq = equalization.detectar_equalizacoes(historico_analise_df, unidades_df)

    processos_df = pd.merge(resumo_df, campos_eq_df, on="processo_norm", how="left")
    processos_df = equalization.calcular_unidade_simulada_sem_equalizacao(processos_df)
    processos_df = metrics.enriquecer_classificacoes(processos_df, unidades_df)

    todas_anomalias = anomalias_linha + anomalias_dup + anomalias_ordem + anomalias_resumo + anomalias_eq

    return {
        "processos_df": processos_df,
        "historico_df": historico_df,
        "episodios_df": episodios_df,
        "anomalias": todas_anomalias,
        "unidades_df": unidades_df,
        "dedup_df": dedup,
    }


def linha_processo(processos_df: pd.DataFrame, processo: str) -> pd.Series:
    resultado = processos_df[processos_df["processo"] == processo]
    assert len(resultado) == 1, f"Processo {processo} nao encontrado ou duplicado: {resultado}"
    return resultado.iloc[0]
