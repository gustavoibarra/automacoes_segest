"""Deteccao de episodios de passagem por triagem e classificacao da
equalizacao (secoes 8, 9 e 10 do prompt).

Uma equalizacao e detectada quando o historico cronologico do processo
contem a sequencia UNIDADE PERMANENTE -> UNIDADE DE TRIAGEM -> UNIDADE
PERMANENTE. O algoritmo varre o historico ja ordenado (produzido por
histories.reconstruir_historico) mantendo o estado da ultima unidade
permanente vista; ao encontrar uma unidade de triagem, abre um episodio;
ao encontrar a proxima unidade permanente, fecha o episodio. Isso cobre
naturalmente o caso de multiplos episodios para o mesmo processo (secao 9,
"Movimentacoes posteriores").

Movimentacoes em unidades nao classificadas (nem permanentes, nem de
triagem) sao ignoradas na deteccao de episodios -- elas ja sao registradas
como anomalia UNIDADE_NAO_CLASSIFICADA em outra etapa e nao servem como
ancora confiavel de origem/destino.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src import anomalies
from src.normalization import (
    CLASSIFICACAO_CEDENTE,
    CLASSIFICACAO_DESTINATARIA,
    INDICADOR_REDISTRIBUICAO,
)

TIPO_VALIDA = "VALIDA"
TIPO_FORA_PADRAO = "FORA_PADRAO"
TIPO_INCOMPLETA = "INCOMPLETA"


@dataclass
class _RegistroUnidade:
    unidade_norm: str
    unidade_original: str
    classificacao: str
    data: pd.Timestamp
    indicador_norm: str
    arquivo_origem: str
    numero_linha_arquivo: int
    sequencia_movimento: int


def _construir_mapa_classificacao(unidades_permanentes_df: pd.DataFrame) -> dict:
    return {
        row.unidade_norm: (row.classificacao, row.unidade_original)
        for row in unidades_permanentes_df.itertuples(index=False)
    }


def _sequencia_relevante(grupo: pd.DataFrame, mapa_classificacao: dict) -> list:
    relevantes = []
    for row in grupo.itertuples(index=False):
        if row.unidade_e_triagem:
            relevantes.append(_RegistroUnidade(
                unidade_norm=row.orgao_norm,
                unidade_original=row.orgao_julgador_original,
                classificacao="TRIAGEM",
                data=row.data_dt,
                indicador_norm=row.indicador_norm,
                arquivo_origem=row.arquivo_origem,
                numero_linha_arquivo=row.numero_linha_arquivo,
                sequencia_movimento=row.sequencia_movimento,
            ))
        elif row.orgao_norm in mapa_classificacao:
            classificacao, unidade_original_oficial = mapa_classificacao[row.orgao_norm]
            relevantes.append(_RegistroUnidade(
                unidade_norm=row.orgao_norm,
                unidade_original=unidade_original_oficial,
                classificacao=classificacao,
                data=row.data_dt,
                indicador_norm=row.indicador_norm,
                arquivo_origem=row.arquivo_origem,
                numero_linha_arquivo=row.numero_linha_arquivo,
                sequencia_movimento=row.sequencia_movimento,
            ))
        # unidades nao classificadas e nao-triagem sao ignoradas aqui
    return relevantes


def _detectar_episodios_processo(relevantes: list) -> list[dict]:
    episodios = []
    ultimo_permanente = None
    episodio_aberto = None

    for item in relevantes:
        if item.classificacao == "TRIAGEM":
            if episodio_aberto is None and ultimo_permanente is not None:
                episodio_aberto = {"origem": ultimo_permanente, "entrada_triagem": item}
        else:
            if episodio_aberto is not None:
                episodio_aberto["destino"] = item
                episodios.append(_finalizar_episodio(episodio_aberto))
                episodio_aberto = None
            ultimo_permanente = item

    if episodio_aberto is not None:
        episodio_aberto["destino"] = None
        episodios.append(_finalizar_episodio(episodio_aberto))

    return episodios


def _finalizar_episodio(ep: dict) -> dict:
    origem: _RegistroUnidade = ep["origem"]
    entrada: _RegistroUnidade = ep["entrada_triagem"]
    destino: _RegistroUnidade | None = ep.get("destino")

    motivos = []
    if destino is None:
        tipo = TIPO_INCOMPLETA
        motivos.append("Nao ha unidade permanente definitiva apos a triagem")
    else:
        origem_ok = origem.classificacao == CLASSIFICACAO_CEDENTE
        destino_ok = destino.classificacao == CLASSIFICACAO_DESTINATARIA
        entrada_redistribuicao = entrada.indicador_norm == INDICADOR_REDISTRIBUICAO
        destino_redistribuicao = destino.indicador_norm == INDICADOR_REDISTRIBUICAO

        if not origem_ok:
            motivos.append(f"Origem nao classificada como CEDENTE (classificacao: {origem.classificacao})")
        if not destino_ok:
            motivos.append(f"Destino nao classificado como DESTINATARIA (classificacao: {destino.classificacao})")
        if not entrada_redistribuicao:
            motivos.append("Movimento de entrada na triagem nao e uma redistribuicao")
        if not destino_redistribuicao:
            motivos.append("Movimento de entrada no destino nao e uma redistribuicao")

        tipo = TIPO_VALIDA if (origem_ok and destino_ok and entrada_redistribuicao and destino_redistribuicao) else TIPO_FORA_PADRAO

    return {
        "origem": origem,
        "entrada_triagem": entrada,
        "destino": destino,
        "tipo": tipo,
        "motivo": "; ".join(motivos),
    }


def detectar_equalizacoes(historico: pd.DataFrame, unidades_permanentes_df: pd.DataFrame
                           ) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """Detecta episodios de equalizacao para todos os processos.

    Retorna:
      - episodios_df: tabela de auditoria com um registro por episodio;
      - campos_processo_df: campos de equalizacao a mesclar em processos_consolidados,
        indexado por processo_norm;
      - anomalias: lista de dicts de anomalia.
    """
    mapa_classificacao = _construir_mapa_classificacao(unidades_permanentes_df)

    linhas_episodios = []
    linhas_processo = []
    anomalias_lista: list[dict] = []

    for processo_norm, grupo in historico.groupby("processo_norm", sort=False):
        grupo = grupo.sort_values("sequencia_movimento")
        processo_original = grupo.iloc[0]["processo"]
        relevantes = _sequencia_relevante(grupo, mapa_classificacao)
        episodios = _detectar_episodios_processo(relevantes)

        for numero, ep in enumerate(episodios, start=1):
            origem, entrada, destino = ep["origem"], ep["entrada_triagem"], ep["destino"]
            linhas_episodios.append({
                "processo": processo_original,
                "processo_norm": processo_norm,
                "numero_episodio": numero,
                "unidade_origem_norm": origem.unidade_norm,
                "unidade_origem": origem.unidade_original,
                "classificacao_origem": origem.classificacao,
                "data_entrada_triagem": entrada.data,
                "unidade_triagem_norm": entrada.unidade_norm,
                "unidade_triagem": entrada.unidade_original,
                "indicador_entrada_triagem": entrada.indicador_norm,
                "unidade_destino_norm": destino.unidade_norm if destino else "",
                "unidade_destino": destino.unidade_original if destino else "",
                "classificacao_destino": destino.classificacao if destino else "",
                "data_destino_equalizacao": destino.data if destino else pd.NaT,
                "indicador_entrada_destino": destino.indicador_norm if destino else "",
                "tipo_episodio": ep["tipo"],
                "motivo": ep["motivo"],
            })

            if ep["tipo"] == TIPO_INCOMPLETA:
                anomalias_lista.append(anomalies.novo(
                    anomalies.PASSAGEM_TRIAGEM_INCOMPLETA, processo=processo_original,
                    arquivo_origem=entrada.arquivo_origem, numero_linha_arquivo=entrada.numero_linha_arquivo,
                ))
            elif ep["tipo"] == TIPO_FORA_PADRAO:
                if origem.classificacao != CLASSIFICACAO_CEDENTE:
                    anomalias_lista.append(anomalies.novo(
                        anomalies.ORIGEM_EQUALIZACAO_NAO_CEDENTE, processo=processo_original,
                        arquivo_origem=entrada.arquivo_origem, numero_linha_arquivo=entrada.numero_linha_arquivo,
                    ))
                if destino is not None and destino.classificacao != CLASSIFICACAO_DESTINATARIA:
                    anomalias_lista.append(anomalies.novo(
                        anomalies.DESTINO_EQUALIZACAO_NAO_DESTINATARIA, processo=processo_original,
                        arquivo_origem=destino.arquivo_origem, numero_linha_arquivo=destino.numero_linha_arquivo,
                    ))

        if len(episodios) > 1:
            anomalias_lista.append(anomalies.novo(
                anomalies.MULTIPLOS_EPISODIOS_EQUALIZACAO, processo=processo_original,
                descricao=f"Processo {processo_original} possui {len(episodios)} episodios de passagem pela triagem.",
                arquivo_origem=grupo.iloc[0]["arquivo_origem"], numero_linha_arquivo=grupo.iloc[0]["numero_linha_arquivo"],
            ))

        episodios_validos = [e for e in episodios if e["tipo"] == TIPO_VALIDA]
        equalizacao_detectada = any(e["destino"] is not None for e in episodios)
        equalizacao_valida = len(episodios_validos) > 0

        episodio_principal = episodios_validos[0] if episodios_validos else (episodios[0] if episodios else None)

        if episodio_principal is not None:
            origem_p = episodio_principal["origem"]
            entrada_p = episodio_principal["entrada_triagem"]
            destino_p = episodio_principal["destino"]
            unidade_cedente_equalizacao = origem_p.unidade_norm
            unidade_cedente_equalizacao_original = origem_p.unidade_original
            unidade_destinataria_equalizacao = destino_p.unidade_norm if destino_p else ""
            unidade_destinataria_equalizacao_original = destino_p.unidade_original if destino_p else ""
            data_entrada_triagem = entrada_p.data
            data_destino_equalizacao = destino_p.data if destino_p else pd.NaT
            motivo_invalidade = "" if equalizacao_valida else episodio_principal["motivo"]
        else:
            unidade_cedente_equalizacao = ""
            unidade_cedente_equalizacao_original = ""
            unidade_destinataria_equalizacao = ""
            unidade_destinataria_equalizacao_original = ""
            data_entrada_triagem = pd.NaT
            data_destino_equalizacao = pd.NaT
            motivo_invalidade = ""

        linhas_processo.append({
            "processo_norm": processo_norm,
            "equalizacao_detectada": equalizacao_detectada,
            "equalizacao_valida": equalizacao_valida,
            "quantidade_episodios_triagem": len(episodios),
            "unidade_cedente_equalizacao": unidade_cedente_equalizacao,
            "unidade_cedente_equalizacao_original": unidade_cedente_equalizacao_original,
            "unidade_destinataria_equalizacao": unidade_destinataria_equalizacao,
            "unidade_destinataria_equalizacao_original": unidade_destinataria_equalizacao_original,
            "data_entrada_triagem": data_entrada_triagem,
            "data_destino_equalizacao": data_destino_equalizacao,
            "motivo_invalidade_equalizacao": motivo_invalidade,
        })

    colunas_episodios = [
        "processo", "processo_norm", "numero_episodio", "unidade_origem_norm", "unidade_origem",
        "classificacao_origem", "data_entrada_triagem", "unidade_triagem_norm", "unidade_triagem",
        "indicador_entrada_triagem", "unidade_destino_norm", "unidade_destino", "classificacao_destino",
        "data_destino_equalizacao", "indicador_entrada_destino", "tipo_episodio", "motivo",
    ]
    colunas_processo = [
        "processo_norm", "equalizacao_detectada", "equalizacao_valida", "quantidade_episodios_triagem",
        "unidade_cedente_equalizacao", "unidade_cedente_equalizacao_original", "unidade_destinataria_equalizacao",
        "unidade_destinataria_equalizacao_original", "data_entrada_triagem", "data_destino_equalizacao",
        "motivo_invalidade_equalizacao",
    ]
    episodios_df = pd.DataFrame(linhas_episodios, columns=colunas_episodios)
    campos_processo_df = pd.DataFrame(linhas_processo, columns=colunas_processo)
    campos_processo_df["equalizacao_detectada"] = campos_processo_df["equalizacao_detectada"].astype(bool)
    campos_processo_df["equalizacao_valida"] = campos_processo_df["equalizacao_valida"].astype(bool)
    campos_processo_df["data_entrada_triagem"] = pd.to_datetime(campos_processo_df["data_entrada_triagem"])
    campos_processo_df["data_destino_equalizacao"] = pd.to_datetime(campos_processo_df["data_destino_equalizacao"])
    episodios_df["data_entrada_triagem"] = pd.to_datetime(episodios_df["data_entrada_triagem"])
    episodios_df["data_destino_equalizacao"] = pd.to_datetime(episodios_df["data_destino_equalizacao"])
    return episodios_df, campos_processo_df, anomalias_lista


def calcular_unidade_simulada_sem_equalizacao(processos_df: pd.DataFrame) -> pd.DataFrame:
    """Calcula a coluna unidade_simulada_sem_equalizacao (secao 12.2):

    - processos com equalizacao valida: unidade cedente imediatamente
      anterior a triagem;
    - processos sem equalizacao valida (inclusive triagem invalida ou
      incompleta): unidade final real.
    """
    df = processos_df.copy()
    if df.empty:
        df["unidade_simulada_sem_equalizacao"] = pd.Series(dtype=str)
        df["unidade_simulada_sem_equalizacao_original"] = pd.Series(dtype=str)
        return df

    def _simular(row):
        if row["equalizacao_valida"]:
            return row["unidade_cedente_equalizacao"], row["unidade_cedente_equalizacao_original"]
        return row["unidade_final_real"], row["unidade_final_real_original"]

    resultado = df.apply(_simular, axis=1, result_type="expand")
    df["unidade_simulada_sem_equalizacao"] = resultado[0]
    df["unidade_simulada_sem_equalizacao_original"] = resultado[1]
    return df
