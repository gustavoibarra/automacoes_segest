"""Testes de aceitacao obrigatorios 1 a 6 (secao 26 do prompt)."""
from tests.helpers import executar_pipeline_em_memoria, linha_processo

UNIDADES = {
    "UNIDADE A": "CEDENTE",
    "UNIDADE B": "DESTINATARIA",
    "UNIDADE C": "NEUTRA",
}
TRIAGEM = "Setor de Triagem"


def test_cenario1_processo_sem_equalizacao():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P1", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026"},
    ], UNIDADES)
    linha = linha_processo(resultado["processos_df"], "P1")
    assert linha["equalizacao_valida"] == False
    assert linha["equalizacao_detectada"] == False
    assert linha["unidade_final_real"] == "UNIDADE A"
    assert linha["unidade_simulada_sem_equalizacao"] == "UNIDADE A"


def test_cenario2_equalizacao_valida():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P2", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026", "linha": 1},
        {"processo": "P2", "indicador": "Redistribuição", "unidade": TRIAGEM, "data": "05/01/2026", "linha": 2},
        {"processo": "P2", "indicador": "Redistribuição", "unidade": "Unidade B", "data": "10/01/2026", "linha": 3},
    ], UNIDADES)
    linha = linha_processo(resultado["processos_df"], "P2")
    assert linha["equalizacao_valida"] == True
    assert linha["unidade_final_real"] == "UNIDADE B"
    assert linha["unidade_simulada_sem_equalizacao"] == "UNIDADE A"
    assert linha["unidade_cedente_equalizacao"] == "UNIDADE A"
    assert linha["unidade_destinataria_equalizacao"] == "UNIDADE B"


def test_cenario3_movimentacao_posterior():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P3", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026", "linha": 1},
        {"processo": "P3", "indicador": "Redistribuição", "unidade": TRIAGEM, "data": "05/01/2026", "linha": 2},
        {"processo": "P3", "indicador": "Redistribuição", "unidade": "Unidade B", "data": "10/01/2026", "linha": 3},
        {"processo": "P3", "indicador": "Redistribuição", "unidade": "Unidade C", "data": "20/01/2026", "linha": 4},
    ], UNIDADES)
    linha = linha_processo(resultado["processos_df"], "P3")
    assert linha["equalizacao_valida"] == True
    assert linha["unidade_cedente_equalizacao"] == "UNIDADE A"
    assert linha["unidade_destinataria_equalizacao"] == "UNIDADE B"
    assert linha["unidade_final_real"] == "UNIDADE C"
    assert linha["unidade_simulada_sem_equalizacao"] == "UNIDADE A"


def test_cenario4_triagem_incompleta():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P4", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026", "linha": 1},
        {"processo": "P4", "indicador": "Redistribuição", "unidade": TRIAGEM, "data": "05/01/2026", "linha": 2},
    ], UNIDADES)
    linha = linha_processo(resultado["processos_df"], "P4")
    assert linha["equalizacao_valida"] == False
    assert linha["equalizacao_detectada"] == False

    episodios = resultado["episodios_df"]
    episodio_p4 = episodios[episodios["processo"] == "P4"].iloc[0]
    assert episodio_p4["tipo_episodio"] == "INCOMPLETA"

    tipos_anomalia = [a["tipo_anomalia"] for a in resultado["anomalias"]]
    from src import anomalies
    assert anomalies.PASSAGEM_TRIAGEM_INCOMPLETA in tipos_anomalia
    assert anomalies.ULTIMO_MOVIMENTO_EM_TRIAGEM in tipos_anomalia


def test_cenario5_fluxo_fora_do_padrao():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P5", "indicador": "Distribuição", "unidade": "Unidade C", "data": "01/01/2026", "linha": 1},
        {"processo": "P5", "indicador": "Redistribuição", "unidade": TRIAGEM, "data": "05/01/2026", "linha": 2},
        {"processo": "P5", "indicador": "Redistribuição", "unidade": "Unidade B", "data": "10/01/2026", "linha": 3},
    ], UNIDADES)
    linha = linha_processo(resultado["processos_df"], "P5")
    assert linha["equalizacao_detectada"] == True
    assert linha["equalizacao_valida"] == False
    assert "nao classificada como CEDENTE" in linha["motivo_invalidade_equalizacao"] or \
           "NEUTRA" in linha["motivo_invalidade_equalizacao"]


def test_cenario6_duplicidade():
    linhas = [
        {"processo": "P6", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026",
         "arquivo": "processos_01-01-2026.csv", "linha": 1},
        {"processo": "P6", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026",
         "arquivo": "processos_02-01-2026.csv", "data_arquivo": "02-01-2026", "linha": 1},
    ]
    resultado = executar_pipeline_em_memoria(linhas, UNIDADES)
    linha = linha_processo(resultado["processos_df"], "P6")
    assert linha["quantidade_movimentos"] == 1

    from src import anomalies
    tipos = [a["tipo_anomalia"] for a in resultado["anomalias"]]
    assert anomalies.MOVIMENTACAO_DUPLICADA_REMOVIDA in tipos
    assert resultado["processos_df"]["processo_norm"].nunique() == 1
