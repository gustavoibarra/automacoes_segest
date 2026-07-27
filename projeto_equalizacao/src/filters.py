"""Aplicacao dos filtros do dashboard sobre a tabela de processos ja
totalmente reconstruida (secao 10 e 16 do prompt).

Importante: os filtros SO sao aplicados depois que o historico completo de
cada processo e a deteccao de equalizacao ja foram calculados sobre a base
inteira. Isso garante que uma equalizacao nao deixe de ser identificada so
porque a distribuicao inicial ocorreu antes do periodo selecionado ou o
destino ocorreu depois dele.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

PAPEL_UNIDADE_FINAL_REAL = "unidade final real"
PAPEL_UNIDADE_INICIAL = "unidade inicial"
PAPEL_UNIDADE_CEDENTE = "unidade cedente da equalizacao"
PAPEL_UNIDADE_DESTINATARIA = "unidade destinataria da equalizacao"
PAPEL_UNIDADE_SIMULADA = "unidade simulada sem equalizacao"

PAPEIS_UNIDADE = (
    PAPEL_UNIDADE_FINAL_REAL,
    PAPEL_UNIDADE_INICIAL,
    PAPEL_UNIDADE_CEDENTE,
    PAPEL_UNIDADE_DESTINATARIA,
    PAPEL_UNIDADE_SIMULADA,
)

_PAPEL_COLUNAS = {
    PAPEL_UNIDADE_FINAL_REAL: ("unidade_final_real", "unidade_final_real_original"),
    PAPEL_UNIDADE_INICIAL: ("unidade_distribuicao_inicial", "unidade_distribuicao_inicial_original"),
    PAPEL_UNIDADE_CEDENTE: ("unidade_cedente_equalizacao", "unidade_cedente_equalizacao_original"),
    PAPEL_UNIDADE_DESTINATARIA: ("unidade_destinataria_equalizacao", "unidade_destinataria_equalizacao_original"),
    PAPEL_UNIDADE_SIMULADA: ("unidade_simulada_sem_equalizacao", "unidade_simulada_sem_equalizacao_original"),
}

BASE_TEMPORAL_CASO_NOVO = "caso_novo"
BASE_TEMPORAL_CONCLUSAO_EQUALIZACAO = "conclusao_equalizacao"
BASE_TEMPORAL_ULTIMO_MOVIMENTO = "ultimo_movimento"
BASE_TEMPORAL_ENTRADA_TRIAGEM = "entrada_triagem"

BASES_TEMPORAIS_SELECIONAVEIS = (
    BASE_TEMPORAL_CASO_NOVO,
    BASE_TEMPORAL_CONCLUSAO_EQUALIZACAO,
    BASE_TEMPORAL_ULTIMO_MOVIMENTO,
)

_BASE_TEMPORAL_COLUNAS = {
    BASE_TEMPORAL_CASO_NOVO: "data_caso_novo",
    BASE_TEMPORAL_CONCLUSAO_EQUALIZACAO: "data_destino_equalizacao",
    BASE_TEMPORAL_ULTIMO_MOVIMENTO: "data_ultimo_movimento",
    BASE_TEMPORAL_ENTRADA_TRIAGEM: "data_entrada_triagem",
}

SITUACAO_EQUALIZADO_VALIDO = "EQUALIZADO_VALIDO"
SITUACAO_FORA_PADRAO = "FORA_PADRAO"
SITUACAO_INCOMPLETA = "INCOMPLETA"
SITUACAO_NAO_EQUALIZADO = "NAO_EQUALIZADO"


def coluna_papel(papel_unidade: str) -> tuple[str, str]:
    return _PAPEL_COLUNAS[papel_unidade]


def coluna_base_temporal(base_temporal: str) -> str:
    return _BASE_TEMPORAL_COLUNAS[base_temporal]


@dataclass
class FiltrosDashboard:
    data_inicial: pd.Timestamp | None = None
    data_final: pd.Timestamp | None = None
    base_temporal: str = BASE_TEMPORAL_CASO_NOVO
    grupos: list = field(default_factory=list)          # CEDENTE / NEUTRA / DESTINATARIA
    unidades: list = field(default_factory=list)         # unidade_norm
    papel_unidade: str = PAPEL_UNIDADE_FINAL_REAL
    classe_judicial: list = field(default_factory=list)
    municipio_sede: list = field(default_factory=list)
    tipo_movimentacao: list = field(default_factory=list)  # DISTRIBUICAO / REDISTRIBUICAO
    situacao_equalizacao: list = field(default_factory=list)
    com_anomalia: str | None = None  # 'COM' | 'SEM' | None


def situacao_processo(row) -> str:
    if row["equalizacao_valida"]:
        return SITUACAO_EQUALIZADO_VALIDO
    if row["quantidade_episodios_triagem"] == 0:
        return SITUACAO_NAO_EQUALIZADO
    if row.get("motivo_invalidade_equalizacao", "") and "definitiva apos a triagem" in str(row.get("motivo_invalidade_equalizacao", "")):
        return SITUACAO_INCOMPLETA
    return SITUACAO_FORA_PADRAO


def aplicar_filtros(processos_df: pd.DataFrame, unidades_permanentes_df: pd.DataFrame,
                     filtros: FiltrosDashboard) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aplica os filtros do dashboard.

    Retorna (processos_filtrados, unidades_filtradas). unidades_filtradas
    contem todas as unidades permanentes que atendem aos filtros de grupo e
    unidade -- inclusive as que nao receberam nenhum processo -- e e usada
    como denominador nas medias e como universo das tabelas comparativas.
    """
    df = processos_df.copy()
    unidades_df = unidades_permanentes_df.copy()

    if "situacao_equalizacao" not in df.columns:
        df["situacao_equalizacao"] = df.apply(situacao_processo, axis=1)

    if filtros.grupos:
        unidades_df = unidades_df[unidades_df["classificacao"].isin(filtros.grupos)]
    if filtros.unidades:
        unidades_df = unidades_df[unidades_df["unidade_norm"].isin(filtros.unidades)]

    col_norm, _ = coluna_papel(filtros.papel_unidade)

    if filtros.grupos or filtros.unidades:
        unidades_permitidas = set(unidades_df["unidade_norm"])
        df = df[df[col_norm].isin(unidades_permitidas)]

    col_data = coluna_base_temporal(filtros.base_temporal)
    if filtros.data_inicial is not None:
        df = df[df[col_data].notna() & (df[col_data] >= filtros.data_inicial)]
    if filtros.data_final is not None:
        df = df[df[col_data].notna() & (df[col_data] <= filtros.data_final)]

    if filtros.classe_judicial:
        df = df[df["classe_judicial"].isin(filtros.classe_judicial)]
    if filtros.municipio_sede:
        df = df[df["municipio_sede"].isin(filtros.municipio_sede)]

    if filtros.tipo_movimentacao:
        tipos = set(filtros.tipo_movimentacao)
        if "REDISTRIBUICAO" in tipos and "DISTRIBUICAO" not in tipos:
            df = df[df["quantidade_redistribuicoes"] > 0]
        elif "DISTRIBUICAO" in tipos and "REDISTRIBUICAO" not in tipos:
            df = df[df["quantidade_redistribuicoes"] == 0]

    if filtros.situacao_equalizacao:
        df = df[df["situacao_equalizacao"].isin(filtros.situacao_equalizacao)]

    if filtros.com_anomalia == "COM":
        df = df[df.get("tem_anomalia", False) == True]  # noqa: E712
    elif filtros.com_anomalia == "SEM":
        df = df[df.get("tem_anomalia", False) == False]  # noqa: E712

    return df.reset_index(drop=True), unidades_df.reset_index(drop=True)


def filtrar_movimentos_para_exibicao(movimentos_df: pd.DataFrame, processos_filtrados: pd.DataFrame
                                      ) -> pd.DataFrame:
    """Restringe a tabela de movimentacoes aos processos que sobreviveram
    aos filtros, para uso nas tabelas detalhadas e na consulta por processo."""
    processos_validos = set(processos_filtrados["processo_norm"])
    return movimentos_df[movimentos_df["processo_norm"].isin(processos_validos)].reset_index(drop=True)
