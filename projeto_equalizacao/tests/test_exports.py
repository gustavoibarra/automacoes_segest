"""Testa a exportacao da base consolidada em Excel (varias abas)."""
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
import pandas as pd

from src import exports


@dataclass
class _SettingsFake:
    output_dir: Path
    arquivos_saida: dict = field(default_factory=lambda: {"consolidado_excel": "consolidado_equalizacao.xlsx"})

    def saida(self, chave: str) -> Path:
        return self.output_dir / self.arquivos_saida[chave]


def test_gera_planilha_excel_com_todas_as_abas(tmp_path):
    settings = _SettingsFake(output_dir=tmp_path)

    movimentos_df = pd.DataFrame({"processo": ["P1"], "orgao_norm": ["1 VARA"], "data_dt": [pd.Timestamp("2026-01-01")]})
    processos_df = pd.DataFrame({"processo": ["P1"], "equalizacao_valida": [False]})
    episodios_df = pd.DataFrame(columns=["processo", "tipo_episodio"])
    comparativo_df = pd.DataFrame({"unidade_norm": ["1 VARA"], "quantidade": [1], "cenario": ["COM_EQUALIZACAO"]})
    fluxos_df = pd.DataFrame(columns=["unidade_cedente", "unidade_destinataria", "quantidade"])
    anomalias_df = pd.DataFrame(columns=["processo", "tipo_anomalia"])
    nao_classificadas_df = pd.DataFrame(columns=["unidade", "quantidade_movimentos"])

    caminho = exports.escrever_excel_consolidado(
        settings, movimentos_df, processos_df, episodios_df, comparativo_df, fluxos_df,
        anomalias_df, nao_classificadas_df,
        qualidade={"quantidade_registros_lidos": 1, "processos_distintos": 1, "data_minima": None, "data_maxima": None},
        avisos=["aviso de teste"], arquivos_utilizados=["processos_01-01-2026.csv"],
    )

    assert caminho.exists()
    workbook = openpyxl.load_workbook(caminho)
    assert set(workbook.sheetnames) == {
        "Resumo", "Processos", "Movimentacoes", "Episodios_Equalizacao", "Comparativo_Unidades",
        "Fluxos_Equalizacao", "Anomalias", "Unidades_Nao_Classificadas",
    }

    processos_sheet = workbook["Processos"]
    assert processos_sheet["A1"].value == "processo"
    assert processos_sheet["A1"].font.bold is True
    assert processos_sheet.freeze_panes == "A2"
    assert processos_sheet["A2"].value == "P1"
