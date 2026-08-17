"""Graficos matplotlib do resumo executivo: comparativo por grupo de
unidades (barras) e coeficiente de variacao com faixas de classificacao
coloridas -- correspondem as 4 imagens do documento de referencia."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # backend sem interface grafica, seguro para gerar PNG em servidor/CLI

import matplotlib.pyplot as plt
import numpy as np

from config import COR_GRAFICO_COM_EQ, COR_GRAFICO_SEM_EQ, COR_TITULO, FAIXAS_CV
from src.formatting import formatar_numero

_COR_SEM_EQ = f"#{COR_GRAFICO_SEM_EQ}"
_COR_COM_EQ = f"#{COR_GRAFICO_COM_EQ}"

_GRUPOS_GRAFICO = ("CEDENTE", "NEUTRA", "DESTINATARIA")
_ROTULOS_GRUPO = {"CEDENTE": "Cedentes", "NEUTRA": "Neutras", "DESTINATARIA": "Destinatárias"}


def _rotular_barras(ax, barras, casas: int = 1) -> None:
    for barra in barras:
        altura = barra.get_height()
        ax.text(barra.get_x() + barra.get_width() / 2, altura, formatar_numero(altura, casas),
                ha="center", va="bottom", fontweight="bold", fontsize=10)


def _desenhar_barras_grupo(ax, grupos_df, coluna_sem: str, coluna_com: str, titulo: str, ylabel: str) -> None:
    grupos_ordenados = grupos_df[grupos_df["grupo"].isin(_GRUPOS_GRAFICO)].set_index("grupo").reindex(_GRUPOS_GRAFICO)
    rotulos = [_ROTULOS_GRUPO[g] for g in grupos_ordenados.index]
    x = np.arange(len(rotulos))
    largura = 0.35

    barras_sem = ax.bar(x - largura / 2, grupos_ordenados[coluna_sem], largura,
                         label="Sem equalização", color=_COR_SEM_EQ)
    barras_com = ax.bar(x + largura / 2, grupos_ordenados[coluna_com], largura,
                         label="Com equalização", color=_COR_COM_EQ)
    _rotular_barras(ax, barras_sem)
    _rotular_barras(ax, barras_com)

    ax.set_title(titulo, fontsize=14, fontweight="bold", color=f"#{COR_TITULO}")
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(rotulos)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    maximo = max(grupos_ordenados[coluna_sem].max(), grupos_ordenados[coluna_com].max())
    ax.set_ylim(0, maximo * 1.18 if maximo else 1)


def grafico_barras_grupo(grupos_df, coluna_sem: str, coluna_com: str, titulo: str, ylabel: str):
    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    _desenhar_barras_grupo(ax, grupos_df, coluna_sem, coluna_com, titulo, ylabel)
    fig.tight_layout()
    return fig


def grafico_comparativo_duplo(grupos_df):
    """Figura com dois paineis lado a lado: media de processos por unidade
    e carga media por magistrado, por grupo -- equivalente a Figura do
    documento de referencia que compara as duas dimensoes juntas."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5), dpi=150)
    _desenhar_barras_grupo(ax1, grupos_df, "media_unidade_sem", "media_unidade_com",
                            "Média de processos por grupo", "Processos por unidade")
    _desenhar_barras_grupo(ax2, grupos_df, "media_magistrado_sem", "media_magistrado_com",
                            "Carga média por magistrado em cada grupo", "Processos por magistrado")
    fig.tight_layout()
    return fig


def grafico_cv_faixas(cv_sem: float, cv_com: float, titulo: str):
    """Grafico de barras (sem x com equalizacao) do coeficiente de
    variacao, sobre faixas de fundo coloridas que classificam o nivel de
    dispersao (mesma escala usada nas tabelas de texto)."""
    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=150)

    limite_superior = max(50.0, cv_sem, cv_com) * 1.05
    for minimo, maximo, rotulo, cor in FAIXAS_CV:
        topo = min(maximo, limite_superior)
        if minimo >= limite_superior:
            continue
        ax.axhspan(minimo, topo, color=cor, alpha=0.9, zorder=0)
        ax.text(1.01, (minimo + topo) / 2, rotulo, transform=ax.get_yaxis_transform(),
                va="center", ha="left", fontsize=10, color="#555555")

    categorias = ["Sem equalização", "Com equalização"]
    valores = [cv_sem, cv_com]
    barras = ax.bar(categorias, valores, width=0.5, color=[_COR_SEM_EQ, _COR_COM_EQ],
                     zorder=3, edgecolor="white")
    for barra, valor in zip(barras, valores):
        ax.text(barra.get_x() + barra.get_width() / 2, valor + limite_superior * 0.015,
                formatar_percentual_grafico(valor), ha="center", va="bottom", fontweight="bold", fontsize=13,
                color="#1f2937")
        rotulo_faixa = _rotulo_faixa(valor)
        if valor > limite_superior * 0.08:
            ax.text(barra.get_x() + barra.get_width() / 2, valor * 0.5, rotulo_faixa,
                     ha="center", va="center", fontweight="bold", fontsize=11, color="white")

    ax.set_title(titulo, fontsize=15, fontweight="bold", color=f"#{COR_TITULO}")
    ax.set_ylabel("Coeficiente de variação (%)")
    ax.set_ylim(0, limite_superior)
    ax.set_xlim(-0.6, 1.9)
    fig.tight_layout()
    return fig


def _rotulo_faixa(cv: float) -> str:
    for minimo, maximo, rotulo, _cor in FAIXAS_CV:
        if minimo <= cv < maximo:
            return rotulo
    return FAIXAS_CV[-1][2]


def formatar_percentual_grafico(valor: float) -> str:
    return f"{formatar_numero(valor, 2)}%"
