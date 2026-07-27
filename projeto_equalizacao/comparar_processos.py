"""Compara a base consolidada do Sistema de Equalizacao com uma relacao de
processos do log do sistema (arquivo externo), indicando:

- quais processos do log NAO aparecem em lugar nenhum da base consolidada;
- para os que aparecem, quais situacoes os levaram a nao ser considerados
  equalizados (quando for o caso).

Uso:
    python comparar_processos.py --log "./caminho/log_processos.xlsx"

Parametros opcionais:
    --consolidado "./output/consolidado_equalizacao.xlsx"   (padrao)
    --saida "./output/comparacao_log_equalizacao.xlsx"      (padrao)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from config import SETTINGS
from src import comparacao
from src.xlsx_utils import formatar_planilha


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compara o log de processos do Sistema de Equalizacao com a base consolidada."
    )
    parser.add_argument("--log", type=str, required=True,
                         help="Caminho do arquivo XLS/XLSX com a relacao de processos do log")
    parser.add_argument("--consolidado", type=str, default=None,
                         help="Caminho do consolidado_equalizacao.xlsx (padrao: output/consolidado_equalizacao.xlsx)")
    parser.add_argument("--saida", type=str, default=None,
                         help="Caminho do relatorio de comparacao a ser gerado (padrao: output/comparacao_log_equalizacao.xlsx)")
    return parser.parse_args(argv)


def gerar_relatorio_comparacao(caminho_saida: Path, resultado: dict) -> Path:
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    planilhas = {
        "Resumo": resultado["resumo"],
        "Nao_Encontrados": resultado["nao_encontrados"],
        "Encontrados_Nao_Equalizados": resultado["encontrados_nao_equalizados"],
        "Encontrados_Equalizados": resultado["encontrados_equalizados"],
        "Todos": resultado["tabela_completa"],
    }
    with pd.ExcelWriter(caminho_saida, engine="openpyxl") as writer:
        for nome_aba, df in planilhas.items():
            df.to_excel(writer, sheet_name=nome_aba, index=False)
            formatar_planilha(writer.sheets[nome_aba], df)
    return caminho_saida


def main(argv=None) -> int:
    args = _parse_args(argv)

    caminho_consolidado = Path(args.consolidado) if args.consolidado else SETTINGS.saida("consolidado_excel")
    caminho_log = Path(args.log)
    caminho_saida = Path(args.saida) if args.saida else SETTINGS.output_dir / "comparacao_log_equalizacao.xlsx"

    try:
        processos_df, anomalias_df = comparacao.carregar_consolidado(caminho_consolidado)
        log_df = comparacao.carregar_log_processos(caminho_log)
    except comparacao.ComparacaoError as erro:
        print(f"[ERRO] {erro}", file=sys.stderr)
        return 1

    resultado = comparacao.comparar(processos_df, anomalias_df, log_df)
    caminho = gerar_relatorio_comparacao(caminho_saida, resultado)

    print("Comparacao concluida.")
    for _, linha in resultado["resumo"].iterrows():
        print(f"  {linha['indicador']}: {linha['valor']}")
    print(f"Relatorio gerado em: {caminho}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
