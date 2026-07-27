"""Cards executivos, cenarios com/sem equalizacao, dispersao, analise por
grupo e analitico do Sistema de Equalizacao (secoes 11 a 15 do prompt).

Convencao de contagem usada em todo o modulo (secao 27): 'processo' sempre
significa COUNT DISTINCT do numero de processo; 'movimentacao' conta linhas
de movimentacao; 'episodio' conta episodios de passagem por triagem
(tabela episodios_equalizacao); 'unidade' conta unidades permanentes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.filters import PAPEIS_UNIDADE, coluna_papel
from src.normalization import (
    CLASSIFICACAO_CEDENTE,
    CLASSIFICACAO_DESTINATARIA,
    CLASSIFICACAO_NEUTRA,
)

GRUPOS = (CLASSIFICACAO_CEDENTE, CLASSIFICACAO_NEUTRA, CLASSIFICACAO_DESTINATARIA)

_PAPEL_CLASSIF_COLUNA = {papel: f"classificacao_{coluna_papel(papel)[0]}" for papel in PAPEIS_UNIDADE}


def enriquecer_classificacoes(processos_df: pd.DataFrame, unidades_permanentes_df: pd.DataFrame
                               ) -> pd.DataFrame:
    """Acrescenta, para cada papel de unidade, a classificacao (CEDENTE /
    NEUTRA / DESTINATARIA / NAO_CLASSIFICADA) da unidade correspondente."""
    df = processos_df.copy()
    mapa = unidades_permanentes_df.set_index("unidade_norm")["classificacao"].to_dict()
    for papel in PAPEIS_UNIDADE:
        col_norm, _ = coluna_papel(papel)
        col_dest = _PAPEL_CLASSIF_COLUNA[papel]
        df[col_dest] = df[col_norm].map(mapa).fillna("NAO_CLASSIFICADA")
        df.loc[df[col_norm] == "", col_dest] = ""
    return df


# ---------------------------------------------------------------------------
# Dispersao
# ---------------------------------------------------------------------------

def calcular_dispersao(quantidades: pd.Series, media_referencia: float | None = None) -> dict:
    """Calcula as medidas de dispersao da secao 12.4 sobre uma serie de
    quantidades por unidade (uma unidade por linha, zeros incluidos).

    Por padrao, o centro de referencia e a media aritmetica simples dos
    valores (cada unidade com o mesmo peso). Quando `media_referencia` e
    informado, ele e usado como centro no lugar da media simples -- e o
    caso das medidas ponderadas pela quantidade de magistrados, cujo
    centro e a media ponderada (total de processos / total de
    magistrados), nao a media simples das taxas por unidade. Valores NaN
    (ex.: unidades sem quantidade de magistrados informada) sao ignorados.
    """
    valores = quantidades.dropna().astype(float).to_numpy()
    n = len(valores)
    if n == 0:
        return {
            "media": float("nan"), "mad": float("nan"), "desvio_padrao": float("nan"),
            "coeficiente_variacao": float("nan"), "amplitude": float("nan"),
            "qtd_acima_media": 0, "qtd_abaixo_media": 0,
            "maior_distancia_positiva": float("nan"), "maior_distancia_negativa": float("nan"),
        }
    media = float(media_referencia) if media_referencia is not None else float(np.mean(valores))
    distancias = valores - media
    mad = float(np.mean(np.abs(distancias)))
    desvio_padrao = float(np.sqrt(np.mean(distancias ** 2)))  # RMS em torno de 'media' (= populacional quando media = np.mean(valores))
    cv = float(desvio_padrao / media * 100) if media != 0 else float("nan")
    amplitude = float(valores.max() - valores.min())
    qtd_acima = int(np.sum(valores > media))
    qtd_abaixo = int(np.sum(valores < media))
    maior_pos = float(distancias.max()) if n else float("nan")
    maior_neg = float(distancias.min()) if n else float("nan")
    return {
        "media": media, "mad": mad, "desvio_padrao": desvio_padrao,
        "coeficiente_variacao": cv, "amplitude": amplitude,
        "qtd_acima_media": qtd_acima, "qtd_abaixo_media": qtd_abaixo,
        "maior_distancia_positiva": maior_pos, "maior_distancia_negativa": maior_neg,
    }


def comparar_dispersao(disp_sem: dict, disp_com: dict) -> dict:
    def _diff_abs(chave):
        return disp_com[chave] - disp_sem[chave]

    def _diff_pct(chave):
        base = disp_sem[chave]
        if not base:
            return float("nan")
        return (disp_com[chave] - base) / base * 100

    def _reducao(chave):
        base = disp_sem[chave]
        if not base:
            return float("nan")
        return (disp_sem[chave] - disp_com[chave]) / base * 100

    return {
        "diferenca_absoluta_media": _diff_abs("media"),
        "diferenca_percentual_media": _diff_pct("media"),
        "melhora": disp_com["mad"] < disp_sem["mad"],
        "reducao_mad_pct": _reducao("mad"),
        "reducao_desvio_padrao_pct": _reducao("desvio_padrao"),
        "reducao_coeficiente_variacao_pct": _reducao("coeficiente_variacao"),
    }


# ---------------------------------------------------------------------------
# Tabela por unidade / cenarios com e sem equalizacao (secao 12)
# ---------------------------------------------------------------------------

def tabela_por_unidade(unidades_filtradas: pd.DataFrame, processos_filtrados: pd.DataFrame,
                        coluna_unidade_norm: str) -> pd.DataFrame:
    """Monta a tabela unidade x quantidade de casos novos, incluindo
    unidades com zero processos, com as medidas da secao 12.1/12.2 e o
    grupo de medidas ponderadas pela quantidade de magistrados de cada
    unidade (processos_por_magistrado e a diferenca em relacao a media
    ponderada do sistema)."""
    contagem = (
        processos_filtrados[processos_filtrados[coluna_unidade_norm] != ""]
        .groupby(coluna_unidade_norm)["processo_norm"].nunique()
    )
    colunas_base = ["unidade_norm", "unidade_original", "classificacao"]
    if "quantidade_magistrados" in unidades_filtradas.columns:
        colunas_base.append("quantidade_magistrados")
    base = unidades_filtradas[colunas_base].copy()
    if "quantidade_magistrados" not in base.columns:
        base["quantidade_magistrados"] = float("nan")
    base["quantidade"] = base["unidade_norm"].map(contagem).fillna(0).astype(int)

    total = int(base["quantidade"].sum())
    media = base["quantidade"].mean() if len(base) else float("nan")

    base["percentual_total"] = base["quantidade"].apply(lambda q: (q / total * 100) if total else float("nan"))
    base["diferenca_absoluta_media"] = base["quantidade"] - media
    base["diferenca_percentual_media"] = base["diferenca_absoluta_media"].apply(
        lambda d: (d / media * 100) if media else float("nan")
    )

    # Grupo de medidas ponderadas pela quantidade de magistrados de cada unidade.
    valida = base["quantidade_magistrados"].notna() & (base["quantidade_magistrados"] > 0)
    total_magistrados = base.loc[valida, "quantidade_magistrados"].sum()
    total_processos_validos = base.loc[valida, "quantidade"].sum()
    media_ponderada = (total_processos_validos / total_magistrados) if total_magistrados else float("nan")

    base["processos_por_magistrado"] = base.apply(
        lambda r: (r["quantidade"] / r["quantidade_magistrados"])
        if pd.notna(r["quantidade_magistrados"]) and r["quantidade_magistrados"] > 0 else float("nan"),
        axis=1,
    )
    base["diferenca_absoluta_media_magistrado"] = base["processos_por_magistrado"] - media_ponderada
    base["diferenca_percentual_media_magistrado"] = base["diferenca_absoluta_media_magistrado"].apply(
        lambda d: (d / media_ponderada * 100) if pd.notna(d) and media_ponderada else float("nan")
    )
    return base.reset_index(drop=True)


def media_ponderada_por_magistrado(tabela: pd.DataFrame) -> float:
    """Recalcula, a partir de uma tabela produzida por tabela_por_unidade,
    a media ponderada pela quantidade de magistrados (total de processos
    das unidades com magistrados informados / total de magistrados)."""
    valida = tabela["quantidade_magistrados"].notna() & (tabela["quantidade_magistrados"] > 0)
    total_magistrados = tabela.loc[valida, "quantidade_magistrados"].sum()
    if not total_magistrados:
        return float("nan")
    total_processos = tabela.loc[valida, "quantidade"].sum()
    return float(total_processos / total_magistrados)


def dispersao_por_magistrado(tabela: pd.DataFrame) -> dict:
    """Dispersao do grupo de medidas ponderadas pela quantidade de
    magistrados: cada unidade contribui com processos_por_magistrado
    (processos da unidade / magistrados da unidade), e o centro de
    referencia e a media ponderada do sistema (nao a media simples das
    taxas por unidade). Unidades sem quantidade de magistrados valida sao
    ignoradas no calculo."""
    media_ponderada = media_ponderada_por_magistrado(tabela)
    return calcular_dispersao(tabela["processos_por_magistrado"], media_referencia=media_ponderada)


def cenario_com_equalizacao(processos_filtrados: pd.DataFrame, unidades_filtradas: pd.DataFrame) -> pd.DataFrame:
    return tabela_por_unidade(unidades_filtradas, processos_filtrados, "unidade_final_real")


def cenario_sem_equalizacao(processos_filtrados: pd.DataFrame, unidades_filtradas: pd.DataFrame) -> pd.DataFrame:
    return tabela_por_unidade(unidades_filtradas, processos_filtrados, "unidade_simulada_sem_equalizacao")


def quantidade_processos_unidade_nao_classificada(processos_filtrados: pd.DataFrame, unidades_filtradas: pd.DataFrame,
                                                    coluna_unidade_norm: str) -> int:
    """Conta processos distintos cuja unidade (no papel indicado) nao esta
    entre as unidades permanentes classificadas do filtro atual -- por
    exemplo, um orgao julgador que nao consta no arquivo de classificacao.
    Esses processos nao aparecem nas tabelas por unidade (que cobrem somente
    unidades permanentes classificadas), mas continuam contabilizados em
    'casos novos' e sao sinalizados como anomalia UNIDADE_NAO_CLASSIFICADA."""
    permitidas = set(unidades_filtradas["unidade_norm"])
    mascara = ~processos_filtrados[coluna_unidade_norm].isin(permitidas)
    return int(processos_filtrados.loc[mascara, "processo_norm"].nunique())


def validar_totais_cenarios(casos_novos: int, tabela_com: pd.DataFrame, tabela_sem: pd.DataFrame,
                             nao_classificados_com: int = 0, nao_classificados_sem: int = 0) -> list[str]:
    """Cenario de aceitacao 7: os totais devem sempre bater. Processos cuja
    unidade nao e classificada (ja sinalizados como anomalia a parte) sao
    somados de volta antes da comparacao, pois eles nao aparecem nas
    tabelas por unidade permanente. Retorna uma lista de erros de
    consistencia (vazia se tudo estiver correto)."""
    erros = []
    total_com = int(tabela_com["quantidade"].sum()) + nao_classificados_com
    total_sem = int(tabela_sem["quantidade"].sum()) + nao_classificados_sem
    if total_com != casos_novos:
        erros.append(f"Erro de consistencia: total com equalizacao ({total_com}) != casos novos ({casos_novos}).")
    if total_sem != casos_novos:
        erros.append(f"Erro de consistencia: total sem equalizacao ({total_sem}) != casos novos ({casos_novos}).")
    return erros


# ---------------------------------------------------------------------------
# Cards executivos (secao 11)
# ---------------------------------------------------------------------------

def cards_executivos(processos_filtrados: pd.DataFrame, unidades_filtradas: pd.DataFrame,
                      disp_sem: dict, disp_com: dict, disp_magistrado_sem: dict | None = None,
                      disp_magistrado_com: dict | None = None) -> dict:
    casos_novos = int(processos_filtrados["processo_norm"].nunique())
    equalizados = int(processos_filtrados.loc[processos_filtrados["equalizacao_valida"], "processo_norm"].nunique())
    percentual_equalizados = (equalizados / casos_novos * 100) if casos_novos else None

    qtd_destinatarias = int((unidades_filtradas["classificacao"] == CLASSIFICACAO_DESTINATARIA).sum())
    media_equalizados_por_destinataria = (equalizados / qtd_destinatarias) if qtd_destinatarias else None

    def _media_final_real_por_grupo(grupo: str):
        qtd_unidades = int((unidades_filtradas["classificacao"] == grupo).sum())
        if qtd_unidades == 0:
            return None
        qtd_processos = int(processos_filtrados.loc[
            processos_filtrados["classificacao_unidade_final_real"] == grupo, "processo_norm"
        ].nunique())
        return qtd_processos / qtd_unidades

    media_por_cedente = _media_final_real_por_grupo(CLASSIFICACAO_CEDENTE)
    media_por_neutra = _media_final_real_por_grupo(CLASSIFICACAO_NEUTRA)
    media_por_destinataria = _media_final_real_por_grupo(CLASSIFICACAO_DESTINATARIA)

    if disp_sem["mad"]:
        reducao_dispersao = (disp_sem["mad"] - disp_com["mad"]) / disp_sem["mad"] * 100
    else:
        reducao_dispersao = None

    media_magistrado_com = disp_magistrado_com["media"] if disp_magistrado_com else None
    media_magistrado_sem = disp_magistrado_sem["media"] if disp_magistrado_sem else None
    if media_magistrado_com is not None and pd.isna(media_magistrado_com):
        media_magistrado_com = None
    if media_magistrado_sem is not None and pd.isna(media_magistrado_sem):
        media_magistrado_sem = None

    reducao_dispersao_magistrado = None
    if disp_magistrado_sem and disp_magistrado_com and disp_magistrado_sem["mad"] and pd.notna(disp_magistrado_sem["mad"]):
        reducao_dispersao_magistrado = (
            (disp_magistrado_sem["mad"] - disp_magistrado_com["mad"]) / disp_magistrado_sem["mad"] * 100
        )

    return {
        "casos_novos": casos_novos,
        "processos_equalizados": equalizados,
        "percentual_processos_equalizados": percentual_equalizados,
        "media_equalizados_por_unidade_destinataria": media_equalizados_por_destinataria,
        "media_processos_por_unidade_cedente": media_por_cedente,
        "media_processos_por_unidade_neutra": media_por_neutra,
        "media_processos_por_unidade_destinataria": media_por_destinataria,
        "reducao_dispersao_pct": reducao_dispersao,
        "media_ponderada_magistrado_com_equalizacao": media_magistrado_com,
        "media_ponderada_magistrado_sem_equalizacao": media_magistrado_sem,
        "reducao_dispersao_magistrado_pct": reducao_dispersao_magistrado,
    }


# ---------------------------------------------------------------------------
# Analise por grupo (secao 13)
# ---------------------------------------------------------------------------

def analise_por_grupo(unidades_filtradas: pd.DataFrame, tabela_com: pd.DataFrame,
                       tabela_sem: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for grupo in GRUPOS:
        qtd_unidades = int((unidades_filtradas["classificacao"] == grupo).sum())
        grupo_com = tabela_com[tabela_com["classificacao"] == grupo]
        grupo_sem = tabela_sem[tabela_sem["classificacao"] == grupo]
        com_grupo = grupo_com["quantidade"]
        sem_grupo = grupo_sem["quantidade"]

        total_com = int(com_grupo.sum())
        total_sem = int(sem_grupo.sum())
        media_com = float(com_grupo.mean()) if len(com_grupo) else float("nan")
        media_sem = float(sem_grupo.mean()) if len(sem_grupo) else float("nan")
        mad_com = calcular_dispersao(com_grupo)["mad"] if len(com_grupo) else float("nan")
        mad_sem = calcular_dispersao(sem_grupo)["mad"] if len(sem_grupo) else float("nan")

        # Grupo de medidas ponderadas pela quantidade de magistrados, dentro do grupo de unidades.
        media_pond_com = media_ponderada_por_magistrado(grupo_com) if len(grupo_com) else float("nan")
        media_pond_sem = media_ponderada_por_magistrado(grupo_sem) if len(grupo_sem) else float("nan")
        mad_pond_com = dispersao_por_magistrado(grupo_com)["mad"] if len(grupo_com) else float("nan")
        mad_pond_sem = dispersao_por_magistrado(grupo_sem)["mad"] if len(grupo_sem) else float("nan")

        linhas.append({
            "grupo": grupo,
            "quantidade_unidades": qtd_unidades,
            "total_com_equalizacao": total_com,
            "total_sem_equalizacao": total_sem,
            "media_com_equalizacao": media_com,
            "media_sem_equalizacao": media_sem,
            "mad_com_equalizacao": mad_com,
            "mad_sem_equalizacao": mad_sem,
            "variacao_media_pct": ((media_com - media_sem) / media_sem * 100) if media_sem else float("nan"),
            "variacao_dispersao_pct": ((mad_com - mad_sem) / mad_sem * 100) if mad_sem else float("nan"),
            "media_ponderada_magistrado_com_equalizacao": media_pond_com,
            "media_ponderada_magistrado_sem_equalizacao": media_pond_sem,
            "mad_ponderada_magistrado_com_equalizacao": mad_pond_com,
            "mad_ponderada_magistrado_sem_equalizacao": mad_pond_sem,
            "variacao_media_magistrado_pct": (
                ((media_pond_com - media_pond_sem) / media_pond_sem * 100) if media_pond_sem else float("nan")
            ),
            "variacao_dispersao_magistrado_pct": (
                ((mad_pond_com - mad_pond_sem) / mad_pond_sem * 100) if mad_pond_sem else float("nan")
            ),
        })
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# Analitico do Sistema de Equalizacao (secao 14)
# ---------------------------------------------------------------------------

def _dias_periodo(filtros) -> tuple[float, float]:
    if filtros.data_inicial is not None and filtros.data_final is not None:
        dias = max((filtros.data_final - filtros.data_inicial).days + 1, 1)
    else:
        dias = 1
    semanas = max(dias / 7, 1 / 7)
    return dias, semanas


def processos_cedidos_por_unidade(processos_filtrados: pd.DataFrame, unidades_filtradas: pd.DataFrame,
                                   filtros) -> pd.DataFrame:
    validos = processos_filtrados[processos_filtrados["equalizacao_valida"]]
    dias, semanas = _dias_periodo(filtros)

    cedentes = unidades_filtradas[unidades_filtradas["classificacao"] == CLASSIFICACAO_CEDENTE]
    total_cedido = int(validos["processo_norm"].nunique())

    linhas = []
    for _, unidade in cedentes.iterrows():
        subset = validos[validos["unidade_cedente_equalizacao"] == unidade["unidade_norm"]]
        qtd = int(subset["processo_norm"].nunique())
        qtd_destinatarias_diferentes = int(subset["unidade_destinataria_equalizacao"].nunique())
        linhas.append({
            "unidade": unidade["unidade_original"],
            "unidade_norm": unidade["unidade_norm"],
            "classificacao": unidade["classificacao"],
            "quantidade_processos_cedidos": qtd,
            "percentual_do_total_cedido": (qtd / total_cedido * 100) if total_cedido else 0.0,
            "quantidade_destinatarias_diferentes": qtd_destinatarias_diferentes,
            "media_diaria": qtd / dias,
            "media_semanal": qtd / semanas,
        })
    colunas = [
        "unidade", "unidade_norm", "classificacao", "quantidade_processos_cedidos",
        "percentual_do_total_cedido", "quantidade_destinatarias_diferentes", "media_diaria", "media_semanal",
    ]
    return pd.DataFrame(linhas, columns=colunas)


def processos_destinados_por_unidade(processos_filtrados: pd.DataFrame, unidades_filtradas: pd.DataFrame,
                                      filtros) -> pd.DataFrame:
    validos = processos_filtrados[processos_filtrados["equalizacao_valida"]]
    dias, semanas = _dias_periodo(filtros)

    destinatarias = unidades_filtradas[unidades_filtradas["classificacao"] == CLASSIFICACAO_DESTINATARIA]
    total_recebido = int(validos["processo_norm"].nunique())

    linhas = []
    for _, unidade in destinatarias.iterrows():
        subset = validos[validos["unidade_destinataria_equalizacao"] == unidade["unidade_norm"]]
        qtd = int(subset["processo_norm"].nunique())
        qtd_cedentes_diferentes = int(subset["unidade_cedente_equalizacao"].nunique())
        linhas.append({
            "unidade": unidade["unidade_original"],
            "unidade_norm": unidade["unidade_norm"],
            "classificacao": unidade["classificacao"],
            "quantidade_processos_recebidos": qtd,
            "percentual_do_total_recebido": (qtd / total_recebido * 100) if total_recebido else 0.0,
            "quantidade_cedentes_diferentes": qtd_cedentes_diferentes,
            "media_diaria": qtd / dias,
            "media_semanal": qtd / semanas,
        })
    colunas = [
        "unidade", "unidade_norm", "classificacao", "quantidade_processos_recebidos",
        "percentual_do_total_recebido", "quantidade_cedentes_diferentes", "media_diaria", "media_semanal",
    ]
    return pd.DataFrame(linhas, columns=colunas)


def saldo_liquido_por_unidade(cedidos_df: pd.DataFrame, destinados_df: pd.DataFrame) -> pd.DataFrame:
    cedidos = cedidos_df[["unidade_norm", "unidade", "classificacao", "quantidade_processos_cedidos"]].rename(
        columns={"quantidade_processos_cedidos": "cedidos"})
    recebidos = destinados_df[["unidade_norm", "unidade", "classificacao", "quantidade_processos_recebidos"]].rename(
        columns={"quantidade_processos_recebidos": "recebidos"})
    fundido = pd.merge(cedidos, recebidos, on=["unidade_norm", "unidade", "classificacao"], how="outer")
    fundido["cedidos"] = fundido["cedidos"].fillna(0).astype(int)
    fundido["recebidos"] = fundido["recebidos"].fillna(0).astype(int)
    fundido["saldo_liquido"] = fundido["recebidos"] - fundido["cedidos"]
    return fundido.reset_index(drop=True)


def matriz_fluxos(processos_filtrados: pd.DataFrame) -> dict:
    validos = processos_filtrados[processos_filtrados["equalizacao_valida"]].copy()
    if validos.empty:
        return {
            "matriz": pd.DataFrame(), "rotas": pd.DataFrame(), "quantidade_pares": 0,
            "participacao_top10_pct": 0.0,
        }

    rotas = (
        validos.groupby(["unidade_cedente_equalizacao_original", "unidade_destinataria_equalizacao_original"])
        ["processo_norm"].nunique().reset_index()
        .rename(columns={
            "unidade_cedente_equalizacao_original": "unidade_cedente",
            "unidade_destinataria_equalizacao_original": "unidade_destinataria",
            "processo_norm": "quantidade",
        })
        .sort_values("quantidade", ascending=False).reset_index(drop=True)
    )
    total = int(rotas["quantidade"].sum())
    rotas["participacao_pct"] = rotas["quantidade"] / total * 100 if total else 0.0

    matriz = validos.pivot_table(
        index="unidade_cedente_equalizacao_original", columns="unidade_destinataria_equalizacao_original",
        values="processo_norm", aggfunc="nunique", fill_value=0,
    )

    top10 = rotas.head(10)
    participacao_top10 = float(top10["quantidade"].sum() / total * 100) if total else 0.0

    return {
        "matriz": matriz,
        "rotas": rotas,
        "principais_rotas": top10,
        "quantidade_pares": int(len(rotas)),
        "participacao_top10_pct": participacao_top10,
    }


# ---------------------------------------------------------------------------
# Indicadores gerenciais adicionais (secao 15)
# ---------------------------------------------------------------------------

def indicadores_adicionais(processos_filtrados: pd.DataFrame, unidades_filtradas: pd.DataFrame,
                            episodios_df: pd.DataFrame, tabela_com: pd.DataFrame,
                            tabela_sem: pd.DataFrame) -> dict:
    processos_norm_filtrados = set(processos_filtrados["processo_norm"])
    episodios_no_filtro = episodios_df[episodios_df["processo_norm"].isin(processos_norm_filtrados)] \
        if not episodios_df.empty else episodios_df

    validos = processos_filtrados[processos_filtrados["equalizacao_valida"]]

    unidades_cederam = int(validos["unidade_cedente_equalizacao"].nunique())
    unidades_receberam = int(validos["unidade_destinataria_equalizacao"].nunique())

    unidades_com_movimento = set(processos_filtrados.loc[
        processos_filtrados["unidade_final_real"] != "", "unidade_final_real"
    ])
    unidades_sem_movimento = int((~unidades_filtradas["unidade_norm"].isin(unidades_com_movimento)).sum())

    qtd_passaram_triagem = int(processos_filtrados.loc[processos_filtrados["passou_por_triagem"], "processo_norm"].nunique())

    if not episodios_no_filtro.empty:
        qtd_eq_validas = int((episodios_no_filtro["tipo_episodio"] == "VALIDA").sum())
        qtd_eq_fora_padrao = int((episodios_no_filtro["tipo_episodio"] == "FORA_PADRAO").sum())
        qtd_passagens_incompletas = int((episodios_no_filtro["tipo_episodio"] == "INCOMPLETA").sum())
    else:
        qtd_eq_validas = qtd_eq_fora_padrao = qtd_passagens_incompletas = 0

    qtd_multiplos_episodios = int(processos_filtrados.loc[
        processos_filtrados["quantidade_episodios_triagem"] > 1, "processo_norm"
    ].nunique())

    casos_novos_por_classe = processos_filtrados.groupby("classe_judicial")["processo_norm"].nunique()
    equalizados_por_classe = validos.groupby("classe_judicial")["processo_norm"].nunique()
    percentual_por_classe = pd.DataFrame({
        "classe_judicial": casos_novos_por_classe.index,
        "casos_novos": casos_novos_por_classe.values,
        "equalizados": equalizados_por_classe.reindex(casos_novos_por_classe.index, fill_value=0).values,
    })
    percentual_por_classe["percentual_equalizados"] = percentual_por_classe.apply(
        lambda r: (r["equalizados"] / r["casos_novos"] * 100) if r["casos_novos"] else 0.0, axis=1
    )

    tempo_ate_destino = (validos["data_destino_equalizacao"] - validos["data_caso_novo"]).dt.days.dropna()
    tempo_medio_ate_destino = float(tempo_ate_destino.mean()) if not tempo_ate_destino.empty else float("nan")
    tempo_mediano_ate_destino = float(tempo_ate_destino.median()) if not tempo_ate_destino.empty else float("nan")

    tempo_triagem = (validos["data_destino_equalizacao"] - validos["data_entrada_triagem"]).dt.days.dropna()
    tempo_medio_triagem = float(tempo_triagem.mean()) if not tempo_triagem.empty else float("nan")
    tempo_mediano_triagem = float(tempo_triagem.median()) if not tempo_triagem.empty else float("nan")

    casos_novos_validos = processos_filtrados[processos_filtrados["data_caso_novo"].notna()]
    evolucao_diaria = (
        casos_novos_validos.groupby(casos_novos_validos["data_caso_novo"].dt.date)["processo_norm"]
        .nunique().reset_index().rename(columns={"data_caso_novo": "data", "processo_norm": "quantidade"})
    )
    evolucao_semanal = (
        casos_novos_validos.groupby(casos_novos_validos["data_caso_novo"].dt.to_period("W").apply(lambda p: p.start_time))
        ["processo_norm"].nunique().reset_index().rename(columns={"data_caso_novo": "semana", "processo_norm": "quantidade"})
    )

    eq_validas_com_data = validos[validos["data_destino_equalizacao"].notna()]
    evolucao_eq_diaria = (
        eq_validas_com_data.groupby(eq_validas_com_data["data_destino_equalizacao"].dt.date)["processo_norm"]
        .nunique().reset_index().rename(columns={"data_destino_equalizacao": "data", "processo_norm": "quantidade"})
    )
    evolucao_eq_semanal = (
        eq_validas_com_data.groupby(
            eq_validas_com_data["data_destino_equalizacao"].dt.to_period("W").apply(lambda p: p.start_time)
        )["processo_norm"].nunique().reset_index().rename(columns={"data_destino_equalizacao": "semana", "processo_norm": "quantidade"})
    )

    distribuicao_acumulada = evolucao_diaria.sort_values("data").copy()
    if not distribuicao_acumulada.empty:
        distribuicao_acumulada["quantidade_acumulada"] = distribuicao_acumulada["quantidade"].cumsum()

    diferenca_carga = pd.merge(
        tabela_com[["unidade_norm", "unidade_original", "classificacao", "quantidade"]].rename(columns={"quantidade": "carga_real"}),
        tabela_sem[["unidade_norm", "quantidade"]].rename(columns={"quantidade": "carga_simulada"}),
        on="unidade_norm", how="outer",
    )
    diferenca_carga["diferenca"] = diferenca_carga["carga_real"] - diferenca_carga["carga_simulada"]

    return {
        "unidades_cedentes_que_cederam": unidades_cederam,
        "unidades_destinatarias_que_receberam": unidades_receberam,
        "unidades_sem_movimentacao": unidades_sem_movimento,
        "processos_passaram_por_triagem": qtd_passaram_triagem,
        "equalizacoes_validas": qtd_eq_validas,
        "equalizacoes_fora_padrao": qtd_eq_fora_padrao,
        "passagens_incompletas_triagem": qtd_passagens_incompletas,
        "processos_multiplos_episodios": qtd_multiplos_episodios,
        "percentual_equalizados_por_classe": percentual_por_classe,
        "tempo_medio_distribuicao_destino_dias": tempo_medio_ate_destino,
        "tempo_mediano_distribuicao_destino_dias": tempo_mediano_ate_destino,
        "tempo_medio_permanencia_triagem_dias": tempo_medio_triagem,
        "tempo_mediano_permanencia_triagem_dias": tempo_mediano_triagem,
        "evolucao_diaria_casos_novos": evolucao_diaria,
        "evolucao_semanal_casos_novos": evolucao_semanal,
        "evolucao_diaria_equalizacoes": evolucao_eq_diaria,
        "evolucao_semanal_equalizacoes": evolucao_eq_semanal,
        "distribuicao_acumulada": distribuicao_acumulada,
        "diferenca_carga_real_simulada": diferenca_carga,
    }


# ---------------------------------------------------------------------------
# Orquestrador
# ---------------------------------------------------------------------------

def calcular_todas_metricas(processos_filtrados: pd.DataFrame, unidades_filtradas: pd.DataFrame,
                             episodios_df: pd.DataFrame, filtros) -> dict:
    tabela_com = cenario_com_equalizacao(processos_filtrados, unidades_filtradas)
    tabela_sem = cenario_sem_equalizacao(processos_filtrados, unidades_filtradas)

    casos_novos = int(processos_filtrados["processo_norm"].nunique())
    nao_class_com = quantidade_processos_unidade_nao_classificada(processos_filtrados, unidades_filtradas, "unidade_final_real")
    nao_class_sem = quantidade_processos_unidade_nao_classificada(
        processos_filtrados, unidades_filtradas, "unidade_simulada_sem_equalizacao"
    )
    erros_consistencia = validar_totais_cenarios(casos_novos, tabela_com, tabela_sem, nao_class_com, nao_class_sem)

    disp_com = calcular_dispersao(tabela_com["quantidade"])
    disp_sem = calcular_dispersao(tabela_sem["quantidade"])
    comparacao_dispersao = comparar_dispersao(disp_sem, disp_com)

    disp_magistrado_com = dispersao_por_magistrado(tabela_com)
    disp_magistrado_sem = dispersao_por_magistrado(tabela_sem)
    comparacao_dispersao_magistrado = comparar_dispersao(disp_magistrado_sem, disp_magistrado_com)

    cards = cards_executivos(processos_filtrados, unidades_filtradas, disp_sem, disp_com,
                              disp_magistrado_sem, disp_magistrado_com)
    grupo_df = analise_por_grupo(unidades_filtradas, tabela_com, tabela_sem)

    cedidos_df = processos_cedidos_por_unidade(processos_filtrados, unidades_filtradas, filtros)
    destinados_df = processos_destinados_por_unidade(processos_filtrados, unidades_filtradas, filtros)
    saldo_df = saldo_liquido_por_unidade(cedidos_df, destinados_df)
    fluxos = matriz_fluxos(processos_filtrados)

    adicionais = indicadores_adicionais(processos_filtrados, unidades_filtradas, episodios_df, tabela_com, tabela_sem)

    return {
        "casos_novos": casos_novos,
        "erros_consistencia": erros_consistencia,
        "processos_unidade_nao_classificada_com": nao_class_com,
        "processos_unidade_nao_classificada_sem": nao_class_sem,
        "tabela_com": tabela_com,
        "tabela_sem": tabela_sem,
        "dispersao_com": disp_com,
        "dispersao_sem": disp_sem,
        "comparacao_dispersao": comparacao_dispersao,
        "dispersao_magistrado_com": disp_magistrado_com,
        "dispersao_magistrado_sem": disp_magistrado_sem,
        "comparacao_dispersao_magistrado": comparacao_dispersao_magistrado,
        "cards": cards,
        "analise_grupo": grupo_df,
        "cedidos": cedidos_df,
        "destinados": destinados_df,
        "saldo_liquido": saldo_df,
        "fluxos": fluxos,
        "adicionais": adicionais,
    }
