"""Dashboard Streamlit do Sistema de Equalizacao TRT12 (secoes 16 a 19).

Executar com:
    streamlit run app.py
"""
from __future__ import annotations

import difflib
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import streamlit as st

from config import SETTINGS
from src import charts, filters, metrics, reports
from src.formatting import formatar_data, formatar_numero, formatar_percentual
from src.loaders import ConfigError
from src.pipeline import executar_pipeline

st.set_page_config(page_title="Sistema de Equalizacao TRT12", layout="wide")


@st.cache_data(show_spinner="Consolidando dados do Sistema de Equalizacao...")
def _carregar(downloads_dir: str, output_dir: str, classificacao_dir: str, forcar: bool, _versao_cache: int):
    settings = SETTINGS
    settings.downloads_dir = Path(downloads_dir)
    settings.output_dir = Path(output_dir)
    classificacao_path = Path(classificacao_dir) if classificacao_dir else None
    return executar_pipeline(settings, classificacao_path=classificacao_path, forcar_atualizacao=forcar)


def _texto_periodo(filtros: filters.FiltrosDashboard) -> str:
    ini = formatar_data(filtros.data_inicial) if filtros.data_inicial else "inicio da base"
    fim = formatar_data(filtros.data_final) if filtros.data_final else "fim da base"
    base = {
        filters.BASE_TEMPORAL_CASO_NOVO: "ingresso do caso novo",
        filters.BASE_TEMPORAL_CONCLUSAO_EQUALIZACAO: "conclusao da equalizacao",
        filters.BASE_TEMPORAL_ULTIMO_MOVIMENTO: "ultimo movimento",
    }[filtros.base_temporal]
    return f"{ini} a {fim} (base: {base})"


def _texto_filtros(filtros: filters.FiltrosDashboard) -> str:
    partes = []
    if filtros.grupos:
        partes.append(f"grupos={','.join(filtros.grupos)}")
    if filtros.unidades:
        partes.append(f"{len(filtros.unidades)} unidade(s) selecionada(s)")
    partes.append(f"papel={filtros.papel_unidade}")
    if filtros.classe_judicial:
        partes.append(f"{len(filtros.classe_judicial)} classe(s)")
    if filtros.municipio_sede:
        partes.append(f"{len(filtros.municipio_sede)} municipio(s)")
    if filtros.situacao_equalizacao:
        partes.append(f"situacao={','.join(filtros.situacao_equalizacao)}")
    if filtros.com_anomalia:
        partes.append(f"anomalia={filtros.com_anomalia}")
    return "; ".join(partes) if partes else "nenhum filtro adicional"


