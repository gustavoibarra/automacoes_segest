import pandas as pd
import pytest

from src import dados
from tests.helpers import escrever_consolidado_fixture


def test_carregar_consolidado_le_as_tres_abas(tmp_path):
    caminho = escrever_consolidado_fixture(tmp_path / "consolidado.xlsx")
    base = dados.carregar_consolidado(caminho)
    assert set(base.keys()) == {"processos", "movimentacoes", "comparativo"}
    assert len(base["processos"]) == 4
    assert pd.api.types.is_datetime64_any_dtype(base["processos"]["data_caso_novo"])


def test_carregar_consolidado_erro_quando_arquivo_nao_existe(tmp_path):
    with pytest.raises(dados.DadosError):
        dados.carregar_consolidado(tmp_path / "nao_existe.xlsx")


def test_unidades_mestre_deduplica_por_unidade(tmp_path):
    caminho = escrever_consolidado_fixture(tmp_path / "consolidado.xlsx")
    base = dados.carregar_consolidado(caminho)
    unidades = dados.unidades_mestre(base["comparativo"])
    assert len(unidades) == 3
    assert set(unidades["unidade_norm"]) == {"UNIDADE A", "UNIDADE B", "UNIDADE C"}
    assert unidades.set_index("unidade_norm")["quantidade_magistrados"].to_dict() == {
        "UNIDADE A": 2, "UNIDADE B": 1, "UNIDADE C": 2,
    }


def test_resolver_periodo_padrao_cobre_toda_a_base(tmp_path):
    caminho = escrever_consolidado_fixture(tmp_path / "consolidado.xlsx")
    base = dados.carregar_consolidado(caminho)
    inicio, fim = dados.resolver_periodo(base["processos"])
    assert inicio == pd.Timestamp("2026-06-15")  # menor data_caso_novo (processo P3)
    assert fim.date() == pd.Timestamp("2026-07-10").date()  # maior data_ultimo_movimento


def test_casos_novos_periodo_usa_data_caso_novo(tmp_path):
    caminho = escrever_consolidado_fixture(tmp_path / "consolidado.xlsx")
    base = dados.carregar_consolidado(caminho)
    inicio, fim = dados.resolver_periodo(base["processos"], pd.Timestamp("2026-07-01"), pd.Timestamp("2026-07-31"))
    casos_novos = dados.casos_novos_periodo(base["processos"], inicio, fim)
    # P3 tem data_caso_novo em junho -> fora do periodo de casos novos
    assert set(casos_novos["processo_norm"]) == {"P1", "P2", "P4"}


def test_processos_movimentados_inclui_redistribuicao_de_processo_antigo(tmp_path):
    caminho = escrever_consolidado_fixture(tmp_path / "consolidado.xlsx")
    base = dados.carregar_consolidado(caminho)
    inicio, fim = dados.resolver_periodo(base["processos"], pd.Timestamp("2026-07-01"), pd.Timestamp("2026-07-31"))
    movimentados = dados.processos_movimentados_periodo(base["processos"], base["movimentacoes"], inicio, fim)
    # P3 teve distribuicao em junho, mas redistribuicoes dentro do periodo -> deve entrar
    assert "P3" in set(movimentados["processo_norm"])
    # P5 so tem uma movimentacao no periodo, mas e RESTITUIDO -> nao deve entrar
    assert "P5" not in set(movimentados["processo_norm"])


def test_processos_movimentados_diverge_de_casos_novos(tmp_path):
    caminho = escrever_consolidado_fixture(tmp_path / "consolidado.xlsx")
    base = dados.carregar_consolidado(caminho)
    inicio, fim = dados.resolver_periodo(base["processos"], pd.Timestamp("2026-07-01"), pd.Timestamp("2026-07-31"))
    casos_novos = dados.casos_novos_periodo(base["processos"], inicio, fim)
    movimentados = dados.processos_movimentados_periodo(base["processos"], base["movimentacoes"], inicio, fim)
    assert set(casos_novos["processo_norm"]) != set(movimentados["processo_norm"])
    assert set(movimentados["processo_norm"]) == {"P1", "P2", "P3", "P4"}
