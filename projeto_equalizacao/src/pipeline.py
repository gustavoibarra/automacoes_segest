"""Orquestracao completa da pipeline de consolidacao (secoes 1 a 10, 21 a
23). Usado tanto por main.py (linha de comando) quanto por app.py
(Streamlit), garantindo que ambos produzam exatamente os mesmos dados.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from src import anomalies, equalization, exports, histories, loaders, metrics, validation
from src.loaders import ConfigError
from src.normalization import INDICADOR_RESTITUIDO


def _construir_nao_classificadas(df_dedup: pd.DataFrame, unidades_permanentes_norm: set[str],
                                  palavra_triagem: str) -> pd.DataFrame:
    mascara = (
        (df_dedup["orgao_norm"] != "")
        & (~df_dedup["orgao_norm"].isin(unidades_permanentes_norm))
        & (~df_dedup["orgao_norm"].str.contains(palavra_triagem, na=False))
    )
    subset = df_dedup[mascara]
    if subset.empty:
        return pd.DataFrame(columns=[
            "unidade", "unidade_norm", "quantidade_movimentos", "processos_distintos",
            "arquivo_exemplo", "linha_exemplo",
        ])
    agrupado = subset.groupby(["orgao_norm", "orgao_julgador_original"]).agg(
        quantidade_movimentos=("processo", "size"),
        processos_distintos=("processo_norm", "nunique"),
        arquivo_exemplo=("arquivo_origem", "first"),
        linha_exemplo=("numero_linha_arquivo", "first"),
    ).reset_index().rename(columns={"orgao_julgador_original": "unidade", "orgao_norm": "unidade_norm"})
    return agrupado.sort_values("quantidade_movimentos", ascending=False).reset_index(drop=True)


def _qualidade_meta_path(settings) -> Path:
    return settings.output_dir / "_qualidade_meta.json"


def _serializar_qualidade(qualidade: dict) -> dict:
    copia = dict(qualidade)
    for chave in ("data_minima", "data_maxima"):
        valor = copia.get(chave)
        copia[chave] = None if valor is None or pd.isna(valor) else pd.Timestamp(valor).isoformat()
    return copia


def _desserializar_qualidade(copia: dict) -> dict:
    for chave in ("data_minima", "data_maxima"):
        valor = copia.get(chave)
        copia[chave] = pd.Timestamp(valor) if valor else None
    return copia


def executar_pipeline(settings, *, classificacao_path: Path | None = None, forcar_atualizacao: bool = False
                       ) -> dict:
    """Executa (ou recupera do cache) a consolidacao completa.

    Retorna um dict com: movimentos_df, processos_df, unidades_permanentes_df,
    episodios_df, anomalias_df, nao_classificadas_df, qualidade, avisos,
    arquivos_utilizados, usou_cache.
    """
    caminho_classificacao = classificacao_path or settings.classificacao_path()
    if caminho_classificacao is None:
        raise ConfigError(
            f"Arquivo de classificacao de unidades nao encontrado. Nomes esperados: "
            f"{list(settings.classificacao_candidatos)} na pasta {settings.base_dir}."
        )

    assinatura = exports.assinatura_entrada(settings.downloads_dir, caminho_classificacao)
    arquivos_obrigatorios = [
        settings.saida("movimentacoes_parquet"), settings.saida("processos_parquet"),
        settings.saida("episodios_csv"), settings.saida("anomalias_csv"), settings.saida("nao_classificadas_csv"),
        settings.saida("consolidado_excel"), _qualidade_meta_path(settings),
    ]

    usar_cache = (not forcar_atualizacao) and exports.cache_valido(
        settings.output_dir, settings.cache_meta_filename, assinatura, arquivos_obrigatorios
    )

    unidades_permanentes_df, avisos_classificacao = loaders.carregar_classificacao_unidades(
        caminho_classificacao, palavra_triagem=settings.palavra_triagem
    )
    avisos = list(avisos_classificacao)
    if len(unidades_permanentes_df) != settings.quantidade_unidades_esperada:
        avisos.append(
            f"Atencao: foram encontradas {len(unidades_permanentes_df)} unidades permanentes, "
            f"quantidade diferente da esperada ({settings.quantidade_unidades_esperada}). "
            "A execucao continuara normalmente."
        )

    if usar_cache:
        dados = exports.carregar_saidas_cacheadas(settings)
        meta_qualidade = json.loads(_qualidade_meta_path(settings).read_text(encoding="utf-8"))
        return {
            "movimentos_df": dados["movimentos_df"],
            "processos_df": dados["processos_df"],
            "unidades_permanentes_df": unidades_permanentes_df,
            "episodios_df": dados["episodios_df"],
            "anomalias_df": dados["anomalias_df"],
            "nao_classificadas_df": dados["nao_classificadas_df"],
            "qualidade": _desserializar_qualidade(meta_qualidade["qualidade"]),
            "avisos": meta_qualidade.get("avisos", avisos),
            "arquivos_utilizados": meta_qualidade.get("arquivos_utilizados", []),
            "excel_consolidado": settings.saida("consolidado_excel"),
            "usou_cache": True,
        }

    # ---- Reprocessamento completo --------------------------------------
    df_bruto, arquivos_utilizados = loaders.carregar_todos_movimentos(
        settings.downloads_dir, settings.colunas_csv_esperadas, encoding=settings.csv_encoding
    )
    df_bruto = validation.padronizar_colunas(df_bruto)
    df_bruto = validation.normalizar_movimentos(df_bruto)

    unidades_permanentes_norm = set(unidades_permanentes_df["unidade_norm"])

    # Movimentacoes com indicador RESTITUIDO ('Restituido Por Redistribuicao')
    # sao mantidas integralmente no historico completo (para rastreabilidade),
    # mas excluidas de toda e qualquer analise: deteccao de anomalias de linha,
    # resumo por processo, deteccao de equalizacao e unidades nao classificadas.
    df_bruto_analise = df_bruto[df_bruto["indicador_norm"] != INDICADOR_RESTITUIDO]
    anomalias_linha = validation.detectar_anomalias_linha(
        df_bruto_analise, unidades_permanentes_norm, palavra_triagem=settings.palavra_triagem
    )

    df_dedup, anomalias_dup = validation.deduplicar_movimentos(df_bruto)

    historico_df, anomalias_ordem = histories.reconstruir_historico(df_dedup, palavra_triagem=settings.palavra_triagem)
    historico_analise_df = histories.filtrar_para_analise(historico_df)

    resumo_processos_df, anomalias_resumo = histories.derivar_resumo_processos(historico_analise_df, unidades_permanentes_norm)

    episodios_df, campos_equalizacao_df, anomalias_equalizacao = equalization.detectar_equalizacoes(
        historico_analise_df, unidades_permanentes_df
    )

    processos_df = pd.merge(resumo_processos_df, campos_equalizacao_df, on="processo_norm", how="left")
    processos_df = equalization.calcular_unidade_simulada_sem_equalizacao(processos_df)
    processos_df = metrics.enriquecer_classificacoes(processos_df, unidades_permanentes_df)

    todas_anomalias = anomalias_linha + anomalias_dup + anomalias_ordem + anomalias_resumo + anomalias_equalizacao
    anomalias_df = pd.DataFrame(todas_anomalias, columns=[
        "processo", "tipo_anomalia", "descricao", "arquivo_origem", "numero_linha_arquivo",
    ])

    processos_com_anomalia = set(anomalias_df["processo"]) if not anomalias_df.empty else set()
    processos_df["tem_anomalia"] = processos_df["processo"].isin(processos_com_anomalia)

    nao_classificadas_df = _construir_nao_classificadas(
        historico_analise_df, unidades_permanentes_norm, settings.palavra_triagem
    )

    qualidade = validation.relatorio_qualidade(df_bruto, historico_df, anomalias_df, nao_classificadas_df, arquivos_utilizados)
    qualidade["registros_restituidos"] = int((historico_df["indicador_norm"] == INDICADOR_RESTITUIDO).sum())

    comparativo_df = pd.concat([
        metrics.tabela_por_unidade(unidades_permanentes_df, processos_df, "unidade_final_real").assign(cenario="COM_EQUALIZACAO"),
        metrics.tabela_por_unidade(unidades_permanentes_df, processos_df, "unidade_simulada_sem_equalizacao").assign(cenario="SEM_EQUALIZACAO"),
    ], ignore_index=True)

    fluxos_info = metrics.matriz_fluxos(processos_df)
    fluxos_df = fluxos_info["rotas"]

    exports.escrever_saidas(
        settings, historico_df, processos_df, episodios_df, comparativo_df, fluxos_df, anomalias_df, nao_classificadas_df,
    )
    exports.escrever_excel_consolidado(
        settings, historico_df, processos_df, episodios_df, comparativo_df, fluxos_df, anomalias_df,
        nao_classificadas_df, qualidade=qualidade, avisos=avisos, arquivos_utilizados=arquivos_utilizados,
    )
    exports.salvar_cache_meta(settings.output_dir, settings.cache_meta_filename, assinatura)

    meta_qualidade = {
        "qualidade": _serializar_qualidade(qualidade),
        "avisos": avisos,
        "arquivos_utilizados": arquivos_utilizados,
    }
    _qualidade_meta_path(settings).write_text(json.dumps(meta_qualidade, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    log_linhas = [
        f"Arquivos processados: {len(arquivos_utilizados)}",
        f"Registros lidos: {qualidade['quantidade_registros_lidos']}",
        f"Registros validos apos deduplicacao: {qualidade['registros_validos']}",
        f"Duplicidades removidas: {qualidade['duplicidades_removidas']}",
        f"Processos distintos: {qualidade['processos_distintos']}",
        f"Registros RESTITUIDO (desconsiderados de todas as analises): {qualidade['registros_restituidos']}",
        f"Unidades permanentes carregadas: {len(unidades_permanentes_df)}",
        f"Unidades nao classificadas encontradas: {qualidade['unidades_nao_classificadas']}",
        f"Planilha Excel consolidada gerada em: {settings.saida('consolidado_excel')}",
    ] + [f"Aviso: {a}" for a in avisos]
    exports.escrever_log(settings, log_linhas)

    return {
        "movimentos_df": historico_df,
        "processos_df": processos_df,
        "unidades_permanentes_df": unidades_permanentes_df,
        "episodios_df": episodios_df,
        "anomalias_df": anomalias_df,
        "nao_classificadas_df": nao_classificadas_df,
        "qualidade": qualidade,
        "avisos": avisos,
        "arquivos_utilizados": arquivos_utilizados,
        "excel_consolidado": settings.saida("consolidado_excel"),
        "usou_cache": False,
    }
