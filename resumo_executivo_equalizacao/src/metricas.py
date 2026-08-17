"""Calculo de todas as medidas do resumo executivo: KPIs, dispersao (com
faixa de classificacao do coeficiente de variacao), comparacao por grupo de
unidades, convergencia entre cedentes e destinatarias, e as tabelas de
anexo por unidade.

As formulas replicam a logica de projeto_equalizacao/src/metrics.py
(calcular_dispersao com media de referencia, medidas ponderadas por
magistrado), reimplementadas aqui para manter os dois projetos
independentes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import FAIXAS_CV

CEDENTE = "CEDENTE"
NEUTRA = "NEUTRA"
DESTINATARIA = "DESTINATARIA"
GRUPOS = (CEDENTE, NEUTRA, DESTINATARIA)


def classificar_cv(cv: float) -> str:
    if cv is None or (isinstance(cv, float) and np.isnan(cv)):
        return "N/A"
    for minimo, maximo, rotulo, _cor in FAIXAS_CV:
        if minimo <= cv < maximo:
            return rotulo
    return FAIXAS_CV[-1][2]


def calcular_dispersao(valores: pd.Series, media_referencia: float | None = None) -> dict:
    """Media, MAD, desvio-padrao, coeficiente de variacao, amplitude,
    minimo/maximo e contagem acima/abaixo da media. Quando
    media_referencia e informado, ele substitui a media simples como
    centro de referencia (usado nas medidas ponderadas por magistrado)."""
    serie = valores.dropna().astype(float)
    valores_np = serie.to_numpy()
    n = len(valores_np)
    if n == 0:
        return {
            "media": float("nan"), "mad": float("nan"), "desvio_padrao": float("nan"),
            "coeficiente_variacao": float("nan"), "amplitude": float("nan"),
            "minimo": float("nan"), "maximo": float("nan"),
            "qtd_acima_media": 0, "qtd_abaixo_media": 0,
        }
    media = float(media_referencia) if media_referencia is not None else float(np.mean(valores_np))
    distancias = valores_np - media
    mad = float(np.mean(np.abs(distancias)))
    desvio_padrao = float(np.sqrt(np.mean(distancias ** 2)))
    cv = float(desvio_padrao / media * 100) if media else float("nan")
    minimo, maximo = float(valores_np.min()), float(valores_np.max())
    return {
        "media": media, "mad": mad, "desvio_padrao": desvio_padrao,
        "coeficiente_variacao": cv, "amplitude": maximo - minimo,
        "minimo": minimo, "maximo": maximo,
        "qtd_acima_media": int(np.sum(valores_np > media)), "qtd_abaixo_media": int(np.sum(valores_np < media)),
    }


def media_ponderada_por_magistrado(tabela: pd.DataFrame) -> float:
    valida = tabela["quantidade_magistrados"].notna() & (tabela["quantidade_magistrados"] > 0)
    total_magistrados = tabela.loc[valida, "quantidade_magistrados"].sum()
    if not total_magistrados:
        return float("nan")
    total_processos = tabela.loc[valida, "quantidade"].sum()
    return float(total_processos / total_magistrados)


def tabela_por_unidade(unidades_df: pd.DataFrame, processos_df: pd.DataFrame, coluna_unidade: str) -> pd.DataFrame:
    """Quantidade de processos distintos por unidade (incluindo unidades
    com zero processos), mais processos_por_magistrado."""
    contagem = (
        processos_df[processos_df[coluna_unidade] != ""]
        .groupby(coluna_unidade)["processo_norm"].nunique()
    )
    base = unidades_df.copy()
    base["quantidade"] = base["unidade_norm"].map(contagem).fillna(0).astype(int)
    base["processos_por_magistrado"] = base.apply(
        lambda r: (r["quantidade"] / r["quantidade_magistrados"])
        if pd.notna(r["quantidade_magistrados"]) and r["quantidade_magistrados"] > 0 else float("nan"),
        axis=1,
    )
    return base.reset_index(drop=True)


def cenario_com_equalizacao(unidades_df: pd.DataFrame, processos_movimentados_df: pd.DataFrame) -> pd.DataFrame:
    return tabela_por_unidade(unidades_df, processos_movimentados_df, "unidade_final_real")


def cenario_sem_equalizacao(unidades_df: pd.DataFrame, processos_movimentados_df: pd.DataFrame) -> pd.DataFrame:
    return tabela_por_unidade(unidades_df, processos_movimentados_df, "unidade_simulada_sem_equalizacao")


def kpis(casos_novos_df: pd.DataFrame, tabela_com: pd.DataFrame, tabela_sem: pd.DataFrame) -> dict:
    casos_novos = int(casos_novos_df["processo_norm"].nunique())
    equalizados = int(casos_novos_df.loc[casos_novos_df["equalizacao_valida"] == True, "processo_norm"].nunique())  # noqa: E712
    percentual = (equalizados / casos_novos * 100) if casos_novos else float("nan")

    disp_com = calcular_dispersao(tabela_com["quantidade"])
    disp_sem = calcular_dispersao(tabela_sem["quantidade"])
    reducao_cv_unidade = (
        (disp_sem["coeficiente_variacao"] - disp_com["coeficiente_variacao"]) / disp_sem["coeficiente_variacao"] * 100
        if disp_sem["coeficiente_variacao"] else float("nan")
    )

    media_pond_com = media_ponderada_por_magistrado(tabela_com)
    media_pond_sem = media_ponderada_por_magistrado(tabela_sem)
    disp_mag_com = calcular_dispersao(tabela_com["processos_por_magistrado"], media_referencia=media_pond_com)
    disp_mag_sem = calcular_dispersao(tabela_sem["processos_por_magistrado"], media_referencia=media_pond_sem)
    reducao_cv_magistrado = (
        (disp_mag_sem["coeficiente_variacao"] - disp_mag_com["coeficiente_variacao"]) / disp_mag_sem["coeficiente_variacao"] * 100
        if disp_mag_sem["coeficiente_variacao"] else float("nan")
    )

    return {
        "casos_novos": casos_novos,
        "processos_equalizados": equalizados,
        "percentual_equalizados": percentual,
        "reducao_cv_unidade_pct": reducao_cv_unidade,
        "reducao_cv_magistrado_pct": reducao_cv_magistrado,
    }


def dimensao_dispersao(tabela_com: pd.DataFrame, tabela_sem: pd.DataFrame, coluna_valor: str,
                        media_referencia_com: float | None = None, media_referencia_sem: float | None = None) -> dict:
    """Monta a tabela de 6 medidas (Figura 1 / Figura 2 do relatorio) para
    uma dimensao (quantidade por unidade ou processos por magistrado)."""
    disp_com = calcular_dispersao(tabela_com[coluna_valor], media_referencia=media_referencia_com)
    disp_sem = calcular_dispersao(tabela_sem[coluna_valor], media_referencia=media_referencia_sem)

    reducao_desvio = (
        (disp_sem["desvio_padrao"] - disp_com["desvio_padrao"]) / disp_sem["desvio_padrao"] * 100
        if disp_sem["desvio_padrao"] else float("nan")
    )
    reducao_cv_pp = disp_sem["coeficiente_variacao"] - disp_com["coeficiente_variacao"]
    reducao_cv_pct = (reducao_cv_pp / disp_sem["coeficiente_variacao"] * 100) if disp_sem["coeficiente_variacao"] else float("nan")
    reducao_amplitude = (
        (disp_sem["amplitude"] - disp_com["amplitude"]) / disp_sem["amplitude"] * 100
        if disp_sem["amplitude"] else float("nan")
    )

    return {
        "sem": disp_sem, "com": disp_com,
        "faixa_sem": classificar_cv(disp_sem["coeficiente_variacao"]),
        "faixa_com": classificar_cv(disp_com["coeficiente_variacao"]),
        "reducao_desvio_padrao_pct": reducao_desvio,
        "reducao_cv_pp": reducao_cv_pp,
        "reducao_cv_pct": reducao_cv_pct,
        "reducao_amplitude_pct": reducao_amplitude,
        "melhora": disp_com["coeficiente_variacao"] < disp_sem["coeficiente_variacao"],
    }


def tabela_grupos(unidades_df: pd.DataFrame, tabela_com: pd.DataFrame, tabela_sem: pd.DataFrame) -> pd.DataFrame:
    """Sintese por grupo (cedentes/neutras/destinatarias) + linha final
    'Total do sistema'."""
    linhas = []
    for grupo in GRUPOS:
        unidades_grupo = unidades_df[unidades_df["classificacao"] == grupo]
        com_grupo = tabela_com[tabela_com["classificacao"] == grupo]
        sem_grupo = tabela_sem[tabela_sem["classificacao"] == grupo]

        qtd_unidades = int(len(unidades_grupo))
        qtd_magistrados = float(unidades_grupo["quantidade_magistrados"].sum(skipna=True))
        total_com = int(com_grupo["quantidade"].sum())
        total_sem = int(sem_grupo["quantidade"].sum())
        media_unid_com = float(com_grupo["quantidade"].mean()) if qtd_unidades else float("nan")
        media_unid_sem = float(sem_grupo["quantidade"].mean()) if qtd_unidades else float("nan")
        media_mag_com = media_ponderada_por_magistrado(com_grupo)
        media_mag_sem = media_ponderada_por_magistrado(sem_grupo)

        linhas.append({
            "grupo": grupo, "quantidade_unidades": qtd_unidades, "quantidade_magistrados": qtd_magistrados,
            "total_sem": total_sem, "media_unidade_sem": media_unid_sem, "media_magistrado_sem": media_mag_sem,
            "total_com": total_com, "media_unidade_com": media_unid_com, "media_magistrado_com": media_mag_com,
            "variacao_processos": total_com - total_sem,
            "variacao_pct": ((total_com - total_sem) / total_sem * 100) if total_sem else float("nan"),
        })

    total_unidades = int(len(unidades_df))
    total_magistrados = float(unidades_df["quantidade_magistrados"].sum(skipna=True))
    total_com_sistema = int(tabela_com["quantidade"].sum())
    total_sem_sistema = int(tabela_sem["quantidade"].sum())
    linhas.append({
        "grupo": "Total do sistema", "quantidade_unidades": total_unidades, "quantidade_magistrados": total_magistrados,
        "total_sem": total_sem_sistema,
        "media_unidade_sem": float(tabela_sem["quantidade"].mean()) if total_unidades else float("nan"),
        "media_magistrado_sem": media_ponderada_por_magistrado(tabela_sem),
        "total_com": total_com_sistema,
        "media_unidade_com": float(tabela_com["quantidade"].mean()) if total_unidades else float("nan"),
        "media_magistrado_com": media_ponderada_por_magistrado(tabela_com),
        "variacao_processos": total_com_sistema - total_sem_sistema,
        "variacao_pct": ((total_com_sistema - total_sem_sistema) / total_sem_sistema * 100) if total_sem_sistema else float("nan"),
    })
    return pd.DataFrame(linhas)


def convergencia_cedentes_destinatarias(grupos_df: pd.DataFrame) -> dict:
    """Diferenca entre as medias de cedentes e destinatarias, nos dois
    cenarios, para as duas dimensoes (por unidade e por magistrado)."""
    cedente = grupos_df[grupos_df["grupo"] == CEDENTE].iloc[0]
    destinataria = grupos_df[grupos_df["grupo"] == DESTINATARIA].iloc[0]

    def _linha(campo_sem, campo_com):
        diff_sem = abs(cedente[campo_sem] - destinataria[campo_sem])
        diff_com = abs(cedente[campo_com] - destinataria[campo_com])
        reducao_abs = diff_sem - diff_com
        reducao_pct = (reducao_abs / diff_sem * 100) if diff_sem else float("nan")
        return {"sem": diff_sem, "com": diff_com, "reducao_absoluta": reducao_abs, "reducao_relativa_pct": reducao_pct}

    return {
        "unidade": _linha("media_unidade_sem", "media_unidade_com"),
        "magistrado": _linha("media_magistrado_sem", "media_magistrado_com"),
    }


def _linha_totais(unidades_grupo: pd.DataFrame, casos_novos_df: pd.DataFrame, tabela_com: pd.DataFrame,
                   tabela_sem: pd.DataFrame, coluna_origem_norm: str, coluna_equalizacao_norm: str
                   ) -> pd.DataFrame:
    linhas = []
    for _, unidade in unidades_grupo.iterrows():
        norm = unidade["unidade_norm"]
        casos_novos_unidade = int(
            casos_novos_df.loc[casos_novos_df[coluna_origem_norm] == norm, "processo_norm"].nunique()
        )
        equalizados_unidade = int(casos_novos_df.loc[
            (casos_novos_df["equalizacao_valida"] == True) & (casos_novos_df[coluna_equalizacao_norm] == norm),  # noqa: E712
            "processo_norm",
        ].nunique())

        linha_com = tabela_com[tabela_com["unidade_norm"] == norm].iloc[0]
        linha_sem = tabela_sem[tabela_sem["unidade_norm"] == norm].iloc[0]

        linhas.append({
            "unidade": unidade["unidade_original"], "unidade_norm": norm,
            "quantidade_magistrados": unidade["quantidade_magistrados"],
            "casos_novos": casos_novos_unidade, "equalizados": equalizados_unidade,
            "sem_processos": int(linha_sem["quantidade"]), "sem_proc_magistrado": linha_sem["processos_por_magistrado"],
            "com_processos": int(linha_com["quantidade"]), "com_proc_magistrado": linha_com["processos_por_magistrado"],
            "variacao_processos": int(linha_com["quantidade"]) - int(linha_sem["quantidade"]),
            "variacao_proc_magistrado": linha_com["processos_por_magistrado"] - linha_sem["processos_por_magistrado"],
        })
    return pd.DataFrame(linhas)


def tabela_anexo_cedentes(unidades_df: pd.DataFrame, casos_novos_df: pd.DataFrame,
                           tabela_com: pd.DataFrame, tabela_sem: pd.DataFrame) -> pd.DataFrame:
    """Tabela do Anexo 1 (unidades cedentes): uma linha por unidade,
    ordenada pelo nome, com Casos novos atribuidos pela unidade de
    distribuicao inicial e Equalizados enviados a partir da unidade
    cedente do episodio principal de cada processo."""
    unidades_grupo = unidades_df[unidades_df["classificacao"] == CEDENTE].sort_values("unidade_original")
    return _linha_totais(
        unidades_grupo, casos_novos_df, tabela_com, tabela_sem,
        coluna_origem_norm="unidade_distribuicao_inicial", coluna_equalizacao_norm="unidade_cedente_equalizacao",
    )


def tabela_anexo_destinatarias(unidades_df: pd.DataFrame, casos_novos_df: pd.DataFrame,
                                tabela_com: pd.DataFrame, tabela_sem: pd.DataFrame) -> pd.DataFrame:
    """Tabela do Anexo 2 (unidades destinatarias): analoga a de cedentes,
    mas com Equalizados recebidos a partir da unidade destinataria."""
    unidades_grupo = unidades_df[unidades_df["classificacao"] == DESTINATARIA].sort_values("unidade_original")
    return _linha_totais(
        unidades_grupo, casos_novos_df, tabela_com, tabela_sem,
        coluna_origem_norm="unidade_distribuicao_inicial", coluna_equalizacao_norm="unidade_destinataria_equalizacao",
    )


def totais_anexo(tabela_anexo_df: pd.DataFrame) -> dict:
    """Linha TOTAL do anexo: soma das colunas absolutas; as colunas de taxa
    (processos por magistrado) nao sao somadas -- ficam a cargo de quem
    monta a tabela exibir '-' nessas posicoes."""
    return {
        "quantidade_magistrados": float(tabela_anexo_df["quantidade_magistrados"].sum()),
        "casos_novos": int(tabela_anexo_df["casos_novos"].sum()),
        "equalizados": int(tabela_anexo_df["equalizados"].sum()),
        "sem_processos": int(tabela_anexo_df["sem_processos"].sum()),
        "com_processos": int(tabela_anexo_df["com_processos"].sum()),
        "variacao_processos": int(tabela_anexo_df["variacao_processos"].sum()),
    }


def media_anexo(tabela_anexo_df: pd.DataFrame, grupos_df: pd.DataFrame, grupo: str) -> dict:
    """Linha 'Media por unidade / carga do grupo': media simples para Mag.,
    Casos novos e Equalizados; para as colunas de processos e
    processos/magistrado, reaproveita a media (simples e ponderada) ja
    calculada em tabela_grupos para esse grupo."""
    linha_grupo = grupos_df[grupos_df["grupo"] == grupo].iloc[0]
    qtd_unidades = len(tabela_anexo_df)
    media_simples = lambda coluna: (tabela_anexo_df[coluna].sum() / qtd_unidades) if qtd_unidades else float("nan")  # noqa: E731
    return {
        "quantidade_magistrados": media_simples("quantidade_magistrados"),
        "casos_novos": media_simples("casos_novos"),
        "equalizados": media_simples("equalizados"),
        "sem_processos": linha_grupo["media_unidade_sem"],
        "sem_proc_magistrado": linha_grupo["media_magistrado_sem"],
        "com_processos": linha_grupo["media_unidade_com"],
        "com_proc_magistrado": linha_grupo["media_magistrado_com"],
        "variacao_processos": linha_grupo["media_unidade_com"] - linha_grupo["media_unidade_sem"],
        "variacao_proc_magistrado": linha_grupo["media_magistrado_com"] - linha_grupo["media_magistrado_sem"],
    }
