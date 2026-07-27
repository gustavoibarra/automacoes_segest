from src import anomalies
from tests.helpers import executar_pipeline_em_memoria, linha_processo

UNIDADES = {
    "1 VARA DO TRABALHO": "NEUTRA",
    "2 VARA DO TRABALHO": "NEUTRA",
    "3 VARA DO TRABALHO": "CEDENTE",
}


def test_ordenacao_e_campos_basicos():
    resultado = executar_pipeline_em_memoria([
        {"processo": "0000001-11.2026.5.12.0001", "indicador": "Distribuição", "unidade": "1 Vara do Trabalho", "data": "01/01/2026", "linha": 1},
        {"processo": "0000001-11.2026.5.12.0001", "indicador": "Redistribuição", "unidade": "2 Vara do Trabalho", "data": "05/01/2026", "linha": 2},
    ], UNIDADES)

    linha = linha_processo(resultado["processos_df"], "0000001-11.2026.5.12.0001")
    assert linha["quantidade_movimentos"] == 2
    assert linha["quantidade_redistribuicoes"] == 1
    assert linha["unidade_final_real"] == "2 VARA DO TRABALHO"
    assert linha["unidade_distribuicao_inicial"] == "1 VARA DO TRABALHO"


def test_primeiro_movimento_diferente_de_distribuicao():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P1", "indicador": "Redistribuição", "unidade": "1 Vara do Trabalho", "data": "01/01/2026"},
    ], UNIDADES)
    tipos = [a["tipo_anomalia"] for a in resultado["anomalias"]]
    assert anomalies.PRIMEIRO_MOVIMENTO_NAO_DISTRIBUICAO in tipos


def test_multipla_distribuicao_inicial():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P1", "indicador": "Distribuição", "unidade": "1 Vara do Trabalho", "data": "01/01/2026", "linha": 1},
        {"processo": "P1", "indicador": "Distribuição", "unidade": "2 Vara do Trabalho", "data": "02/01/2026", "linha": 2},
    ], UNIDADES)
    tipos = [a["tipo_anomalia"] for a in resultado["anomalias"]]
    assert anomalies.MULTIPLA_DISTRIBUICAO_INICIAL in tipos


def test_redistribuicao_anterior_a_distribuicao():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P1", "indicador": "Redistribuição", "unidade": "1 Vara do Trabalho", "data": "01/01/2026", "linha": 1},
        {"processo": "P1", "indicador": "Distribuição", "unidade": "2 Vara do Trabalho", "data": "05/01/2026", "linha": 2},
    ], UNIDADES)
    tipos = [a["tipo_anomalia"] for a in resultado["anomalias"]]
    assert anomalies.REDISTRIBUICAO_ANTERIOR_A_DISTRIBUICAO in tipos


def test_ordem_cronologica_ambigua():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P1", "indicador": "Distribuição", "unidade": "1 Vara do Trabalho", "data": "01/01/2026", "linha": 1},
        {"processo": "P1", "indicador": "Redistribuição", "unidade": "2 Vara do Trabalho", "data": "01/01/2026", "linha": 2},
    ], UNIDADES)
    tipos = [a["tipo_anomalia"] for a in resultado["anomalias"]]
    assert anomalies.ORDEM_CRONOLOGICA_AMBIGUA in tipos


def test_unidade_nao_classificada():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P1", "indicador": "Distribuição", "unidade": "Unidade Fantasma", "data": "01/01/2026"},
    ], UNIDADES)
    tipos = [a["tipo_anomalia"] for a in resultado["anomalias"]]
    assert anomalies.UNIDADE_NAO_CLASSIFICADA in tipos
