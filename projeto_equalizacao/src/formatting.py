"""Formatacao de numeros, percentuais e datas no padrao brasileiro
(secao 27 do prompt)."""
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


def formatar_data(valor) -> str:
    if valor is None or pd.isna(valor):
        return "-"
    ts = pd.Timestamp(valor)
    return ts.strftime("%d/%m/%Y")
