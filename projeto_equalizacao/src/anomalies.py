"""Catalogo centralizado de tipos de anomalia e utilitario de criacao de
registros de anomalia, usados por validation.py, histories.py e
equalization.py para alimentar a tabela unica anomalias.csv.
"""
from __future__ import annotations

PROCESSO_SEM_NUMERO = "PROCESSO_SEM_NUMERO"
PROCESSO_FORMATO_INVALIDO = "PROCESSO_FORMATO_INVALIDO"
DATA_INVALIDA = "DATA_INVALIDA"
UNIDADE_VAZIA = "UNIDADE_VAZIA"
UNIDADE_NAO_CLASSIFICADA = "UNIDADE_NAO_CLASSIFICADA"
PRIMEIRO_MOVIMENTO_NAO_DISTRIBUICAO = "PRIMEIRO_MOVIMENTO_NAO_DISTRIBUICAO"
MULTIPLA_DISTRIBUICAO_INICIAL = "MULTIPLA_DISTRIBUICAO_INICIAL"
REDISTRIBUICAO_ANTERIOR_A_DISTRIBUICAO = "REDISTRIBUICAO_ANTERIOR_A_DISTRIBUICAO"
ORDEM_CRONOLOGICA_AMBIGUA = "ORDEM_CRONOLOGICA_AMBIGUA"
PASSAGEM_TRIAGEM_INCOMPLETA = "PASSAGEM_TRIAGEM_INCOMPLETA"
ORIGEM_EQUALIZACAO_NAO_CEDENTE = "ORIGEM_EQUALIZACAO_NAO_CEDENTE"
DESTINO_EQUALIZACAO_NAO_DESTINATARIA = "DESTINO_EQUALIZACAO_NAO_DESTINATARIA"
ULTIMO_MOVIMENTO_EM_TRIAGEM = "ULTIMO_MOVIMENTO_EM_TRIAGEM"
MULTIPLOS_EPISODIOS_EQUALIZACAO = "MULTIPLOS_EPISODIOS_EQUALIZACAO"
MOVIMENTACAO_DUPLICADA_REMOVIDA = "MOVIMENTACAO_DUPLICADA_REMOVIDA"
CLASSE_JUDICIAL_DIVERGENTE = "CLASSE_JUDICIAL_DIVERGENTE"

DESCRICOES = {
    PROCESSO_SEM_NUMERO: "Processo sem numero",
    PROCESSO_FORMATO_INVALIDO: "Processo com formato aparentemente invalido",
    DATA_INVALIDA: "Data invalida",
    UNIDADE_VAZIA: "Unidade vazia",
    UNIDADE_NAO_CLASSIFICADA: "Unidade nao classificada",
    PRIMEIRO_MOVIMENTO_NAO_DISTRIBUICAO: "Primeiro movimento diferente de distribuicao",
    MULTIPLA_DISTRIBUICAO_INICIAL: "Mais de uma distribuicao inicial",
    REDISTRIBUICAO_ANTERIOR_A_DISTRIBUICAO: "Redistribuicao com data anterior a distribuicao",
    ORDEM_CRONOLOGICA_AMBIGUA: "Ordem cronologica ambigua entre movimentos na mesma data",
    PASSAGEM_TRIAGEM_INCOMPLETA: "Passagem incompleta pela triagem",
    ORIGEM_EQUALIZACAO_NAO_CEDENTE: "Origem da equalizacao nao classificada como cedente",
    DESTINO_EQUALIZACAO_NAO_DESTINATARIA: "Destino da equalizacao nao classificado como destinataria",
    ULTIMO_MOVIMENTO_EM_TRIAGEM: "Ultimo movimento do processo ainda em unidade de triagem",
    MULTIPLOS_EPISODIOS_EQUALIZACAO: "Processo com mais de um episodio de passagem pela triagem",
    MOVIMENTACAO_DUPLICADA_REMOVIDA: "Movimentacao duplicada removida na consolidacao",
    CLASSE_JUDICIAL_DIVERGENTE: "Classe judicial divergente entre movimentos do mesmo processo",
}


def novo(tipo: str, processo: str = "", descricao: str = "", arquivo_origem: str = "",
         numero_linha_arquivo=None) -> dict:
    return {
        "processo": processo,
        "tipo_anomalia": tipo,
        "descricao": descricao or DESCRICOES.get(tipo, tipo),
        "arquivo_origem": arquivo_origem,
        "numero_linha_arquivo": numero_linha_arquivo,
    }
