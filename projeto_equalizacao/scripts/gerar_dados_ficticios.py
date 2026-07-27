"""Gera dados ficticios de teste/demonstracao para o Sistema de Equalizacao.

Uso:
    python scripts/gerar_dados_ficticios.py

Cria classificacao_unidades.xlsx e alguns arquivos processos_DD-MM-YYYY.csv
dentro de exemplos/dados_ficticios/ (NUNCA na raiz do projeto nem em
downloads/, que sao reservados para os dados reais), cobrindo os cenarios
de aceitacao descritos na secao 26 do prompt original, alem de casos comuns
(processos sem equalizacao, unidade nao classificada, data invalida).

Para experimentar com esses dados, aponte o main.py/app.py para essa pasta,
por exemplo:
    python main.py --downloads "./exemplos/dados_ficticios/downloads" \\
        --classificacao "./exemplos/dados_ficticios/classificacao_unidades.xlsx"
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
EXEMPLOS_DIR = BASE_DIR / "exemplos" / "dados_ficticios"

UNIDADES = [
    ("1 Vara do Trabalho de Florianopolis", "CEDENTE"),
    ("2 Vara do Trabalho de Florianopolis", "CEDENTE"),
    ("3 Vara do Trabalho de Florianopolis", "NEUTRA"),
    ("4 Vara do Trabalho de Florianopolis", "NEUTRA"),
    ("5 Vara do Trabalho de Florianopolis", "DESTINATARIA"),
    ("6 Vara do Trabalho de Florianopolis", "DESTINATARIA"),
    ("1 Vara do Trabalho de Itajai", "CEDENTE"),
    ("1 Vara do Trabalho de Joinville", "DESTINATARIA"),
    ("1 Vara do Trabalho de Blumenau", "NEUTRA"),
    ("1 Vara do Trabalho de Chapeco", "DESTINATARIA"),
]

TRIAGEM = "Setor de Triagem - Equalizacao"


def gerar_classificacao():
    EXEMPLOS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(UNIDADES, columns=["Unidade", "Classificacao"])
    caminho = EXEMPLOS_DIR / "classificacao_unidades.xlsx"
    df.to_excel(caminho, index=False)
    print(f"Gerado: {caminho}")


def _linha(processo, indicador, unidade, data, classe="ATSum - Procedimento Sumario", municipio="Florianopolis"):
    return {
        "#Processo": processo, "Indicador": indicador, "Município Sede": municipio,
        "Órgão Julgador": unidade, "Classe Judicial": classe, "Data": data,
    }


def gerar_csvs():
    linhas_arquivo1 = [
        # Processo sem equalizacao (permanece na 3 vara)
        _linha("0000001-11.2026.5.12.0001", "Distribuição", "3 Vara do Trabalho de Florianopolis", "02/01/2026"),

        # Equalizacao valida: 1 Vara (CEDENTE) -> Triagem -> 5 Vara (DESTINATARIA)
        _linha("0000002-22.2026.5.12.0001", "Distribuição", "1 Vara do Trabalho de Florianopolis", "02/01/2026"),
        _linha("0000002-22.2026.5.12.0001", "Redistribuição", TRIAGEM, "03/01/2026"),
        _linha("0000002-22.2026.5.12.0001", "Redistribuição", "5 Vara do Trabalho de Florianopolis", "05/01/2026"),

        # Equalizacao valida com movimentacao posterior (5 Vara -> 4 Vara, neutra)
        _linha("0000003-33.2026.5.12.0001", "Distribuição", "2 Vara do Trabalho de Florianopolis", "03/01/2026"),
        _linha("0000003-33.2026.5.12.0001", "Redistribuição", TRIAGEM, "04/01/2026"),
        _linha("0000003-33.2026.5.12.0001", "Redistribuição", "6 Vara do Trabalho de Florianopolis", "06/01/2026"),
        _linha("0000003-33.2026.5.12.0001", "Redistribuição", "4 Vara do Trabalho de Florianopolis", "20/01/2026"),

        # Passagem incompleta pela triagem (ainda esta la)
        _linha("0000004-44.2026.5.12.0001", "Distribuição", "1 Vara do Trabalho de Itajai", "05/01/2026"),
        _linha("0000004-44.2026.5.12.0001", "Redistribuição", TRIAGEM, "06/01/2026"),

        # Fluxo fora do padrao: origem NEUTRA (nao CEDENTE)
        _linha("0000005-55.2026.5.12.0001", "Distribuição", "3 Vara do Trabalho de Florianopolis", "05/01/2026"),
        _linha("0000005-55.2026.5.12.0001", "Redistribuição", TRIAGEM, "06/01/2026"),
        _linha("0000005-55.2026.5.12.0001", "Redistribuição", "6 Vara do Trabalho de Florianopolis", "08/01/2026"),

        # Unidade nao classificada
        _linha("0000006-66.2026.5.12.0001", "Distribuição", "Vara Inexistente", "06/01/2026"),

        # Data invalida
        _linha("0000007-77.2026.5.12.0001", "Distribuição", "1 Vara do Trabalho de Joinville", "31/13/2026"),

        # Duplicidade proposital (mesma linha aparece no arquivo 2)
        _linha("0000008-88.2026.5.12.0001", "Distribuição", "1 Vara do Trabalho de Blumenau", "07/01/2026"),

        # Multiplos episodios de triagem
        _linha("0000009-99.2026.5.12.0001", "Distribuição", "1 Vara do Trabalho de Florianopolis", "02/01/2026"),
        _linha("0000009-99.2026.5.12.0001", "Redistribuição", TRIAGEM, "03/01/2026"),
        _linha("0000009-99.2026.5.12.0001", "Redistribuição", "5 Vara do Trabalho de Florianopolis", "04/01/2026"),
        _linha("0000009-99.2026.5.12.0001", "Redistribuição", TRIAGEM, "10/01/2026"),
        _linha("0000009-99.2026.5.12.0001", "Redistribuição", "1 Vara do Trabalho de Chapeco", "12/01/2026"),
    ]

    linhas_arquivo2 = [
        # Duplicidade da linha do processo 8 (mesmo processo/indicador/orgao/data/classe/municipio)
        _linha("0000008-88.2026.5.12.0001", "Distribuição", "1 Vara do Trabalho de Blumenau", "07/01/2026"),

        # Novo caso na segunda semana
        _linha("0000010-10.2026.5.12.0001", "Distribuição", "2 Vara do Trabalho de Florianopolis", "09/01/2026"),
        _linha("0000010-10.2026.5.12.0001", "Redistribuição", TRIAGEM, "10/01/2026"),
        _linha("0000010-10.2026.5.12.0001", "Redistribuição", "1 Vara do Trabalho de Joinville", "13/01/2026"),

        _linha("0000011-20.2026.5.12.0001", "Distribuição", "4 Vara do Trabalho de Florianopolis", "09/01/2026"),
        _linha("0000012-30.2026.5.12.0001", "Distribuição", "1 Vara do Trabalho de Itajai", "10/01/2026"),
        _linha("0000012-30.2026.5.12.0001", "Redistribuição", TRIAGEM, "11/01/2026"),
        _linha("0000012-30.2026.5.12.0001", "Redistribuição", "1 Vara do Trabalho de Chapeco", "14/01/2026"),
    ]

    downloads = EXEMPLOS_DIR / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)

    caminho1 = downloads / "processos_01-01-2026.csv"
    caminho2 = downloads / "processos_08-01-2026.csv"

    _escrever_csv_com_resumo(caminho1, pd.DataFrame(linhas_arquivo1), "01/01/2026", "07/01/2026")
    _escrever_csv_com_resumo(caminho2, pd.DataFrame(linhas_arquivo2), "08/01/2026", "14/01/2026")
    print(f"Gerado: {caminho1}")
    print(f"Gerado: {caminho2}")


def _escrever_csv_com_resumo(caminho: Path, df: pd.DataFrame, data_inicial: str, data_final: str) -> None:
    """Escreve o CSV reproduzindo o formato real das exportacoes do Sistema
    de Equalizacao: linhas de resumo (tambem iniciadas por '#') antes do
    cabecalho das colunas, separador ';' e a coluna Data com data e hora.
    O loader (src/loaders.py) descarta tudo antes da linha cujo primeiro
    campo e exatamente '#Processo' e detecta o separador automaticamente."""
    linhas_resumo = [
        "#Processos distribuidos e redistribuidos por OJ no 1o grau  detalhado",
        f"#Data Final: {data_final}; Indicador de Distribuicao: NAO PREENCHIDO; "
        f"Orgao Julgador: NAO PREENCHIDO; Municipio: NAO PREENCHIDO; Data Inicial: {data_inicial}; "
        "Classe Processual: NAO PREENCHIDO",
        "",
        f"#Total de registros: {len(df)}",
        "#Relatorio gerado automaticamente (dados ficticios de demonstracao)",
        "",
    ]
    df = df.copy()
    df["Data"] = df["Data"] + " 08:00:00"
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        for linha in linhas_resumo:
            f.write(linha + "\n")
        df.to_csv(f, index=False, sep=";")


if __name__ == "__main__":
    gerar_classificacao()
    gerar_csvs()
