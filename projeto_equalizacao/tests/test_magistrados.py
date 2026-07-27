"""Testes do grupo de medidas ponderadas pela quantidade de magistrados de
cada unidade: leitura da coluna no arquivo de classificacao, calculo das
taxas por unidade e da dispersao em torno da media ponderada do sistema."""
import math

import pandas as pd
import pytest

from src import filters, loaders, metrics
from tests.helpers import executar_pipeline_em_memoria

UNIDADES = {"UNIDADE A": "CEDENTE", "UNIDADE B": "DESTINATARIA"}
MAGISTRADOS = {"UNIDADE A": 2, "UNIDADE B": 1}


# ---------------------------------------------------------------------------
# Leitura do arquivo de classificacao
# ---------------------------------------------------------------------------

def test_carrega_quantidade_magistrados(tmp_path):
    df = pd.DataFrame({
        "Unidade": ["1 Vara do Trabalho", "2 Vara do Trabalho"],
        "Classificacao": ["Cedente", "Destinataria"],
        "Quantidade de Magistrados": [2, 1],
    })
    caminho = tmp_path / "classificacao.xlsx"
    df.to_excel(caminho, index=False)

    unidades_df, avisos = loaders.carregar_classificacao_unidades(caminho)
    assert list(unidades_df["quantidade_magistrados"]) == [2.0, 1.0]
    assert not any("magistrado" in a.lower() for a in avisos)


def test_avisa_quando_coluna_de_magistrados_ausente(tmp_path):
    df = pd.DataFrame({
        "Unidade": ["1 Vara do Trabalho"],
        "Classificacao": ["Cedente"],
    })
    caminho = tmp_path / "classificacao_sem_magistrados.xlsx"
    df.to_excel(caminho, index=False)

    unidades_df, avisos = loaders.carregar_classificacao_unidades(caminho)
    assert unidades_df.iloc[0]["quantidade_magistrados"] != unidades_df.iloc[0]["quantidade_magistrados"]  # NaN
    assert any("nao possui uma coluna de quantidade de magistrados" in a for a in avisos)


def test_avisa_quando_valor_de_magistrados_invalido(tmp_path):
    df = pd.DataFrame({
        "Unidade": ["1 Vara do Trabalho", "2 Vara do Trabalho"],
        "Classificacao": ["Cedente", "Destinataria"],
        "Quantidade de Magistrados": [2, "n/d"],
    })
    caminho = tmp_path / "classificacao_invalida.xlsx"
    df.to_excel(caminho, index=False)

    unidades_df, avisos = loaders.carregar_classificacao_unidades(caminho)
    linha_invalida = unidades_df[unidades_df["unidade_original"] == "2 Vara do Trabalho"].iloc[0]
    assert math.isnan(linha_invalida["quantidade_magistrados"])
    assert any("quantidade de magistrados ausente ou invalida" in a for a in avisos)


# ---------------------------------------------------------------------------
# Calculo das medidas ponderadas por magistrado (src/metrics.py)
# ---------------------------------------------------------------------------

def _tabela_exemplo():
    unidades = pd.DataFrame({
        "unidade_norm": ["A", "B", "C"],
        "unidade_original": ["A", "B", "C"],
        "classificacao": ["CEDENTE", "DESTINATARIA", "NEUTRA"],
        "quantidade_magistrados": [2, 1, 2],
    })
    processos = pd.DataFrame({
        "processo_norm": ["P1", "P2", "P3", "P4", "P5", "P6"],
        "unidade_final_real": ["A", "A", "A", "A", "B", "C"],
    })
    return metrics.tabela_por_unidade(unidades, processos, "unidade_final_real")


def test_tabela_por_unidade_calcula_processos_por_magistrado():
    tabela = _tabela_exemplo()
    valores = tabela.set_index("unidade_norm")["processos_por_magistrado"]
    assert valores["A"] == pytest.approx(2.0)   # 4 processos / 2 magistrados
    assert valores["B"] == pytest.approx(1.0)   # 1 processo / 1 magistrado
    assert valores["C"] == pytest.approx(0.5)   # 1 processo / 2 magistrados


def test_media_ponderada_por_magistrado():
    tabela = _tabela_exemplo()
    # total processos = 6, total magistrados = 5 -> 1.2 (nao e a media simples das taxas, que seria 1.1667)
    assert metrics.media_ponderada_por_magistrado(tabela) == pytest.approx(1.2)


def test_dispersao_por_magistrado_usa_media_ponderada_como_centro():
    tabela = _tabela_exemplo()
    disp = metrics.dispersao_por_magistrado(tabela)
    assert disp["media"] == pytest.approx(1.2)
    # MAD em torno de 1.2: |2.0-1.2| + |1.0-1.2| + |0.5-1.2| ; media dos 3
    mad_esperado = (abs(2.0 - 1.2) + abs(1.0 - 1.2) + abs(0.5 - 1.2)) / 3
    assert disp["mad"] == pytest.approx(mad_esperado)


