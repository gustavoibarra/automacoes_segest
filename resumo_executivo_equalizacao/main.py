"""Gera o Resumo Executivo do Sistema de Equalizacao TRT12 em DOCX, a
partir de um arquivo consolidado (padrao: consolidado_equalizacao.xlsx
gerado por projeto_equalizacao).

Uso:
    python main.py
    python main.py --arquivo "./outro_consolidado.xlsx"
    python main.py --inicio 01/07/2026 --fim 29/07/2026
    python main.py --saida "./output/meu_relatorio.docx"
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import CONSOLIDADO_PADRAO, OUTPUT_DIR
from src.dados import DadosError
from src.relatorio import gerar_relatorio


def _parse_data(texto: str | None) -> pd.Timestamp | None:
    if not texto:
        return None
    return pd.to_datetime(texto, dayfirst=True)


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera o Resumo Executivo do Sistema de Equalizacao TRT12 (DOCX) a partir do consolidado."
    )
    parser.add_argument("--arquivo", type=str, default=None,
                         help=f"Caminho do consolidado_equalizacao.xlsx (padrao: {CONSOLIDADO_PADRAO})")
    parser.add_argument("--inicio", type=str, default=None, help="Data inicial do periodo, DD/MM/AAAA (padrao: primeira data disponivel)")
    parser.add_argument("--fim", type=str, default=None, help="Data final do periodo, DD/MM/AAAA (padrao: ultima data disponivel)")
    parser.add_argument("--saida", type=str, default=None, help="Caminho do DOCX de saida (padrao: output/Resumo_Executivo_Equalizacao_<periodo>.docx)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)

    caminho_arquivo = Path(args.arquivo) if args.arquivo else CONSOLIDADO_PADRAO
    inicio = _parse_data(args.inicio)
    fim = _parse_data(args.fim)

    try:
        if args.saida:
            caminho_saida = Path(args.saida)
            resultado = gerar_relatorio(caminho_arquivo, caminho_saida, inicio=inicio, fim=fim)
        else:
            # Nome de saida definitivo depende do periodo resolvido (so conhecido apos ler o
            # arquivo); gera primeiro num nome provisorio e renomeia ao final.
            provisorio = OUTPUT_DIR / "_resumo_executivo_tmp.docx"
            resultado = gerar_relatorio(caminho_arquivo, provisorio, inicio=inicio, fim=fim)
            from src import dados
            base = dados.carregar_consolidado(caminho_arquivo)
            periodo_inicio, periodo_fim = dados.resolver_periodo(base["processos"], inicio, fim)
            nome_final = (
                f"Resumo_Executivo_Equalizacao_{periodo_inicio.strftime('%d-%m-%Y')}"
                f"_a_{periodo_fim.strftime('%d-%m-%Y')}.docx"
            )
            caminho_saida = OUTPUT_DIR / nome_final
            resultado.replace(caminho_saida)
    except DadosError as erro:
        print(f"[ERRO] {erro}", file=sys.stderr)
        return 1

    print(f"Resumo executivo gerado em: {caminho_saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
