"""Leitura dos arquivos de entrada: CSVs de movimentacoes e planilha de
classificacao das unidades judiciarias.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.normalization import normalize_classificacao, normalize_text, normalize_unit_name

_NOME_ARQUIVO_RE = re.compile(r"^processos_(\d{2}-\d{2}-\d{4})\.csv$", re.IGNORECASE)

# Os CSVs exportados pelo Sistema de Equalizacao trazem, nas primeiras linhas,
# um resumo do arquivo (sem valor para a consolidacao). A tabela de fato so
# comeca na linha do cabecalho das colunas, que inicia com "#Processo" --
# tipicamente a linha 7, mas o numero exato de linhas de resumo pode variar
# entre exportacoes, por isso a linha de cabecalho e localizada dinamicamente
# em vez de assumir uma quantidade fixa de linhas a pular.
_MARCADOR_CABECALHO = "#Processo"
_MAX_LINHAS_RESUMO = 50


class ConfigError(Exception):
    """Erro de configuracao ou estrutura de arquivo de entrada que deve
    interromper o processamento com uma mensagem objetiva para o usuario."""


@dataclass
class ArquivoCsvInfo:
    caminho: Path
    data_arquivo: datetime
    ordem_arquivo: int


def localizar_arquivos_csv(downloads_dir: Path, prefixo: str = "processos_",
                            sufixo: str = ".csv") -> list[ArquivoCsvInfo]:
    """Localiza todos os arquivos processos_{DD-MM-YYYY}.csv na pasta downloads.

    Arquivos cujo nome nao segue o padrao de data sao ignorados com aviso
    (o chamador e responsavel por logar). A ordem retornada e cronologica
    pela data do arquivo e, em caso de empate, alfabetica pelo nome -- essa
    ordem define 'ordem_arquivo', usada como criterio de desempate na
    reconstrucao do historico.
    """
    if not downloads_dir.exists():
        raise ConfigError(
            f"A pasta de downloads nao foi encontrada: {downloads_dir}"
        )

    encontrados = []
    ignorados = []
    for caminho in sorted(downloads_dir.iterdir()):
        if not caminho.is_file():
            continue
        nome = caminho.name
        if not (nome.lower().startswith(prefixo.lower()) and nome.lower().endswith(sufixo.lower())):
            continue
        match = _NOME_ARQUIVO_RE.match(nome)
        if not match:
            ignorados.append(nome)
            continue
        data_arquivo = datetime.strptime(match.group(1), "%d-%m-%Y")
        encontrados.append((caminho, data_arquivo))

    if not encontrados:
        raise ConfigError(
            f"Nenhum arquivo no padrao '{prefixo}DD-MM-YYYY{sufixo}' foi encontrado em {downloads_dir}."
        )

    encontrados.sort(key=lambda item: (item[1], item[0].name))
    infos = [
        ArquivoCsvInfo(caminho=caminho, data_arquivo=data, ordem_arquivo=ordem)
        for ordem, (caminho, data) in enumerate(encontrados)
    ]
    return infos


_DELIMITADORES_SUPORTADOS = (";", ",")


def _localizar_linha_cabecalho(caminho: Path, encoding: str, max_linhas: int = _MAX_LINHAS_RESUMO
                                ) -> tuple[int, str]:
    """Retorna (indice 0-based, delimitador) da linha que contem o
    cabecalho das colunas -- aquela cuja primeira celula e '#Processo' --
    para que tudo o que vem antes (linhas de resumo do arquivo) seja
    descartado. As linhas de resumo tambem podem comecar com '#' (ex.:
    '#Total de registros: ...'), por isso a comparacao e feita pelo texto
    exato da primeira celula, e nao apenas pelo prefixo '#'. O delimitador
    (';' ou ',') e detectado a partir da propria linha de cabecalho, pois
    exportacoes do sistema usam ';'."""
    with open(caminho, "r", encoding=encoding, newline="") as f:
        for indice, linha in enumerate(f):
            if indice > max_linhas:
                break
            texto = linha.strip().lstrip("﻿").strip('"').strip("'")
            for delimitador in _DELIMITADORES_SUPORTADOS:
                primeira_celula = texto.split(delimitador)[0].strip().strip('"').strip("'")
                if primeira_celula == _MARCADOR_CABECALHO:
                    return indice, delimitador
    raise ConfigError(
        f"Nao foi possivel localizar a linha de cabecalho (iniciada por '{_MARCADOR_CABECALHO}') "
        f"nas primeiras {max_linhas} linhas do arquivo {caminho.name}. Verifique se as linhas de "
        "resumo do arquivo antecedem corretamente o cabecalho das colunas."
    )


def _renomear_colunas_tolerante(df: pd.DataFrame, colunas_esperadas: tuple[str, ...]) -> pd.DataFrame:
    """Renomeia colunas do CSV para o nome oficial esperado quando elas
    coincidem apos normalizacao (maiusculas, sem acento, espacos
    colapsados). Isso tolera pequenas variacoes/erros de digitacao do
    sistema de origem -- por exemplo, a coluna sair como 'Municipío Sede'
    em vez de 'Município Sede' nao deve interromper o processamento, pois
    ambas normalizam para 'MUNICIPIO SEDE'."""
    mapa_esperado_norm = {normalize_text(c): c for c in colunas_esperadas}
    renomeio = {}
    for coluna_real in df.columns:
        norm = normalize_text(coluna_real)
        canonical = mapa_esperado_norm.get(norm)
        if canonical is not None and coluna_real != canonical:
            renomeio[coluna_real] = canonical
    if renomeio:
        df = df.rename(columns=renomeio)
    return df


def carregar_csv_movimentos(info: ArquivoCsvInfo, encoding: str = "utf-8",
                             colunas_esperadas: tuple[str, ...] = ()) -> pd.DataFrame:
    """Carrega um unico CSV de movimentacoes, descartando as linhas de
    resumo que antecedem o cabecalho das colunas (linha iniciada por
    '#Processo'), preservando o numero do processo como texto e
    acrescentando colunas de rastreabilidade."""
    linha_cabecalho, delimitador = _localizar_linha_cabecalho(info.caminho, encoding)
    df = pd.read_csv(
        info.caminho,
        encoding=encoding,
        sep=delimitador,
        skiprows=linha_cabecalho,
        dtype={"#Processo": str},
        keep_default_na=True,
    )
    df.columns = [str(c).strip() for c in df.columns]
    if colunas_esperadas:
        df = _renomear_colunas_tolerante(df, colunas_esperadas)

    df["arquivo_origem"] = info.caminho.name
    df["data_arquivo"] = info.data_arquivo
    df["ordem_arquivo"] = info.ordem_arquivo
    # numero_linha_arquivo reflete a linha fisica real no arquivo original
    # (1-based), considerando as linhas de resumo e o cabecalho descartados.
    primeira_linha_dado = linha_cabecalho + 2
    df["numero_linha_arquivo"] = range(primeira_linha_dado, primeira_linha_dado + len(df))
    df["data_processamento"] = datetime.now()
    return df


def carregar_todos_movimentos(downloads_dir: Path, colunas_esperadas: tuple,
                               encoding: str = "utf-8") -> tuple[pd.DataFrame, list[str]]:
    """Localiza e concatena todos os CSVs de movimentacoes.

    Retorna a tabela consolidada bruta e a lista de nomes de arquivo
    ignorados por nao seguirem o padrao esperado.
    """
    infos = localizar_arquivos_csv(downloads_dir)
    partes = []
    nomes_arquivos = []
    for info in infos:
        df = carregar_csv_movimentos(info, encoding=encoding, colunas_esperadas=colunas_esperadas)
        faltantes = [c for c in colunas_esperadas if c not in df.columns]
        if faltantes:
            raise ConfigError(
                f"O arquivo {info.caminho.name} nao contem as colunas esperadas {faltantes}. "
                f"Colunas encontradas: {list(df.columns)}"
            )
        partes.append(df)
        nomes_arquivos.append(info.caminho.name)
    consolidado = pd.concat(partes, ignore_index=True)
    return consolidado, nomes_arquivos


def _encontrar_coluna(colunas_originais: list[str], palavras_chave: tuple[str, ...]) -> str | None:
    for coluna in colunas_originais:
        norm = normalize_unit_name(coluna)
        if any(chave in norm for chave in palavras_chave):
            return coluna
    return None


def carregar_classificacao_unidades(caminho: Path, palavra_triagem: str = "TRIAGEM"
                                     ) -> tuple[pd.DataFrame, list[str]]:
    """Carrega o arquivo de classificacao das unidades judiciarias.

    Detecta automaticamente as colunas de nome da unidade e de
    classificacao. Interrompe o processamento (ConfigError) se a estrutura
    nao puder ser identificada.

    Retorna (dataframe, avisos). O dataframe contem apenas unidades
    permanentes validas (exclui linhas cujo nome contenha TRIAGEM e linhas
    cuja classificacao nao normalize para CEDENTE/NEUTRA/DESTINATARIA).
    """
    bruto = pd.read_excel(caminho, dtype=str)
    bruto.columns = [str(c).strip() for c in bruto.columns]
    colunas = list(bruto.columns)

    coluna_unidade = _encontrar_coluna(colunas, ("UNIDADE", "ORGAO JULGADOR", "ORGAO"))
    coluna_classificacao = _encontrar_coluna(colunas, ("CLASSIFICACAO", "CLASSE"))
    coluna_magistrados = _encontrar_coluna(colunas, ("MAGISTRADO",))

    if coluna_unidade is None or coluna_classificacao is None:
        raise ConfigError(
            "Nao foi possivel identificar as colunas do arquivo de classificacao de unidades. "
            f"Colunas encontradas: {colunas}. "
            "Colunas esperadas: uma coluna com o nome da unidade (ex.: 'Unidade' ou 'Orgao Julgador') "
            "e uma coluna com a classificacao (ex.: 'Classificacao'), contendo os valores "
            "CEDENTE, NEUTRA e DESTINATARIA (com ou sem acento, singular ou plural)."
        )

    avisos: list[str] = []
    if coluna_magistrados is None:
        avisos.append(
            "O arquivo de classificacao de unidades nao possui uma coluna de quantidade de magistrados "
            "(ex.: 'Quantidade de Magistrados'). As medidas ponderadas por magistrado ficarao indisponiveis "
            "(aparecerao como N/A)."
        )

    registros = []
    for _, linha in bruto.iterrows():
        unidade_original = linha[coluna_unidade]
        if pd.isna(unidade_original) or str(unidade_original).strip() == "":
            continue
        unidade_norm = normalize_unit_name(unidade_original)
        if palavra_triagem in unidade_norm:
            continue

        classificacao_original = linha[coluna_classificacao]
        classificacao_norm = normalize_classificacao(classificacao_original)
        if classificacao_norm is None:
            avisos.append(
                f"Unidade '{unidade_original}' possui classificacao nao reconhecida "
                f"('{classificacao_original}') e foi ignorada do universo de unidades permanentes."
            )
            continue

        quantidade_magistrados = float("nan")
        if coluna_magistrados is not None:
            valor_magistrados = pd.to_numeric(linha[coluna_magistrados], errors="coerce")
            if pd.isna(valor_magistrados) or valor_magistrados <= 0:
                avisos.append(
                    f"Unidade '{unidade_original}' possui quantidade de magistrados ausente ou invalida "
                    f"('{linha[coluna_magistrados]}'); as medidas ponderadas por magistrado desta unidade "
                    "ficarao indisponiveis (N/A)."
                )
            else:
                quantidade_magistrados = float(valor_magistrados)

        registros.append({
            "unidade_original": str(unidade_original).strip(),
            "unidade_norm": unidade_norm,
            "classificacao": classificacao_norm,
            "quantidade_magistrados": quantidade_magistrados,
        })

    df = pd.DataFrame(registros, columns=["unidade_original", "unidade_norm", "classificacao", "quantidade_magistrados"])
    df = df.drop_duplicates(subset=["unidade_norm"], keep="first").reset_index(drop=True)
    return df, avisos


def localizar_arquivo_classificacao(base_dir: Path, candidatos: tuple[str, ...]) -> Path:
    for nome in candidatos:
        caminho = base_dir / nome
        if caminho.exists():
            return caminho
    raise ConfigError(
        f"Arquivo de classificacao de unidades nao encontrado. Nomes esperados: {list(candidatos)} "
        f"na pasta {base_dir}."
    )
