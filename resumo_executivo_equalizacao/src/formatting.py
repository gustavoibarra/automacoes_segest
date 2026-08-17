"""Formatacao de numeros, percentuais e datas no padrao brasileiro.
Modulo autocontido (sem dependencia de projeto_equalizacao)."""
from __future__ import annotations

import math

import pandas as pd


def formatar_numero(valor, casas: int = 0) -> str:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "N/A"
    texto = f"{valor:,.{casas}f}"
    texto = texto.replace(",", "§").replace(".", ",").replace("§", ".")
    return texto


def formatar_percentual(valor, casas: int = 1) -> str:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "N/A"
    return f"{formatar_numero(valor, casas)}%"


def formatar_percentual_com_sinal(valor, casas: int = 1) -> str:
    """Como formatar_percentual, mas antepoe '+' a valores positivos --
    usado nas colunas de variacao liquida."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "N/A"
    sinal = "+" if valor > 0 else ""
    return f"{sinal}{formatar_numero(valor, casas)}%"


def formatar_data(valor) -> str:
    if valor is None or pd.isna(valor):
        return "-"
    ts = pd.Timestamp(valor)
    return ts.strftime("%d/%m/%Y")


def formatar_data_extenso_dia1(valor) -> str:
    """Formata como '1º/07/2026' quando o dia e 1, senao 'DD/MM/AAAA'."""
    if valor is None or pd.isna(valor):
        return "-"
    ts = pd.Timestamp(valor)
    if ts.day == 1:
        return f"1º/{ts.month:02d}/{ts.year}"
    return ts.strftime("%d/%m/%Y")
