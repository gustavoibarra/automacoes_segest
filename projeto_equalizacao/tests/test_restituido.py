"""Movimentacoes com indicador 'Restituido Por Redistribuicao' devem ser
classificadas como RESTITUIDO, permanecer no historico completo (para
rastreabilidade), mas ser desconsideradas de toda e qualquer analise:
contagem de movimentos, resumo do processo, deteccao de equalizacao e
anomalias de ordem cronologica."""
import pandas as pd

from src import histories
from src.normalization import INDICADOR_RESTITUIDO, normalize_indicador
from tests.helpers import executar_pipeline_em_memoria, linha_processo

UNIDADES = {
    "UNIDADE A": "CEDENTE",
    "UNIDADE B": "DESTINATARIA",
}
TRIAGEM = "Setor de Triagem"


def test_normalize_indicador_classifica_restituido():
    assert normalize_indicador("Restituído Por Redistribuição") == INDICADOR_RESTITUIDO
    assert normalize_indicador("RESTITUIDO POR REDISTRIBUICAO") == INDICADOR_RESTITUIDO


def test_restituido_nao_conta_como_movimento_nem_redistribuicao():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P1", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026", "linha": 1},
        {"processo": "P1", "indicador": "Redistribuição", "unidade": "Unidade B", "data": "05/01/2026", "linha": 2},
        {"processo": "P1", "indicador": "Restituído Por Redistribuição", "unidade": "Unidade B", "data": "06/01/2026", "linha": 3},
    ], UNIDADES)

    linha = linha_processo(resultado["processos_df"], "P1")
    assert linha["quantidade_movimentos"] == 2
    assert linha["quantidade_redistribuicoes"] == 1

    # mas a movimentacao continua no historico completo, para rastreabilidade
    historico = resultado["historico_df"]
    restituidos = historico[historico["processo"] == "P1"]
    restituidos = restituidos[restituidos["indicador_norm"] == INDICADOR_RESTITUIDO]
    assert len(restituidos) == 1


def test_restituido_nao_participa_da_deteccao_de_equalizacao():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P2", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026", "linha": 1},
        {"processo": "P2", "indicador": "Restituído Por Redistribuição", "unidade": TRIAGEM, "data": "03/01/2026", "linha": 2},
        {"processo": "P2", "indicador": "Redistribuição", "unidade": TRIAGEM, "data": "05/01/2026", "linha": 3},
        {"processo": "P2", "indicador": "Redistribuição", "unidade": "Unidade B", "data": "10/01/2026", "linha": 4},
    ], UNIDADES)

    linha = linha_processo(resultado["processos_df"], "P2")
    assert linha["equalizacao_valida"] == True  # noqa: E712
    assert linha["quantidade_episodios_triagem"] == 1  # a passagem "restituida" nao vira um episodio


def test_processo_so_com_restituido_nao_aparece_nos_processos_mas_fica_no_historico():
    resultado = executar_pipeline_em_memoria([
        {"processo": "P3", "indicador": "Restituído Por Redistribuição", "unidade": "Unidade A", "data": "01/01/2026", "linha": 1},
    ], UNIDADES)

    assert len(resultado["processos_df"]) == 0
    historico = resultado["historico_df"]
    assert (historico["processo"] == "P3").any()
    assert (historico.loc[historico["processo"] == "P3", "indicador_norm"] == INDICADOR_RESTITUIDO).all()


def test_restituido_nao_gera_anomalia_de_ordem_ambigua():
    # Redistribuicao e Restituido na mesma data: sem a exclusao, isso geraria ORDEM_CRONOLOGICA_AMBIGUA
    resultado = executar_pipeline_em_memoria([
        {"processo": "P4", "indicador": "Distribuição", "unidade": "Unidade A", "data": "01/01/2026", "linha": 1},
        {"processo": "P4", "indicador": "Redistribuição", "unidade": "Unidade B", "data": "05/01/2026", "linha": 2},
        {"processo": "P4", "indicador": "Restituído Por Redistribuição", "unidade": "Unidade B", "data": "05/01/2026", "linha": 3},
    ], UNIDADES)

    from src import anomalies
    tipos = [a["tipo_anomalia"] for a in resultado["anomalias"]]
    assert anomalies.ORDEM_CRONOLOGICA_AMBIGUA not in tipos


def test_filtrar_para_analise_remove_apenas_restituido():
    historico = pd.DataFrame({
        "processo": ["P1", "P1", "P2"],
        "indicador_norm": ["DISTRIBUICAO", "RESTITUIDO", "REDISTRIBUICAO"],
    })
    filtrado = histories.filtrar_para_analise(historico)
    assert len(filtrado) == 2
    assert "RESTITUIDO" not in filtrado["indicador_norm"].tolist()