def _barra_lateral(resultado: dict):
    st.sidebar.title("Filtros")

    if st.sidebar.button("Atualizar dados", use_container_width=True):
        st.session_state["_versao_cache"] = st.session_state.get("_versao_cache", 0) + 1
        st.cache_data.clear()
        st.rerun()

    processos_df = resultado["processos_df"]
    unidades_df = resultado["unidades_permanentes_df"]

    datas_validas = processos_df["data_caso_novo"].dropna()
    data_min = datas_validas.min().date() if not datas_validas.empty else date.today()
    data_max = datas_validas.max().date() if not datas_validas.empty else date.today()

    st.sidebar.subheader("Periodo")
    intervalo = st.sidebar.date_input("Intervalo de datas", value=(data_min, data_max),
                                       min_value=data_min, max_value=data_max)
    if isinstance(intervalo, tuple) and len(intervalo) == 2:
        data_inicial, data_final = intervalo
    else:
        data_inicial, data_final = data_min, data_max

    rotulos_base = {
        "Ingresso do caso novo": filters.BASE_TEMPORAL_CASO_NOVO,
        "Conclusao da equalizacao": filters.BASE_TEMPORAL_CONCLUSAO_EQUALIZACAO,
        "Ultimo movimento": filters.BASE_TEMPORAL_ULTIMO_MOVIMENTO,
    }
    rotulo_base = st.sidebar.selectbox("Base temporal do filtro", list(rotulos_base.keys()))
    base_temporal = rotulos_base[rotulo_base]

    st.sidebar.subheader("Grupo de unidades")
    grupos = st.sidebar.multiselect("Classificacao (logica OU)", list(metrics.GRUPOS))

    st.sidebar.subheader("Unidade")
    unidades_disponiveis = unidades_df if not grupos else unidades_df[unidades_df["classificacao"].isin(grupos)]
    opcoes_unidade = dict(zip(unidades_disponiveis["unidade_original"], unidades_disponiveis["unidade_norm"]))
    selecao_unidade = st.sidebar.multiselect("Unidade (logica OU)", list(opcoes_unidade.keys()))
    unidades_norm = [opcoes_unidade[nome] for nome in selecao_unidade]

    st.sidebar.subheader("Papel da unidade")
    papel_unidade = st.sidebar.selectbox("Dimensao usada no filtro de unidade", filters.PAPEIS_UNIDADE)

    with st.sidebar.expander("Filtros complementares"):
        classes = st.multiselect("Classe judicial", sorted(processos_df["classe_judicial"].dropna().unique()))
        municipios = st.multiselect("Municipio sede", sorted(processos_df["municipio_sede"].dropna().unique()))
        tipos_mov = st.multiselect("Tipo de movimentacao (aproximado)", ["DISTRIBUICAO", "REDISTRIBUICAO"])
        situacoes = st.multiselect("Situacao da equalizacao", [
            filters.SITUACAO_EQUALIZADO_VALIDO, filters.SITUACAO_FORA_PADRAO,
            filters.SITUACAO_INCOMPLETA, filters.SITUACAO_NAO_EQUALIZADO,
        ])
        anomalia = st.radio("Processos com anomalia", ["Todos", "Somente com anomalia", "Somente sem anomalia"])
        com_anomalia = {"Todos": None, "Somente com anomalia": "COM", "Somente sem anomalia": "SEM"}[anomalia]

    filtros = filters.FiltrosDashboard(
        data_inicial=pd.Timestamp(data_inicial), data_final=pd.Timestamp(data_final),
        base_temporal=base_temporal, grupos=grupos, unidades=unidades_norm, papel_unidade=papel_unidade,
        classe_judicial=classes, municipio_sede=municipios, tipo_movimentacao=tipos_mov,
        situacao_equalizacao=situacoes, com_anomalia=com_anomalia,
    )
    return filtros


