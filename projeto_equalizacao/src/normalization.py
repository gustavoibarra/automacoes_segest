"""Funcoes centrais de normalizacao de texto.

Todo texto que participa de comparacoes (nomes de unidade, indicador,
classificacao, classe judicial, municipio) deve passar por esta funcao unica
antes de ser comparado ou agrupado. O texto original e sempre preservado em
uma coluna separada para exibicao.

Nao fazemos correspondencia aproximada (fuzzy matching): duas grafias que
normalizam para strings diferentes permanecem diferentes.
"""
from __future__ import annotations

import re
import unicodedata

_MULTI_SPACE_RE = re.compile(r"\s+")
_ORDINAL_RE = re.compile(r"\b(\d+)[OA](?=\s|$)")
_DASH_CHARS_RE = re.compile(r"[‐‑‒–—―−]")
_MULTI_DASH_RE = re.compile(r"-{2,}")
_EDGE_PUNCT_RE = re.compile(r"^[\.\,\;\:\-\s]+|[\.\,\;\:\-\s]+$")


def strip_accents(text: str) -> str:
    """Remove diacriticos preservando a letra base (NFKD)."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_text(value) -> str:
    """Normalizacao central: maiusculas, sem acento, sem espacos duplicados,
    ordinais unificados (1a, 1A, 1o -> 1), hifens e pontuacao normalizados.
    """
    if value is None:
        return ""
    text = str(value)
    if not text or text.strip() == "" or text.strip().lower() == "nan":
        return ""

    text = strip_accents(text)
    text = text.upper()
    text = _DASH_CHARS_RE.sub("-", text)
    text = _ORDINAL_RE.sub(r"\1", text)
    text = _MULTI_DASH_RE.sub("-", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _EDGE_PUNCT_RE.sub("", text)
    text = _MULTI_SPACE_RE.sub(" ", text).strip()
    return text


def normalize_unit_name(value) -> str:
    """Normaliza nomes de unidades judiciarias (orgao julgador)."""
    return normalize_text(value)


INDICADOR_DISTRIBUICAO = "DISTRIBUICAO"
INDICADOR_REDISTRIBUICAO = "REDISTRIBUICAO"
INDICADOR_RESTITUIDO = "RESTITUIDO"
INDICADOR_OUTRO = "OUTRO"
INDICADOR_NAO_IDENTIFICADO = "NAO_IDENTIFICADO"


def normalize_indicador(value) -> str:
    """Classifica o indicador em DISTRIBUICAO / REDISTRIBUICAO / RESTITUIDO /
    OUTRO / NAO_IDENTIFICADO.

    A busca por "RESTITUIDO" precede as demais, pois o indicador "Restituido
    Por Redistribuicao" contem o trecho "redistribuicao" mas representa uma
    movimentacao de natureza diferente (estorno/devolucao), que deve ser
    classificada e armazenada separadamente. Em seguida, a busca por
    "REDISTRIBUICAO" precede a busca por "DISTRIBUICAO", pois a palavra
    "redistribuicao" contem o trecho "distribuicao".
    """
    norm = normalize_text(value)
    if norm == "":
        return INDICADOR_NAO_IDENTIFICADO
    if "RESTITUIDO" in norm:
        return INDICADOR_RESTITUIDO
    if "REDISTRIBUICAO" in norm:
        return INDICADOR_REDISTRIBUICAO
    if "DISTRIBUICAO" in norm:
        return INDICADOR_DISTRIBUICAO
    return INDICADOR_OUTRO


CLASSIFICACAO_CEDENTE = "CEDENTE"
CLASSIFICACAO_NEUTRA = "NEUTRA"
CLASSIFICACAO_DESTINATARIA = "DESTINATARIA"
CLASSIFICACAO_NAO_CLASSIFICADA = "NAO_CLASSIFICADA"

_CLASSIFICACAO_PREFIXOS = (
    (CLASSIFICACAO_CEDENTE, "CEDENTE"),
    (CLASSIFICACAO_NEUTRA, "NEUTRA"),
    (CLASSIFICACAO_DESTINATARIA, "DESTINATARIA"),
)


def normalize_classificacao(value) -> str | None:
    """Normaliza a classificacao da unidade aceitando com/sem acento e
    singular/plural. Retorna None quando o valor nao corresponde a nenhuma
    das tres categorias oficiais.
    """
    norm = normalize_text(value)
    if norm == "":
        return None
    for destino, prefixo in _CLASSIFICACAO_PREFIXOS:
        if norm.startswith(prefixo):
            return destino
    return None


def normalize_processo_numero(value) -> str:
    """Normaliza o numero do processo apenas removendo espacos externos.

    Nunca converte para numero (evita perda de zeros a esquerda) e nunca
    remove pontuacao, pois ela faz parte da identificacao processual (CNJ).
    """
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def is_unidade_triagem(unidade_normalizada: str, palavra_triagem: str = "TRIAGEM") -> bool:
    """Identifica unidade de triagem: nome normalizado contem a palavra
    TRIAGEM, de forma insensivel a maiusculas/minusculas e acentos (o
    parametro de entrada ja deve estar normalizado por normalize_unit_name).
    """
    return palavra_triagem in unidade_normalizada
