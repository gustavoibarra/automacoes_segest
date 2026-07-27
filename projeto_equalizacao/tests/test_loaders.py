"""Testa a leitura de CSVs cujas primeiras linhas contem um resumo do
arquivo (sem valor para a consolidacao), com o cabecalho das colunas
comecando somente na linha em que a primeira celula e '#Processo'."""
from datetime import datetime

import pytest

from src.loaders import ArquivoCsvInfo, ConfigError, carregar_csv_movimentos


def _escrever_csv(caminho, linhas_resumo, linhas_dados):
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        for linha in linhas_resumo:
            f.write(linha + "\n")
        for linha in linhas_dados:
            f.write(linha + "\n")


def test_ignora_linhas_de_resumo_antes_do_cabecalho(tmp_path):
    caminho = tmp_path / "processos_01-01-2026.csv"
    linhas_resumo = [
        "Relatorio de Distribuicao e Redistribuicao de Processos",
        "Sistema de Equalizacao TRT12",
        "Periodo: 01/01/2026 a 07/01/2026",
        "Total de registros: 2",
        "",
    ]
    linhas_dados = [
        "#Processo,Indicador,Município Sede,Órgão Julgador,Classe Judicial,Data",
        "0000001-11.2026.5.12.0001,Distribuição,Florianopolis,1 Vara do Trabalho,ATSum,01/01/2026",
        "0000002-22.2026.5.12.0001,Distribuição,Florianopolis,2 Vara do Trabalho,ATSum,02/01/2026",
    ]
    _escrever_csv(caminho, linhas_resumo, linhas_dados)

    info = ArquivoCsvInfo(caminho=caminho, data_arquivo=datetime(2026, 1, 1), ordem_arquivo=0)
    df = carregar_csv_movimentos(info)

    assert list(df.columns[:6]) == [
        "#Processo", "Indicador", "Município Sede", "Órgão Julgador", "Classe Judicial", "Data",
    ]
    assert len(df) == 2
    assert df.iloc[0]["#Processo"] == "0000001-11.2026.5.12.0001"
    # cabecalho esta na linha 6 (1-based); primeira linha de dado e a linha 7
    assert df.iloc[0]["numero_linha_arquivo"] == 7
    assert df.iloc[1]["numero_linha_arquivo"] == 8


def test_processo_com_zeros_a_esquerda_preservado(tmp_path):
    caminho = tmp_path / "processos_01-01-2026.csv"
    linhas_resumo = ["resumo linha 1", "resumo linha 2", "resumo linha 3", "resumo linha 4", "resumo linha 5", ""]
    linhas_dados = [
        "#Processo,Indicador,Município Sede,Órgão Julgador,Classe Judicial,Data",
        "0000009-99.2026.5.12.0001,Distribuição,Florianopolis,1 Vara do Trabalho,ATSum,01/01/2026",
    ]
    _escrever_csv(caminho, linhas_resumo, linhas_dados)

    info = ArquivoCsvInfo(caminho=caminho, data_arquivo=datetime(2026, 1, 1), ordem_arquivo=0)
    df = carregar_csv_movimentos(info)
    assert df.iloc[0]["#Processo"] == "0000009-99.2026.5.12.0001"


def test_erro_quando_cabecalho_nao_encontrado(tmp_path):
    caminho = tmp_path / "processos_01-01-2026.csv"
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("isso nao e um arquivo valido\nsem cabecalho de processo\n")

    info = ArquivoCsvInfo(caminho=caminho, data_arquivo=datetime(2026, 1, 1), ordem_arquivo=0)
    with pytest.raises(ConfigError):
        carregar_csv_movimentos(info)