def _pagina_visao_executiva(m, ctx):
    st.header("Visao Executiva")
    if m["erros_consistencia"]:
        for erro in m["erros_consistencia"]:
            st.error(erro)
    if m["processos_unidade_nao_classificada_com"] or m["processos_unidade_nao_classificada_sem"]:
        st.info(
            f"{m['processos_unidade_nao_classificada_com']} processo(s) estao em unidades nao classificadas no "
            "cenario com equalizacao e nao aparecem nas tabelas por unidade (contam em 'casos novos' e estao "
            "listados na pagina Qualidade dos Dados)."
        )

    cards = m["cards"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Casos novos (processos distintos)", formatar_numero(cards["casos_novos"]))
    c2.metric("Processos equalizados", formatar_numero(cards["processos_equalizados"]))
    c3.metric("% processos equalizados", formatar_percentual(cards["percentual_processos_equalizados"]))
    c4.metric("Reducao da dispersao (MAD)", formatar_percentual(cards["reducao_dispersao_pct"]))

    c5, c6, c7 = st.columns(3)
    c5.metric("Media por unidade cedente", formatar_numero(cards["media_processos_por_unidade_cedente"], 2))
    c6.metric("Media por unidade neutra", formatar_numero(cards["media_processos_por_unidade_neutra"], 2))
    c7.metric("Media por unidade destinataria", formatar_numero(cards["media_processos_por_unidade_destinataria"], 2))

    st.subheader("Medias ponderadas por magistrado")
    if pd.isna(m["dispersao_magistrado_com"]["media"]) and pd.isna(m["dispersao_magistrado_sem"]["media"]):
        st.info(
            "Nenhuma unidade do filtro atual possui quantidade de magistrados valida. Adicione a coluna "
            "'Quantidade de Magistrados' no arquivo de classificacao de unidades para habilitar estas medidas."
        )
    else:
        c8, c9, c10 = st.columns(3)
        c8.metric("Media ponderada por magistrado (com equalizacao)",
                  formatar_numero(cards["media_ponderada_magistrado_com_equalizacao"], 2))
        c9.metric("Media ponderada por magistrado (sem equalizacao)",
                  formatar_numero(cards["media_ponderada_magistrado_sem_equalizacao"], 2))
        c10.metric("Reducao da dispersao por magistrado (MAD)",
                   formatar_percentual(cards["reducao_dispersao_magistrado_pct"]))

    st.plotly_chart(charts.grafico_comparativo_barras(m["tabela_com"], m["tabela_sem"],
                                                        periodo_texto=ctx["periodo_texto"], filtros_texto=ctx["filtros_texto"]),
                     use_container_width=True)
    st.plotly_chart(charts.grafico_distancia_media(m["tabela_com"], periodo_texto=ctx["periodo_texto"],
                                                     filtros_texto=ctx["filtros_texto"]), use_container_width=True)

    st.subheader("Comparativo por unidade -- por magistrado")
    st.plotly_chart(charts.grafico_comparativo_barras_por_magistrado(
        m["tabela_com"], m["tabela_sem"], periodo_texto=ctx["periodo_texto"], filtros_texto=ctx["filtros_texto"]
    ), use_container_width=True)
    st.plotly_chart(charts.grafico_distancia_media_por_magistrado(
        m["tabela_com"], periodo_texto=ctx["periodo_texto"], filtros_texto=ctx["filtros_texto"]
    ), use_container_width=True)

    st.subheader("Ranking de proximidade/afastamento da media (cenario com equalizacao)")
    ranking = m["tabela_com"].assign(distancia_abs=lambda d: d["diferenca_absoluta_media"].abs()) \
        .sort_values("distancia_abs")
    st.dataframe(ranking[["unidade_original", "classificacao", "quantidade", "diferenca_absoluta_media",
                           "diferenca_percentual_media"]], use_container_width=True)

    st.subheader("Ranking de proximidade/afastamento da media ponderada por magistrado")
    ranking_mag = m["tabela_com"].dropna(subset=["diferenca_absoluta_media_magistrado"]) \
        .assign(distancia_abs=lambda d: d["diferenca_absoluta_media_magistrado"].abs()) \
        .sort_values("distancia_abs")
    if ranking_mag.empty:
        st.info("Sem dados suficientes de quantidade de magistrados para montar este ranking.")
    else:
        st.dataframe(ranking_mag[["unidade_original", "classificacao", "quantidade_magistrados",
                                   "processos_por_magistrado", "diferenca_absoluta_media_magistrado",
                                   "diferenca_percentual_media_magistrado"]], use_container_width=True)


def _pagina_comparativo(m, ctx):
    st.header("Comparativo com e sem Sistema de Equalizacao")
    col1, col2 = st.columns(2)
    col1.subheader("Com equalizacao (unidade final real)")
    col1.dataframe(m["tabela_com"], use_container_width=True)
    col2.subheader("Sem equalizacao (simulado)")
    col2.dataframe(m["tabela_sem"], use_container_width=True)

    st.plotly_chart(charts.grafico_dispersao_45graus(m["tabela_com"], m["tabela_sem"],
                                                        periodo_texto=ctx["periodo_texto"], filtros_texto=ctx["filtros_texto"]),
                     use_container_width=True)
    st.plotly_chart(charts.boxplot_por_grupo(m["tabela_com"], m["tabela_sem"],
                                              periodo_texto=ctx["periodo_texto"], filtros_texto=ctx["filtros_texto"]),
                     use_container_width=True)

    st.subheader("Indicadores de dispersao")
    disp_com, disp_sem, comp = m["dispersao_com"], m["dispersao_sem"], m["comparacao_dispersao"]
    disp_df = pd.DataFrame([
        {"Medida": k, "Sem equalizacao": disp_sem[k], "Com equalizacao": disp_com[k]}
        for k in ["media", "mad", "desvio_padrao", "coeficiente_variacao", "amplitude", "qtd_acima_media", "qtd_abaixo_media"]
    ])
    st.dataframe(disp_df, use_container_width=True)
    st.write(f"Reducao da MAD: {formatar_percentual(comp['reducao_mad_pct'])} | "
             f"Reducao do desvio-padrao: {formatar_percentual(comp['reducao_desvio_padrao_pct'])} | "
             f"Reducao do CV: {formatar_percentual(comp['reducao_coeficiente_variacao_pct'])} | "
             f"Situacao: {'melhora' if comp['melhora'] else 'piora'}")

    st.subheader("Medidas ponderadas por magistrado")
    disp_mag_com, disp_mag_sem = m["dispersao_magistrado_com"], m["dispersao_magistrado_sem"]
    comp_mag = m["comparacao_dispersao_magistrado"]
    if pd.isna(disp_mag_com["media"]) and pd.isna(disp_mag_sem["media"]):
        st.info(
            "Nenhuma unidade do filtro atual possui quantidade de magistrados valida. Adicione a coluna "
            "'Quantidade de Magistrados' no arquivo de classificacao de unidades para habilitar estas medidas."
        )
    else:
        st.plotly_chart(charts.grafico_dispersao_45graus_por_magistrado(
            m["tabela_com"], m["tabela_sem"], periodo_texto=ctx["periodo_texto"], filtros_texto=ctx["filtros_texto"]
        ), use_container_width=True)
        st.plotly_chart(charts.boxplot_por_grupo_por_magistrado(
            m["tabela_com"], m["tabela_sem"], periodo_texto=ctx["periodo_texto"], filtros_texto=ctx["filtros_texto"]
        ), use_container_width=True)

        disp_mag_df = pd.DataFrame([
            {"Medida": k, "Sem equalizacao": disp_mag_sem[k], "Com equalizacao": disp_mag_com[k]}
            for k in ["media", "mad", "desvio_padrao", "coeficiente_variacao", "amplitude", "qtd_acima_media", "qtd_abaixo_media"]
        ])
        st.caption("Media = total de processos / total de magistrados das unidades com quantidade de "
                   "magistrados informada (media ponderada do sistema, nao a media simples das taxas por unidade).")
        st.dataframe(disp_mag_df, use_container_width=True)
        st.write(f"Reducao da MAD por magistrado: {formatar_percentual(comp_mag['reducao_mad_pct'])} | "
                 f"Reducao do desvio-padrao: {formatar_percentual(comp_mag['reducao_desvio_padrao_pct'])} | "
                 f"Reducao do CV: {formatar_percentual(comp_mag['reducao_coeficiente_variacao_pct'])} | "
                 f"Situacao: {'melhora' if comp_mag['melhora'] else 'piora'}")

    st.subheader("Analise por grupo de unidades")
    st.dataframe(m["analise_grupo"], use_container_width=True)


def _pagina_cedentes(m, ctx):
    st.header("Cedentes")
    st.dataframe(m["cedidos"].drop(columns=["unidade_norm"], errors="ignore"), use_container_width=True)
    if not m["cedidos"].empty:
        st.plotly_chart(charts.grafico_barras_unidade(m["cedidos"], "quantidade_processos_cedidos", "unidade",
                                                        "Processos cedidos por unidade", periodo_texto=ctx["periodo_texto"],
                                                        filtros_texto=ctx["filtros_texto"]), use_container_width=True)
    st.subheader("Saldo liquido")
    st.dataframe(m["saldo_liquido"][m["saldo_liquido"]["classificacao"] == "CEDENTE"], use_container_width=True)


def _pagina_destinatarias(m, ctx):
    st.header("Destinatarias")
    st.dataframe(m["destinados"].drop(columns=["unidade_norm"], errors="ignore"), use_container_width=True)
    if not m["destinados"].empty:
        st.plotly_chart(charts.grafico_barras_unidade(m["destinados"], "quantidade_processos_recebidos", "unidade",
                                                        "Processos recebidos por unidade", periodo_texto=ctx["periodo_texto"],
                                                        filtros_texto=ctx["filtros_texto"]), use_container_width=True)
    st.subheader("Saldo liquido")
    st.dataframe(m["saldo_liquido"][m["saldo_liquido"]["classificacao"] == "DESTINATARIA"], use_container_width=True)


def _pagina_fluxos(m, ctx):
    st.header("Fluxos de Equalizacao")
    fluxos = m["fluxos"]
    c1, c2 = st.columns(2)
    c1.metric("Pares cedente-destinataria", formatar_numero(fluxos["quantidade_pares"]))
    c2.metric("Participacao das 10 maiores rotas", formatar_percentual(fluxos["participacao_top10_pct"]))

    st.plotly_chart(charts.mapa_calor_fluxos(fluxos["matriz"], periodo_texto=ctx["periodo_texto"],
                                              filtros_texto=ctx["filtros_texto"]), use_container_width=True)
    st.plotly_chart(charts.sankey_fluxos(fluxos["rotas"], periodo_texto=ctx["periodo_texto"],
                                          filtros_texto=ctx["filtros_texto"]), use_container_width=True)

    st.subheader("Principais rotas")
    st.dataframe(fluxos["rotas"], use_container_width=True)


def _pagina_evolucao(m, ctx):
    st.header("Evolucao Temporal")
    a = m["adicionais"]
    st.plotly_chart(charts.grafico_evolucao(a["evolucao_diaria_casos_novos"], a["evolucao_semanal_casos_novos"],
                                             "Evolucao de casos novos", periodo_texto=ctx["periodo_texto"],
                                             filtros_texto=ctx["filtros_texto"]), use_container_width=True)
    st.plotly_chart(charts.grafico_evolucao(a["evolucao_diaria_equalizacoes"], a["evolucao_semanal_equalizacoes"],
                                             "Evolucao de equalizacoes validas", periodo_texto=ctx["periodo_texto"],
                                             filtros_texto=ctx["filtros_texto"]), use_container_width=True)

    if not a["distribuicao_acumulada"].empty:
        st.subheader("Distribuicao acumulada de casos novos")
        st.line_chart(a["distribuicao_acumulada"].set_index("data")["quantidade_acumulada"])

    c1, c2 = st.columns(2)
    c1.metric("Tempo medio distribuicao -> destino (dias)", formatar_numero(a["tempo_medio_distribuicao_destino_dias"], 1))
    c1.metric("Tempo mediano distribuicao -> destino (dias)", formatar_numero(a["tempo_mediano_distribuicao_destino_dias"], 1))
    c2.metric("Tempo medio na triagem (dias)", formatar_numero(a["tempo_medio_permanencia_triagem_dias"], 1))
    c2.metric("Tempo mediano na triagem (dias)", formatar_numero(a["tempo_mediano_permanencia_triagem_dias"], 1))

    st.subheader("Diferenca entre carga real e carga simulada por unidade")
    st.dataframe(a["diferenca_carga_real_simulada"], use_container_width=True)


def _pagina_classes(m, ctx):
    st.header("Classes Judiciais")
    df = m["adicionais"]["percentual_equalizados_por_classe"].sort_values("casos_novos", ascending=False)
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        import plotly.express as px
        fig = px.bar(df.head(20), x="classe_judicial", y="percentual_equalizados")
        fig = charts.aplicar_metadados(fig, "Percentual de processos equalizados por classe judicial",
                                        ctx["periodo_texto"], ctx["filtros_texto"], unidade_medida="% de processos")
        st.plotly_chart(fig, use_container_width=True)


def _pagina_qualidade(resultado, ctx):
    st.header("Qualidade dos Dados")
    qualidade = resultado["qualidade"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Registros lidos", formatar_numero(qualidade["quantidade_registros_lidos"]))
    c1.metric("Arquivos processados", formatar_numero(qualidade["quantidade_arquivos"]))
    c2.metric("Registros validos", formatar_numero(qualidade["registros_validos"]))
    c2.metric("Duplicidades removidas", formatar_numero(qualidade["duplicidades_removidas"]))
    c3.metric("Processos distintos", formatar_numero(qualidade["processos_distintos"]))
    c3.metric("Unidades nao classificadas", formatar_numero(qualidade["unidades_nao_classificadas"]))
    st.metric("Registros RESTITUIDO (desconsiderados de todas as analises)",
              formatar_numero(qualidade.get("registros_restituidos", 0)))

    st.write(f"Periodo dos dados: {formatar_data(qualidade['data_minima'])} a {formatar_data(qualidade['data_maxima'])}")

    st.subheader("Completude por coluna")
    completude_df = pd.DataFrame([
        {"coluna": k, "percentual_completo": v} for k, v in qualidade["percentual_completude_por_coluna"].items()
    ])
    st.dataframe(completude_df, use_container_width=True)

    if resultado["avisos"]:
        st.subheader("Avisos")
        for aviso in resultado["avisos"]:
            st.warning(aviso)

    st.subheader("Anomalias")
    anomalias_df = resultado["anomalias_df"]
    if not anomalias_df.empty:
        tipos = st.multiselect("Filtrar por tipo de anomalia", sorted(anomalias_df["tipo_anomalia"].unique()))
        exibir = anomalias_df[anomalias_df["tipo_anomalia"].isin(tipos)] if tipos else anomalias_df
        st.dataframe(exibir, use_container_width=True)
        st.download_button("Baixar anomalias (CSV)", exibir.to_csv(index=False).encode("utf-8-sig"),
                            file_name="anomalias.csv")
    else:
        st.info("Nenhuma anomalia registrada.")

    st.subheader("Unidades nao classificadas")
    nc_df = resultado["nao_classificadas_df"]
    if not nc_df.empty:
        nomes_oficiais = resultado["unidades_permanentes_df"]["unidade_original"].tolist()
        sugestoes = []
        for nome in nc_df["unidade"]:
            proximos = difflib.get_close_matches(nome, nomes_oficiais, n=3, cutoff=0.6)
            sugestoes.append(", ".join(proximos) if proximos else "-")
        nc_exibicao = nc_df.copy()
        nc_exibicao["sugestoes_de_correspondencia"] = sugestoes
        st.dataframe(nc_exibicao, use_container_width=True)
        st.caption("As sugestoes sao apenas informativas; nenhuma correspondencia e aplicada automaticamente.")
    else:
        st.info("Todas as unidades encontradas nos CSVs foram classificadas.")


def _pagina_consulta_processo(resultado, ctx):
    st.header("Consulta por Processo")
    numero = st.text_input("Numero do processo")
    if not numero:
        return

    from src.normalization import normalize_processo_numero, normalize_text
    numero_norm = normalize_text(normalize_processo_numero(numero))

    movimentos_df = resultado["movimentos_df"]
    processos_df = resultado["processos_df"]

    historico = movimentos_df[movimentos_df["processo_norm"] == numero_norm].sort_values("sequencia_movimento") \
        if "sequencia_movimento" in movimentos_df.columns else movimentos_df[movimentos_df["processo_norm"] == numero_norm]
    resumo = processos_df[processos_df["processo_norm"] == numero_norm]

    if historico.empty:
        st.warning("Processo nao encontrado na base consolidada.")
        return

    linha = resumo.iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Unidade final real", linha["unidade_final_real_original"] or "-")
    c1.metric("Unidade de distribuicao inicial", linha["unidade_distribuicao_inicial_original"] or "-")
    c2.metric("Unidade cedente (equalizacao)", linha["unidade_cedente_equalizacao_original"] or "-")
    c2.metric("Unidade destinataria (equalizacao)", linha["unidade_destinataria_equalizacao_original"] or "-")
    c3.metric("Unidade simulada sem equalizacao", linha["unidade_simulada_sem_equalizacao_original"] or "-")
    c3.metric("Situacao", "VALIDA" if linha["equalizacao_valida"] else ("DETECTADA" if linha["equalizacao_detectada"] else "NAO EQUALIZADO"))

    st.subheader("Historico cronologico")
    colunas = ["sequencia_movimento", "data", "indicador_norm", "orgao_julgador_original", "classe_judicial_original",
               "unidade_e_triagem", "arquivo_origem", "numero_linha_arquivo"]
    colunas_existentes = [c for c in colunas if c in historico.columns]
    st.dataframe(historico[colunas_existentes], use_container_width=True)

    anomalias_processo = resultado["anomalias_df"]
    anomalias_processo = anomalias_processo[anomalias_processo["processo"] == linha["processo"]]
    st.subheader("Anomalias encontradas")
    if not anomalias_processo.empty:
        st.dataframe(anomalias_processo, use_container_width=True)
    else:
        st.info("Nenhuma anomalia registrada para este processo.")


_METODOLOGIA_MD = """
### Metodologia

**Reconstrucao do historico**: o historico cronologico completo de cada processo e reconstruido antes de qualquer filtro,
ordenando os movimentos por data, data do arquivo, ordem do arquivo e numero da linha.

**Deteccao de equalizacao**: uma equalizacao e detectada quando o historico contem a sequencia
`UNIDADE PERMANENTE -> UNIDADE DE TRIAGEM -> UNIDADE PERMANENTE`. E valida quando a origem e CEDENTE, o destino e
DESTINATARIA, e os dois movimentos de entrada (na triagem e no destino) sao redistribuicoes.

**Cenario com equalizacao**: cada processo e contado na sua `unidade_final_real` (ultima unidade permanente do historico).

**Cenario sem equalizacao (simulado)**: processos com equalizacao valida sao recontados na `unidade_cedente_equalizacao`
(unidade imediatamente anterior a triagem); os demais processos permanecem na `unidade_final_real`. Os dois cenarios
sempre somam a mesma quantidade total de processos distintos.

**Dispersao**: a medida principal e a MAD (distancia media absoluta da media). Tambem sao apresentados desvio-padrao
populacional, coeficiente de variacao e amplitude.

**Convencoes de contagem**: 'processo' e sempre COUNT DISTINCT do numero de processo; 'movimentacao' conta linhas de
movimentacao; 'episodio' conta episodios de passagem por triagem (podem existir varios por processo).
"""


def _pagina_metodologia():
    st.header("Metodologia")
    st.markdown(_METODOLOGIA_MD)


def main():
    st.sidebar.header("Sistema de Equalizacao TRT12")

    versao_cache = st.session_state.get("_versao_cache", 0)
    try:
        resultado = _carregar(str(SETTINGS.downloads_dir), str(SETTINGS.output_dir),
                               str(SETTINGS.classificacao_path() or ""), False, versao_cache)
    except ConfigError as erro:
        st.error(str(erro))
        st.stop()
        return

    filtros = _barra_lateral(resultado)
    processos_filtrados, unidades_filtradas = filters.aplicar_filtros(
        resultado["processos_df"], resultado["unidades_permanentes_df"], filtros
    )
    metricas = metrics.calcular_todas_metricas(processos_filtrados, unidades_filtradas, resultado["episodios_df"], filtros)

    ctx = {
        "periodo_texto": _texto_periodo(filtros),
        "filtros_texto": _texto_filtros(filtros),
    }

    if st.sidebar.button("Gerar relatorio DOCX", use_container_width=True):
        with st.spinner("Gerando relatorio..."):
            caminho = reports.gerar_relatorio_docx(
                SETTINGS.saida("relatorio_docx"), filtros=filtros, metricas=metricas,
                processos_filtrados=processos_filtrados, unidades_filtradas=unidades_filtradas,
                arquivos_utilizados=resultado["arquivos_utilizados"], qualidade=resultado["qualidade"],
                anomalias_df=resultado["anomalias_df"], periodo_texto=ctx["periodo_texto"],
                filtros_texto=ctx["filtros_texto"], data_geracao=datetime.now(),
            )
        with open(caminho, "rb") as f:
            st.sidebar.download_button("Baixar relatorio DOCX", f.read(), file_name=caminho.name)

    caminho_excel = resultado["excel_consolidado"]
    if caminho_excel.exists():
        with open(caminho_excel, "rb") as f:
            st.sidebar.download_button(
                "Baixar Excel consolidado (base completa)", f.read(), file_name=caminho_excel.name,
                help="Todos os processos e movimentacoes da base consolidada, sem os filtros da barra lateral.",
                use_container_width=True,
            )

    paginas = {
        "Visao Executiva": lambda: _pagina_visao_executiva(metricas, ctx),
        "Comparativo com e sem Equalizacao": lambda: _pagina_comparativo(metricas, ctx),
        "Cedentes": lambda: _pagina_cedentes(metricas, ctx),
        "Destinatarias": lambda: _pagina_destinatarias(metricas, ctx),
        "Fluxos de Equalizacao": lambda: _pagina_fluxos(metricas, ctx),
        "Evolucao Temporal": lambda: _pagina_evolucao(metricas, ctx),
        "Classes Judiciais": lambda: _pagina_classes(metricas, ctx),
        "Qualidade dos Dados": lambda: _pagina_qualidade(resultado, ctx),
        "Consulta por Processo": lambda: _pagina_consulta_processo(resultado, ctx),
        "Metodologia": _pagina_metodologia,
    }
    pagina_selecionada = st.sidebar.radio("Pagina", list(paginas.keys()))
    paginas[pagina_selecionada]()


if __name__ == "__main__":
    main()
