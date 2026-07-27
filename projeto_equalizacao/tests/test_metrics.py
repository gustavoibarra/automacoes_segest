import math

import pandas as pd

from src import filters, metrics
from tests.helpers import executar_pipeline_em_memoria

UNIDADES = {"UNIDADE A": "CEDENTE", "UNIDADE B": "DESTINATARIA"}


def test_dispersao_mad_e_desvio_padrao():
    quantidades = pd.Series([2, 4, 6, 8])
    disp = metrics.calcular_dispersao(quantidades)
    assert disp["media"] == 5
    assert disp["mad"] == sum(abs(v - 5) for v in [2, 4, 6, 8]) / 4
    assert math.isclose(disp["desvio_padrao"], quantidades.std(ddof=0))
    assert disp["amplitude"] == 6
    assert disp["qtd_acima_media"] == 2
    assert disp["qtd_abaixo_media"] == 2


def test_percentual_na_quando_sem_casos_novos():
    resultado = executar_pipeline_em_memoria([], UNIDADES)
    processos_df = resultado["processos_df"]
    unidades_df = resultado["unidades_df"]
    filtros = filters.FiltrosDashboard()
    processos_filtrados, unidades_filtradas = filters.aplicar_filtros(processos_df, unidades_df, filtros)
    m = metrics.calcular_todas_metricas(processos_filtrados, unidades_filtradas, resultado["episodios_df"], filtros)
    assert m["cards"]["casos_novos"] == 0
    assert m["cards"]["percentual_processos_equalizados"] is None


def test_filtro_sem_cedentes_nao_quebra_saldo_liquido():
    """Regressao: filtrar o dashboard de forma que o universo de unidades
    filtradas nao contenha nenhuma CEDENTE (ou nenhuma DESTINATARIA) nao pode
    quebrar processos_cedidos_por_unidade / saldo_liquido_por_unidade."""
    resultado = executar_pipeline_em_memoria([
        {"processo": "P1", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026", "linha": 1},
        {"processo": "P1", "indicador": "Redistribuição", "unidade": "Setor de Triagem", "data": "05/01/2026", "linha": 2},
        {"processo": "P1", "indicador": "Redistribuição", "unidade": "Unidade B", "data": "10/01/2026", "linha": 3},
    ], UNIDADES)
    processos_df = resultado["processos_df"]
    unidades_df = resultado["unidades_df"]

    filtros = filters.FiltrosDashboard(grupos=["DESTINATARIA"])
    processos_filtrados, unidades_filtradas = filters.aplicar_filtros(processos_df, unidades_df, filtros)
    m = metrics.calcular_todas_metricas(processos_filtrados, unidades_filtradas, resultado["episodios_df"], filtros)

    assert m["cedidos"].empty
    assert list(m["cedidos"].columns) == [
        "unidade", "unidade_norm", "classificacao", "quantidade_processos_cedidos",
        "percentual_do_total_cedido", "quantidade_destinatarias_diferentes", "media_diaria", "media_semanal",
    ]
    assert not m["saldo_liquido"].empty