def test_unidade_sem_magistrados_fica_de_fora_da_media_ponderada():
    unidades = pd.DataFrame({
        "unidade_norm": ["A", "B"],
        "unidade_original": ["A", "B"],
        "classificacao": ["CEDENTE", "DESTINATARIA"],
        "quantidade_magistrados": [2, float("nan")],
    })
    processos = pd.DataFrame({"processo_norm": ["P1", "P2", "P3"], "unidade_final_real": ["A", "A", "B"]})
    tabela = metrics.tabela_por_unidade(unidades, processos, "unidade_final_real")

    linha_b = tabela[tabela["unidade_norm"] == "B"].iloc[0]
    assert math.isnan(linha_b["processos_por_magistrado"])
    # media ponderada considera so a unidade A: 2 processos / 2 magistrados = 1.0
    assert metrics.media_ponderada_por_magistrado(tabela) == pytest.approx(1.0)


def test_tabela_por_unidade_sem_coluna_magistrados_nao_quebra():
    """Compatibilidade com bases antigas: se a tabela de unidades nao tiver
    a coluna quantidade_magistrados, tudo deve retornar N/A, sem erro."""
    unidades = pd.DataFrame({
        "unidade_norm": ["A"], "unidade_original": ["A"], "classificacao": ["CEDENTE"],
    })
    processos = pd.DataFrame({"processo_norm": ["P1"], "unidade_final_real": ["A"]})
    tabela = metrics.tabela_por_unidade(unidades, processos, "unidade_final_real")

    assert "processos_por_magistrado" in tabela.columns
    assert tabela["processos_por_magistrado"].isna().all()
    assert math.isnan(metrics.media_ponderada_por_magistrado(tabela))


def test_calcular_dispersao_media_referencia_compativel_com_media_simples():
    """Sem media_referencia, o comportamento deve ser identico ao anterior
    (media simples, desvio-padrao populacional em torno da propria media)."""
    valores = pd.Series([2, 4, 6, 8])
    disp_padrao = metrics.calcular_dispersao(valores)
    disp_explicito = metrics.calcular_dispersao(valores, media_referencia=valores.mean())
    assert disp_padrao == pytest.approx(disp_explicito)
    assert disp_padrao["desvio_padrao"] == pytest.approx(valores.std(ddof=0))


# ---------------------------------------------------------------------------
# Fim a fim: cards executivos e dispersao no pipeline completo
# ---------------------------------------------------------------------------

def test_cards_e_dispersao_magistrado_no_pipeline_completo():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P1", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026", "linha": 1},
        {"processo": "P2", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026", "linha": 1},
        {"processo": "P3", "indicador": "Distribuição", "unidade": "Unidade B", "data": "01/01/2026", "linha": 1},
    ], UNIDADES, MAGISTRADOS)
    processos_df = resultado["processos_df"]
    unidades_df = resultado["unidades_df"]

    filtros = filters.FiltrosDashboard()
    processos_filtrados, unidades_filtradas = filters.aplicar_filtros(processos_df, unidades_df, filtros)
    m = metrics.calcular_todas_metricas(processos_filtrados, unidades_filtradas, resultado["episodios_df"], filtros)

    # 2 processos em A (2 magistrados) + 1 em B (1 magistrado) = 3 processos / 3 magistrados = 1.0
    assert m["dispersao_magistrado_com"]["media"] == pytest.approx(1.0)
    assert m["cards"]["media_ponderada_magistrado_com_equalizacao"] == pytest.approx(1.0)
    assert m["cards"]["media_ponderada_magistrado_sem_equalizacao"] == pytest.approx(1.0)
    assert "diferenca_absoluta_media_magistrado" in m["tabela_com"].columns


def test_cards_magistrado_none_quando_sem_dados_de_magistrado():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P1", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026", "linha": 1},
    ], UNIDADES)  # sem mapa_magistrados
    processos_df = resultado["processos_df"]
    unidades_df = resultado["unidades_df"]

    filtros = filters.FiltrosDashboard()
    processos_filtrados, unidades_filtradas = filters.aplicar_filtros(processos_df, unidades_df, filtros)
    m = metrics.calcular_todas_metricas(processos_filtrados, unidades_filtradas, resultado["episodios_df"], filtros)

    assert m["cards"]["media_ponderada_magistrado_com_equalizacao"] is None
    assert m["cards"]["media_ponderada_magistrado_sem_equalizacao"] is None
    assert m["cards"]["reducao_dispersao_magistrado_pct"] is None
