"""Testes de aceitacao obrigatorios 7, 8 e 9 (secao 26 do prompt)."""
import pandas as pd

from src import filters, metrics
from tests.helpers import executar_pipeline_em_memoria

UNIDADES = {
    "UNIDADE A": "CEDENTE",
    "UNIDADE B": "DESTINATARIA",
    "UNIDADE C": "NEUTRA",
}
TRIAGEM = "Setor de Triagem"


def _movimentos_mistos():
    return [
        # nao equalizado
        {"processo": "P1", "indicador": "Distribuição", "unidade": "Unidade C", "data": "01/01/2026", "linha": 1},
        # equalizado valido
        {"processo": "P2", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026", "linha": 1},
        {"processo": "P2", "indicador": "Redistribuição", "unidade": TRIAGEM, "data": "05/01/2026", "linha": 2},
        {"processo": "P2", "indicador": "Redistribuição", "unidade": "Unidade B", "data": "10/01/2026", "linha": 3},
        # incompleta
        {"processo": "P3", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026", "linha": 1},
        {"processo": "P3", "indicador": "Redistribuição", "unidade": TRIAGEM, "data": "05/01/2026", "linha": 2},
        # fora do padrao
        {"processo": "P4", "indicador": "Distribuição", "unidade": "Unidade C", "data": "01/01/2026", "linha": 1},
        {"processo": "P4", "indicador": "Redistribuição", "unidade": TRIAGEM, "data": "05/01/2026", "linha": 2},
        {"processo": "P4", "indicador": "Redistribuição", "unidade": "Unidade B", "data": "10/01/2026", "linha": 3},
    ]


def test_cenario7_igualdade_dos_totais():
    resultado = executar_pipeline_em_memoria(_movimentos_mistos(), UNIDADES)
    processos_df = resultado["processos_df"]
    unidades_df = resultado["unidades_df"]

    filtros = filters.FiltrosDashboard()
    processos_filtrados, unidades_filtradas = filters.aplicar_filtros(processos_df, unidades_df, filtros)
    m = metrics.calcular_todas_metricas(processos_filtrados, unidades_filtradas, resultado["episodios_df"], filtros)

    assert m["erros_consistencia"] == []
    assert int(m["tabela_com"]["quantidade"].sum()) == m["casos_novos"]
    assert int(m["tabela_sem"]["quantidade"].sum()) == m["casos_novos"]
    assert m["casos_novos"] == 4


def test_cenario8_unidade_com_zero_processos():
    unidades = dict(UNIDADES)
    unidades["UNIDADE D"] = "DESTINATARIA"
    resultado = executar_pipeline_em_memoria(_movimentos_mistos(), unidades)
    processos_df = resultado["processos_df"]
    unidades_df = resultado["unidades_df"]

    filtros = filters.FiltrosDashboard()
    processos_filtrados, unidades_filtradas = filters.aplicar_filtros(processos_df, unidades_df, filtros)
    tabela_com = metrics.cenario_com_equalizacao(processos_filtrados, unidades_filtradas)

    linha_d = tabela_com[tabela_com["unidade_norm"] == "UNIDADE D"]
    assert len(linha_d) == 1
    assert linha_d.iloc[0]["quantidade"] == 0

    disp = metrics.calcular_dispersao(tabela_com["quantidade"])
    assert disp["media"] == tabela_com["quantidade"].mean()


def test_cenario9_filtro_nao_quebra_historico():
    linhas = [
        {"processo": "P9", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026", "linha": 1},
        {"processo": "P9", "indicador": "Redistribuição", "unidade": TRIAGEM, "data": "12/01/2026", "linha": 2},
        {"processo": "P9", "indicador": "Redistribuição", "unidade": "Unidade B", "data": "15/01/2026", "linha": 3},
    ]
    resultado = executar_pipeline_em_memoria(linhas, UNIDADES)
    processos_df = resultado["processos_df"]
    unidades_df = resultado["unidades_df"]

    filtros = filters.FiltrosDashboard(
        data_inicial=pd.Timestamp("2026-01-10"), data_final=pd.Timestamp("2026-01-20"),
        base_temporal=filters.BASE_TEMPORAL_CONCLUSAO_EQUALIZACAO,
    )
    processos_filtrados, _ = filters.aplicar_filtros(processos_df, unidades_df, filtros)

    assert len(processos_filtrados) == 1
    linha = processos_filtrados.iloc[0]
    assert linha["equalizacao_valida"] == True
    assert linha["unidade_cedente_equalizacao"] == "UNIDADE A"
    assert linha["unidade_destinataria_equalizacao"] == "UNIDADE B"
