"""Testes do modulo de comparacao entre o log de processos e a base
consolidada (comparar_processos.py / src/comparacao.py)."""
import pandas as pd
import pytest

from src import comparacao


def _processos_df():
    return pd.DataFrame([
        {
            "processo": "0000001-11.2026.5.12.0001", "processo_norm": "0000001-11.2026.5.12.0001",
            "data_caso_novo": pd.Timestamp("2026-01-01"), "unidade_distribuicao_inicial_original": "1 VARA",
            "unidade_final_real_original": "5 VARA", "data_ultimo_movimento": pd.Timestamp("2026-01-10"),
            "classe_judicial": "ATSUM", "quantidade_movimentos": 3, "quantidade_redistribuicoes": 2,
            "passou_por_triagem": True, "equalizacao_detectada": True, "equalizacao_valida": True,
            "quantidade_episodios_triagem": 1, "unidade_cedente_equalizacao_original": "1 VARA",
            "unidade_destinataria_equalizacao_original": "5 VARA", "motivo_invalidade_equalizacao": "",
            "unidade_simulada_sem_equalizacao_original": "1 VARA", "tem_anomalia": False,
        },
        {
            "processo": "0000002-22.2026.5.12.0001", "processo_norm": "0000002-22.2026.5.12.0001",
            "data_caso_novo": pd.Timestamp("2026-01-01"), "unidade_distribuicao_inicial_original": "3 VARA",
            "unidade_final_real_original": "3 VARA", "data_ultimo_movimento": pd.Timestamp("2026-01-05"),
            "classe_judicial": "ATSUM", "quantidade_movimentos": 2, "quantidade_redistribuicoes": 1,
            "passou_por_triagem": True, "equalizacao_detectada": True, "equalizacao_valida": False,
            "quantidade_episodios_triagem": 1, "unidade_cedente_equalizacao_original": "3 VARA",
            "unidade_destinataria_equalizacao_original": "",
            "motivo_invalidade_equalizacao": "Nao ha unidade permanente definitiva apos a triagem",
            "unidade_simulada_sem_equalizacao_original": "3 VARA", "tem_anomalia": True,
        },
    ])


def _anomalias_df():
    df = pd.DataFrame([
        {"processo": "0000002-22.2026.5.12.0001", "tipo_anomalia": "PASSAGEM_TRIAGEM_INCOMPLETA",
         "descricao": "x", "arquivo_origem": "a.csv", "numero_linha_arquivo": 1},
        {"processo": "0000002-22.2026.5.12.0001", "tipo_anomalia": "ULTIMO_MOVIMENTO_EM_TRIAGEM",
         "descricao": "y", "arquivo_origem": "a.csv", "numero_linha_arquivo": 1},
    ])
    df["processo_norm"] = df["processo"]
    return df


def _log_df(processos: list[str]):
    return pd.DataFrame({
        "Processo": processos,
        "Unidade de Origem": ["1 VARA"] * len(processos),
        "Situação": ["Pendente"] * len(processos),
        "Fase": ["Triagem"] * len(processos),
        "Observação": [""] * len(processos),
        "Ocorrências Triagem": [0] * len(processos),
        "Erros Triagem": [0] * len(processos),
        "Ocorrências Territorial": [0] * len(processos),
        "Erros Territorial": [0] * len(processos),
        "processo_norm": [comparacao._processo_norm(p) for p in processos],
    })


def test_processo_encontrado_e_equalizado_validamente():
    resultado = comparacao.comparar(_processos_df(), _anomalias_df(), _log_df(["0000001-11.2026.5.12.0001"]))
    assert len(resultado["encontrados_equalizados"]) == 1
    assert len(resultado["encontrados_nao_equalizados"]) == 0
    assert len(resultado["nao_encontrados"]) == 0


def test_processo_encontrado_mas_nao_equalizado_traz_motivo_e_anomalias():
    resultado = comparacao.comparar(_processos_df(), _anomalias_df(), _log_df(["0000002-22.2026.5.12.0001"]))
    assert len(resultado["encontrados_nao_equalizados"]) == 1
    linha = resultado["encontrados_nao_equalizados"].iloc[0]
    assert linha["situacao_calculada"] == "INCOMPLETA"
    assert "PASSAGEM_TRIAGEM_INCOMPLETA" in linha["anomalias_encontradas"]
    assert "ULTIMO_MOVIMENTO_EM_TRIAGEM" in linha["anomalias_encontradas"]


def test_processo_nao_encontrado_na_base():
    resultado = comparacao.comparar(_processos_df(), _anomalias_df(), _log_df(["9999999-99.2026.5.12.9999"]))
    assert len(resultado["nao_encontrados"]) == 1
    assert resultado["nao_encontrados"].iloc[0]["situacao_calculada"] == comparacao.SITUACAO_PROCESSO_NAO_ENCONTRADO


def test_resumo_contadores():
    log = _log_df([
        "0000001-11.2026.5.12.0001", "0000002-22.2026.5.12.0001", "9999999-99.2026.5.12.9999",
    ])
    resultado = comparacao.comparar(_processos_df(), _anomalias_df(), log)
    resumo = {r["indicador"]: r["valor"] for _, r in resultado["resumo"].iterrows()}
    assert resumo["Processos no arquivo de log"] == 3
    assert resumo["Nao encontrados na base consolidada"] == 1
    assert resumo["Encontrados na base, mas nao equalizados validamente"] == 1
    assert resumo["Encontrados na base e equalizados validamente"] == 1


def test_carregar_log_processos_tolera_variacao_de_coluna(tmp_path):
    df = pd.DataFrame({
        "Processo": ["0000001-11.2026.5.12.0001"],
        "Unidade de Origem": ["1 VARA"],
        "Situacao": ["Pendente"],  # sem acento
        "Fase": ["Triagem"],
        "Observacao": [""],  # sem acento
        "Ocorrencias Triagem": [0],
        "Erros Triagem": [0],
        "Ocorrencias Territorial": [0],
        "Erros Territorial": [0],
    })
    caminho = tmp_path / "log.xlsx"
    df.to_excel(caminho, index=False)

    log_df = comparacao.carregar_log_processos(caminho)
    assert "Situação" in log_df.columns
    assert "Observação" in log_df.columns
    assert log_df.iloc[0]["processo_norm"] == "0000001-11.2026.5.12.0001"


def test_carregar_log_processos_erro_quando_coluna_faltando(tmp_path):
    df = pd.DataFrame({"Processo": ["123"], "Fase": ["Triagem"]})
    caminho = tmp_path / "log_incompleto.xlsx"
    df.to_excel(caminho, index=False)

    with pytest.raises(comparacao.ComparacaoError):
        comparacao.carregar_log_processos(caminho)


def test_carregar_consolidado_erro_quando_arquivo_nao_existe(tmp_path):
    with pytest.raises(comparacao.ComparacaoError):
        comparacao.carregar_consolidado(tmp_path / "nao_existe.xlsx")
