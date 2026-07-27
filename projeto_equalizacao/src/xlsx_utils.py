"""Utilitarios compartilhados para geracao de planilhas Excel (usado por
src/exports.py e src/comparacao.py)."""
from __future__ import annotations

import pandas as pd
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

LARGURA_COLUNA_MINIMA = 10
LARGURA_COLUNA_MAXIMA = 60


def formatar_planilha(worksheet, df: pd.DataFrame) -> None:
    """Aplica formatacao basica para facilitar a analise em Excel:
    cabecalho em negrito, primeira linha congelada, autofiltro e largura
    de coluna ajustada ao conteudo."""
    if df.empty and len(df.columns) == 0:
        return

    for celula in worksheet[1]:
        celula.font = Font(bold=True)
    worksheet.freeze_panes = "A2"
    if len(df.columns) > 0 and len(df) > 0:
        worksheet.auto_filter.ref = worksheet.dimensions

    for indice, coluna in enumerate(df.columns, start=1):
        try:
            maior_valor = df[coluna].astype(str).map(len).max()
        except (TypeError, ValueError):
            maior_valor = 0
        largura = max(
            LARGURA_COLUNA_MINIMA,
            min(LARGURA_COLUNA_MAXIMA, len(str(coluna)) + 2, maior_valor + 2 if pd.notna(maior_valor) else LARGURA_COLUNA_MINIMA),
        )
        worksheet.column_dimensions[get_column_letter(indice)].width = largura


def remover_timezone(df: pd.DataFrame) -> pd.DataFrame:
    """Remove timezone de colunas datetime (Excel nao suporta datas com
    fuso horario)."""
    df = df.copy()
    for coluna in df.columns:
        if isinstance(df[coluna].dtype, pd.DatetimeTZDtype):
            df[coluna] = df[coluna].dt.tz_localize(None)
    return df
