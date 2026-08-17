import math

import pandas as pd
import pytest

from src import metricas


def _unidades():
    return pd.DataFrame({
        "unidade_norm": ["A", "B", "C"],
        "unidade_original": ["A", "B", "C"],
        "classificacao": ["CEDENTE", "DESTINATARIA", "NEUTRA"],
        "quantidade_magistrados": [2, 1, 2],
    })


def _processos():
    return pd.DataFrame({
        "processo_norm": [f"P{i}" for i in range(1, 9)],
        "unidade_final_real": ["B", "B", "C", "C", "B", "A", "A", "A"],
        "unidade_simulada_sem_equalizacao": ["A", "A", "C", "C", "A", "A", "A", "A"],
    })


def test_classificar_cv_faixas():
    assert metricas.classificar_cv(5) == "Distribuição bastante homogênea"
    assert metricas.classificar_cv(10) == "Dispersão relativamente baixa"
    assert metricas.classificar_cv(25) == "Dispersão relevante"
    assert metricas.classificar_cv(35) == "Dispersão elevada"
    assert metricas.classificar_cv(45) == "Dispersão muito elevada"
    assert metricas.classificar_cv(float("nan")) == "N/A"


def test_calcular_dispersao_media_simples():
    disp = metricas.calcular_dispersao(pd.Series([2, 4, 6, 8]))
    assert disp["media"] == 5
    assert disp["mad"] == pytest.approx(2.0)
    assert disp["desvio_padrao"] == pytest.approx(pd.Series([2, 4, 6, 8]).std(ddof=0))
    assert disp["minimo"] == 2 and disp["maximo"] == 8
    assert disp["amplitude"] == 6


def test_calcular_dispersao_com_media_referencia_externa():
    disp = metricas.calcular_dispersao(pd.Series([2.0, 1.0, 0.5]), media_referencia=1.2)
    assert disp["media"] == 1.2
    esperado_mad = (abs(2.0 - 1.2) + abs(1.0 - 1.2) + abs(0.5 - 1.2)) / 3
    assert disp["mad"] == pytest.approx(esperado_mad)


def test_calcular_dispersao_ignora_nan():
    disp = metricas.calcular_dispersao(pd.Series([2.0, float("nan"), 4.0]))
    assert disp["media"] == 3.0


def test_tabela_por_unidade_inclui_zero_processos():
    tabela = metricas.tabela_por_unidade(_unidades(), _processos(), "unidade_final_real")
    linha_c = tabela[tabela["unidade_norm"] == "C"].iloc[0]
    linha_b = tabela[tabela["unidade_norm"] == "B"].iloc[0]
    assert linha_c["quantidade"] == 2
    assert linha_b["processos_por_magistrado"] == pytest.approx(3.0)  # 3 processos / 1 magistrado


def test_media_ponderada_por_magistrado():
    tabela = metricas.tabela_por_unidade(_unidades(), _processos(), "unidade_final_real")
    # total processos=8, total magistrados=5 -> 1.6 (nao e media simples das taxas)
    assert metricas.media_ponderada_por_magistrado(tabela) == pytest.approx(8 / 5)


def test_kpis_percentual_e_reducao_cv():
    unidades = _unidades()
    processos = _processos()
    tabela_com = metricas.cenario_com_equalizacao(unidades, processos)
    tabela_sem = metricas.cenario_sem_equalizacao(unidades, processos)
    casos_novos_df = pd.DataFrame({
        "processo_norm": processos["processo_norm"],
        "equalizacao_valida": [True, True, False, False, True, False, False, False],
    })
    resultado = metricas.kpis(casos_novos_df, tabela_com, tabela_sem)
    assert resultado["casos_novos"] == 8
    assert resultado["processos_equalizados"] == 3
    assert resultado["percentual_equalizados"] == pytest.approx(37.5)


def test_tabela_grupos_tem_linha_total_do_sistema():
    unidades = _unidades()
    processos = _processos()
    tabela_com = metricas.cenario_com_equalizacao(unidades, processos)
    tabela_sem = metricas.cenario_sem_equalizacao(unidades, processos)
    grupos = metricas.tabela_grupos(unidades, tabela_com, tabela_sem)
    assert "Total do sistema" in grupos["grupo"].tolist()
    total = grupos[grupos["grupo"] == "Total do sistema"].iloc[0]
    assert total["total_com"] == int(tabela_com["quantidade"].sum())
    assert total["total_sem"] == int(tabela_sem["quantidade"].sum())
    assert total["total_com"] == total["total_sem"]  # mesma quantidade total nos dois cenarios


def test_convergencia_cedentes_destinatarias():
    unidades = _unidades()
    processos = _processos()
    tabela_com = metricas.cenario_com_equalizacao(unidades, processos)
    tabela_sem = metricas.cenario_sem_equalizacao(unidades, processos)
    grupos = metricas.tabela_grupos(unidades, tabela_com, tabela_sem)
    conv = metricas.convergencia_cedentes_destinatarias(grupos)
    assert conv["unidade"]["reducao_relativa_pct"] is not None
    assert conv["unidade"]["sem"] >= 0
    assert conv["magistrado"]["sem"] >= 0


def test_dimensao_dispersao_reducao_cv():
    unidades = _unidades()
    processos = _processos()
    tabela_com = metricas.cenario_com_equalizacao(unidades, processos)
    tabela_sem = metricas.cenario_sem_equalizacao(unidades, processos)
    dim = metricas.dimensao_dispersao(tabela_com, tabela_sem, "quantidade")
    assert dim["sem"]["media"] == pytest.approx(dim["com"]["media"])  # mesma media, dispersao diferente
    assert dim["faixa_sem"] in {r for _, _, r, _ in __import__("config").FAIXAS_CV}


def test_tabela_anexo_cedentes_casos_novos_por_distribuicao_inicial():
    unidades = _unidades()
    processos = _processos()
    tabela_com = metricas.cenario_com_equalizacao(unidades, processos)
    tabela_sem = metricas.cenario_sem_equalizacao(unidades, processos)
    casos_novos_df = pd.DataFrame({
        "processo_norm": processos["processo_norm"],
        "unidade_distribuicao_inicial": ["A"] * 6 + ["A", "A"],
        "unidade_cedente_equalizacao": ["A", "A", "", "", "A", "", "", ""],
        "equalizacao_valida": [True, True, False, False, True, False, False, False],
    })
    anexo = metricas.tabela_anexo_cedentes(unidades, casos_novos_df, tabela_com, tabela_sem)
    linha_a = anexo[anexo["unidade_norm"] == "A"].iloc[0]
    assert linha_a["casos_novos"] == 8
    assert linha_a["equalizados"] == 3
