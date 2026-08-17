"""Fixtures em memoria das 3 abas do consolidado, usadas pelos testes."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def processos_fixture() -> pd.DataFrame:
    return pd.DataFrame([
        # equalizado: A (cedente) -> B (destinataria)
        {"processo_norm": "P1", "data_caso_novo": "2026-07-02", "data_ultimo_movimento": "2026-07-10",
         "unidade_distribuicao_inicial": "UNIDADE A", "unidade_final_real": "UNIDADE B",
         "unidade_simulada_sem_equalizacao": "UNIDADE A", "unidade_cedente_equalizacao": "UNIDADE A",
         "unidade_destinataria_equalizacao": "UNIDADE B", "equalizacao_valida": True},
        # nao equalizado, fica na origem
        {"processo_norm": "P2", "data_caso_novo": "2026-07-03", "data_ultimo_movimento": "2026-07-03",
         "unidade_distribuicao_inicial": "UNIDADE A", "unidade_final_real": "UNIDADE A",
         "unidade_simulada_sem_equalizacao": "UNIDADE A", "unidade_cedente_equalizacao": "",
         "unidade_destinataria_equalizacao": "", "equalizacao_valida": False},
        # processo antigo (caso novo fora do periodo), mas com redistribuicao dentro do periodo
        {"processo_norm": "P3", "data_caso_novo": "2026-06-15", "data_ultimo_movimento": "2026-07-05",
         "unidade_distribuicao_inicial": "UNIDADE A", "unidade_final_real": "UNIDADE B",
         "unidade_simulada_sem_equalizacao": "UNIDADE A", "unidade_cedente_equalizacao": "UNIDADE A",
         "unidade_destinataria_equalizacao": "UNIDADE B", "equalizacao_valida": True},
        # unidade neutra
        {"processo_norm": "P4", "data_caso_novo": "2026-07-04", "data_ultimo_movimento": "2026-07-04",
         "unidade_distribuicao_inicial": "UNIDADE C", "unidade_final_real": "UNIDADE C",
         "unidade_simulada_sem_equalizacao": "UNIDADE C", "unidade_cedente_equalizacao": "",
         "unidade_destinataria_equalizacao": "", "equalizacao_valida": False},
    ])


def movimentacoes_fixture() -> pd.DataFrame:
    return pd.DataFrame([
        {"processo_norm": "P1", "data_dt": "2026-07-02", "indicador_norm": "DISTRIBUICAO"},
        {"processo_norm": "P1", "data_dt": "2026-07-05", "indicador_norm": "REDISTRIBUICAO"},
        {"processo_norm": "P1", "data_dt": "2026-07-10", "indicador_norm": "REDISTRIBUICAO"},
        {"processo_norm": "P2", "data_dt": "2026-07-03", "indicador_norm": "DISTRIBUICAO"},
        # P3: distribuicao ANTES do periodo (junho), redistribuicoes DENTRO do periodo (julho)
        {"processo_norm": "P3", "data_dt": "2026-06-15", "indicador_norm": "DISTRIBUICAO"},
        {"processo_norm": "P3", "data_dt": "2026-07-01", "indicador_norm": "REDISTRIBUICAO"},
        {"processo_norm": "P3", "data_dt": "2026-07-05", "indicador_norm": "REDISTRIBUICAO"},
        {"processo_norm": "P4", "data_dt": "2026-07-04", "indicador_norm": "DISTRIBUICAO"},
        # movimentacao RESTITUIDO dentro do periodo para um processo que NAO tem outra movimentacao no periodo
        {"processo_norm": "P5", "data_dt": "2026-07-08", "indicador_norm": "RESTITUIDO"},
    ])


def comparativo_unidades_fixture() -> pd.DataFrame:
    linhas = []
    unidades = [
        ("UNIDADE A", "Unidade A", "CEDENTE", 2),
        ("UNIDADE B", "Unidade B", "DESTINATARIA", 1),
        ("UNIDADE C", "Unidade C", "NEUTRA", 2),
    ]
    for norm, original, classif, mag in unidades:
        for cenario in ("COM_EQUALIZACAO", "SEM_EQUALIZACAO"):
            linhas.append({
                "unidade_norm": norm, "unidade_original": original, "classificacao": classif,
                "quantidade_magistrados": mag, "cenario": cenario, "quantidade": 0,
            })
    return pd.DataFrame(linhas)


def escrever_consolidado_fixture(caminho: Path) -> Path:
    with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
        processos_fixture().to_excel(writer, sheet_name="Processos", index=False)
        movimentacoes_fixture().to_excel(writer, sheet_name="Movimentacoes", index=False)
        comparativo_unidades_fixture().to_excel(writer, sheet_name="Comparativo_Unidades", index=False)
    return caminho
