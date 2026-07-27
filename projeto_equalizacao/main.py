"""Ponto de entrada de linha de comando (secao 25 do prompt).

Uso:
    python main.py
    python main.py --downloads "./downloads" --classificacao "./classificacao_unidades.xls" --output "./output"
    python main.py --relatorio
    python main.py --atualizar
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from config import SETTINGS
from src import filters, metrics, reports
from src.loaders import ConfigError
from src.pipeline import executar_pipeline


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consolidacao e analise do Sistema de Equalizacao TRT12")
    parser.add_argument("--downloads", type=str, default=None, help="Pasta com os arquivos CSV de processos")
    parser.add_argument("--classificacao", type=str, default=None, help="Caminho do arquivo de classificacao de unidades")
    parser.add_argument("--output", type=str, default=None, help="Pasta de saida")
    parser.add_argument("--atualizar", action="store_true", help="Forca o reprocessamento ignorando o cache")
    parser.add_argument("--relatorio", action="store_true", help="Gera tambem o relatorio gerencial em DOCX")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)

    settings = SETTINGS
    if args.downloads:
        settings.downloads_dir = Path(args.downloads)
    if args.output:
        settings.output_dir = Path(args.output)
    classificacao_path = Path(args.classificacao) if args.classificacao else None

    try:
        resultado = executar_pipeline(
            settings, classificacao_path=classificacao_path, forcar_atualizacao=args.atualizar
        )
    except ConfigError as erro:
        print(f"[ERRO] {erro}", file=sys.stderr)
        return 1

    print(f"Processamento concluido ({'cache reutilizado' if resultado['usou_cache'] else 'reprocessado'}).")
    print(f"Arquivos utilizados: {len(resultado['arquivos_utilizados'])}")
    print(f"Processos distintos: {resultado['qualidade']['processos_distintos']}")
    print(f"Planilha Excel consolidada: {resultado['excel_consolidado']}")
    for aviso in resultado["avisos"]:
        print(f"[AVISO] {aviso}")

    if args.relatorio:
        processos_df = resultado["processos_df"]
        unidades_df = resultado["unidades_permanentes_df"]
        filtros_padrao = filters.FiltrosDashboard()
        processos_filtrados, unidades_filtradas = filters.aplicar_filtros(processos_df, unidades_df, filtros_padrao)
        metricas = metrics.calcular_todas_metricas(
            processos_filtrados, unidades_filtradas, resultado["episodios_df"], filtros_padrao
        )
        caminho = reports.gerar_relatorio_docx(
            settings.saida("relatorio_docx"),
            filtros=filtros_padrao,
            metricas=metricas,
            processos_filtrados=processos_filtrados,
            unidades_filtradas=unidades_filtradas,
            arquivos_utilizados=resultado["arquivos_utilizados"],
            qualidade=resultado["qualidade"],
            anomalias_df=resultado["anomalias_df"],
            periodo_texto="Todo o periodo disponivel",
            filtros_texto="Nenhum (relatorio padrao via linha de comando)",
            data_geracao=datetime.now(),
        )
        print(f"Relatorio gerado em: {caminho}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
