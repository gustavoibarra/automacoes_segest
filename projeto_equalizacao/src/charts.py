"""Construtores de graficos Plotly, reutilizados pelo dashboard Streamlit e
pelo relatorio DOCX (exportados como imagem via kaleido). Secao 18.

Todo grafico passa por `aplicar_metadados`, que garante titulo, periodo,
filtros aplicados, unidade de medida, fonte dos dados e data de atualizacao
-- alem do tooltip padrao do Plotly.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

FONTE_DADOS = "Sistema de Equalizacao TRT12 - dados consolidados localmente"


def aplicar_metadados(fig: go.Figure, titulo: str, periodo_texto: str = "", filtros_texto: str = "",
                       unidade_medida: str = "processos", atualizado_em: datetime | None = None) -> go.Figure:
    atualizado_em = atualizado_em or datetime.now()
    subtitulo = f"Periodo: {periodo_texto or 'todo o periodo disponivel'} | Filtros: {filtros_texto or 'nenhum'}"
    rodape = f"Fonte: {FONTE_DADOS} | Unidade de medida: {unidade_medida} | Atualizado em: {atualizado_em.strftime('%d/%m/%Y %H:%M')}"

    fig.update_layout(
        title={"text": f"{titulo}<br><sup>{subtitulo}</sup>"},
        hovermode="closest",
        margin=dict(b=90),
        template="plotly_white",
    )
    fig.add_annotation(
        text=rodape, xref="paper", yref="paper", x=0, y=-0.22, showarrow=False,
        font=dict(size=10, color="gray"), align="left",
    )
    return fig


def grafico_comparativo_barras(tabela_com: pd.DataFrame, tabela_sem: pd.DataFrame, *, periodo_texto="",
                                filtros_texto="", coluna_valor: str = "quantidade",
                                titulo: str = "Comparativo por unidade: com x sem equalizacao",
                                rotulo_eixo_y: str = "Quantidade de processos distintos",
                                unidade_medida: str = "processos") -> go.Figure:
    fig = go.Figure()
    fig.add_bar(name="Sem equalizacao (simulado)", x=tabela_sem["unidade_original"], y=tabela_sem[coluna_valor])
    fig.add_bar(name="Com equalizacao (real)", x=tabela_com["unidade_original"], y=tabela_com[coluna_valor])

    media_sem = tabela_sem[coluna_valor].mean() if len(tabela_sem) else 0
    media_com = tabela_com[coluna_valor].mean() if len(tabela_com) else 0
    fig.add_hline(y=media_sem, line_dash="dot", line_color="orange",
                   annotation_text=f"Media sem equalizacao ({media_sem:.2f})")
    fig.add_hline(y=media_com, line_dash="dash", line_color="blue",
                   annotation_text=f"Media com equalizacao ({media_com:.2f})")

    fig.update_layout(barmode="group", xaxis_title="Unidade", yaxis_title=rotulo_eixo_y)
    return aplicar_metadados(fig, titulo, periodo_texto, filtros_texto, unidade_medida=unidade_medida)


def grafico_comparativo_barras_por_magistrado(tabela_com: pd.DataFrame, tabela_sem: pd.DataFrame, *,
                                               periodo_texto="", filtros_texto="") -> go.Figure:
    """Mesma comparacao por unidade, mas usando processos_por_magistrado no
    lugar da quantidade bruta -- as medidas ponderadas pela quantidade de
    magistrados de cada unidade."""
    return grafico_comparativo_barras(
        tabela_com, tabela_sem, periodo_texto=periodo_texto, filtros_texto=filtros_texto,
        coluna_valor="processos_por_magistrado",
        titulo="Comparativo por unidade (por magistrado): com x sem equalizacao",
        rotulo_eixo_y="Processos por magistrado", unidade_medida="processos por magistrado",
    )


def grafico_dispersao_45graus(tabela_com: pd.DataFrame, tabela_sem: pd.DataFrame, *, periodo_texto="",
                               filtros_texto="", coluna_valor: str = "quantidade",
                               titulo: str = "Dispersao: quantidade sem x com equalizacao (linha de 45 graus)",
                               rotulo_eixo: str = "Quantidade", unidade_medida: str = "processos") -> go.Figure:
    dados = pd.merge(
        tabela_sem[["unidade_norm", "unidade_original", "classificacao", coluna_valor]]
        .rename(columns={coluna_valor: "sem_equalizacao"}),
        tabela_com[["unidade_norm", coluna_valor]].rename(columns={coluna_valor: "com_equalizacao"}),
        on="unidade_norm",
    )
    fig = px.scatter(dados, x="sem_equalizacao", y="com_equalizacao", color="classificacao",
                      hover_name="unidade_original", labels={
                          "sem_equalizacao": f"{rotulo_eixo} sem equalizacao", "com_equalizacao": f"{rotulo_eixo} com equalizacao",
                      })
    maior_sem = dados["sem_equalizacao"].max() if not dados.empty else 0
    maior_com = dados["com_equalizacao"].max() if not dados.empty else 0
    limite = max(maior_sem, maior_com, 1)
    fig.add_shape(type="line", x0=0, y0=0, x1=limite, y1=limite, line=dict(dash="dash", color="gray"))
    return aplicar_metadados(fig, titulo, periodo_texto, filtros_texto, unidade_medida=unidade_medida)


def grafico_dispersao_45graus_por_magistrado(tabela_com: pd.DataFrame, tabela_sem: pd.DataFrame, *,
                                              periodo_texto="", filtros_texto="") -> go.Figure:
    return grafico_dispersao_45graus(
        tabela_com, tabela_sem, periodo_texto=periodo_texto, filtros_texto=filtros_texto,
        coluna_valor="processos_por_magistrado",
        titulo="Dispersao por magistrado: sem x com equalizacao (linha de 45 graus)",
        rotulo_eixo="Processos por magistrado", unidade_medida="processos por magistrado",
    )


def boxplot_por_grupo(tabela_com: pd.DataFrame, tabela_sem: pd.DataFrame, *, periodo_texto="",
                       filtros_texto="", coluna_valor: str = "quantidade",
                       titulo: str = "Distribuicao de processos por grupo de unidades",
                       rotulo_eixo_y: str = "Quantidade de processos",
                       unidade_medida: str = "processos") -> go.Figure:
    com = tabela_com[["classificacao", coluna_valor]].assign(cenario="Com equalizacao")
    sem = tabela_sem[["classificacao", coluna_valor]].assign(cenario="Sem equalizacao")
    dados = pd.concat([com, sem], ignore_index=True)
    fig = px.box(dados, x="classificacao", y=coluna_valor, color="cenario", points="all",
                 labels={"classificacao": "Grupo de unidades", coluna_valor: rotulo_eixo_y})
    return aplicar_metadados(fig, titulo, periodo_texto, filtros_texto, unidade_medida=unidade_medida)


def boxplot_por_grupo_por_magistrado(tabela_com: pd.DataFrame, tabela_sem: pd.DataFrame, *, periodo_texto="",
                                      filtros_texto="") -> go.Figure:
    return boxplot_por_grupo(
        tabela_com, tabela_sem, periodo_texto=periodo_texto, filtros_texto=filtros_texto,
        coluna_valor="processos_por_magistrado",
        titulo="Distribuicao de processos por magistrado, por grupo de unidades",
        rotulo_eixo_y="Processos por magistrado", unidade_medida="processos por magistrado",
    )


def grafico_evolucao(diaria_df: pd.DataFrame, semanal_df: pd.DataFrame, titulo: str, *, periodo_texto="",
                      filtros_texto="") -> go.Figure:
    fig = go.Figure()
    if not diaria_df.empty:
        fig.add_trace(go.Scatter(x=diaria_df.iloc[:, 0], y=diaria_df["quantidade"], mode="lines+markers", name="Diaria"))
    if not semanal_df.empty:
        fig.add_trace(go.Scatter(x=semanal_df.iloc[:, 0], y=semanal_df["quantidade"], mode="lines+markers", name="Semanal"))
    fig.update_layout(xaxis_title="Data", yaxis_title="Quantidade de processos distintos")
    return aplicar_metadados(fig, titulo, periodo_texto, filtros_texto)


def grafico_barras_unidade(df: pd.DataFrame, coluna_valor: str, coluna_unidade: str, titulo: str, *,
                            periodo_texto="", filtros_texto="", unidade_medida="processos") -> go.Figure:
    dados = df.sort_values(coluna_valor, ascending=False)
    fig = px.bar(dados, x=coluna_unidade, y=coluna_valor)
    fig.update_layout(xaxis_title="Unidade", yaxis_title=titulo)
    return aplicar_metadados(fig, titulo, periodo_texto, filtros_texto, unidade_medida=unidade_medida)


def mapa_calor_fluxos(matriz: pd.DataFrame, *, periodo_texto="", filtros_texto="") -> go.Figure:
    if matriz.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem episodios de equalizacao valida no filtro atual.", showarrow=False)
        return aplicar_metadados(fig, "Matriz cedente x destinataria", periodo_texto, filtros_texto)

    fig = px.imshow(matriz, labels=dict(x="Unidade destinataria", y="Unidade cedente", color="Processos"),
                     color_continuous_scale="Blues", aspect="auto")
    return aplicar_metadados(fig, "Matriz de fluxos: unidade cedente x unidade destinataria", periodo_texto, filtros_texto)


def sankey_fluxos(rotas_df: pd.DataFrame, *, periodo_texto="", filtros_texto="", top_n: int = 25) -> go.Figure:
    if rotas_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sem episodios de equalizacao valida no filtro atual.", showarrow=False)
        return aplicar_metadados(fig, "Diagrama Sankey dos fluxos de equalizacao", periodo_texto, filtros_texto)

    dados = rotas_df.sort_values("quantidade", ascending=False).head(top_n)
    cedentes = list(dados["unidade_cedente"].unique())
    destinatarias = list(dados["unidade_destinataria"].unique())
    rotulos = cedentes + destinatarias
    indice = {nome: i for i, nome in enumerate(rotulos)}

    fig = go.Figure(go.Sankey(
        node=dict(label=rotulos, pad=15, thickness=15),
        link=dict(
            source=[indice[c] for c in dados["unidade_cedente"]],
            target=[indice[d] for d in dados["unidade_destinataria"]],
            value=dados["quantidade"].tolist(),
        ),
    ))
    return aplicar_metadados(fig, f"Diagrama Sankey dos fluxos de equalizacao (top {top_n} rotas)",
                              periodo_texto, filtros_texto)


def grafico_distancia_media(df: pd.DataFrame, *, periodo_texto="", filtros_texto="",
                             coluna_diferenca: str = "diferenca_absoluta_media",
                             titulo: str = "Distancia de cada unidade em relacao a media",
                             rotulo_eixo_y: str = "Distancia da media (processos)",
                             unidade_medida: str = "processos") -> go.Figure:
    dados = df.dropna(subset=[coluna_diferenca]).sort_values(coluna_diferenca, ascending=False)
    cores = dados[coluna_diferenca].apply(lambda v: "Acima da media" if v >= 0 else "Abaixo da media")
    fig = px.bar(dados, x="unidade_original", y=coluna_diferenca, color=cores,
                 labels={"unidade_original": "Unidade", coluna_diferenca: rotulo_eixo_y})
    return aplicar_metadados(fig, titulo, periodo_texto, filtros_texto, unidade_medida=unidade_medida)


def grafico_distancia_media_por_magistrado(df: pd.DataFrame, *, periodo_texto="", filtros_texto="") -> go.Figure:
    return grafico_distancia_media(
        df, periodo_texto=periodo_texto, filtros_texto=filtros_texto,
        coluna_diferenca="diferenca_absoluta_media_magistrado",
        titulo="Distancia de cada unidade em relacao a media ponderada por magistrado",
        rotulo_eixo_y="Distancia da media ponderada (processos por magistrado)",
        unidade_medida="processos por magistrado",
    )
