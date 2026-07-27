"""Escrita dos arquivos de saida e cache de consolidacao baseado na
assinatura (nome, tamanho e data de modificacao) dos arquivos de entrada
(secoes 21 e 23 do prompt)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.xlsx_utils import formatar_planilha, remover_timezone


def assinatura_entrada(downloads_dir: Path, classificacao_path: Path | None) -> str:
    partes = []
    if downloads_dir.exists():
        for caminho in sorted(downloads_dir.iterdir()):
            if caminho.is_file():
                stat = caminho.stat()
                partes.append(f"{caminho.name}:{stat.st_size}:{int(stat.st_mtime)}")
    if classificacao_path is not None and classificacao_path.exists():
        stat = classificacao_path.stat()
        partes.append(f"{classificacao_path.name}:{stat.st_size}:{int(stat.st_mtime)}")
    bruto = "|".join(partes)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def cache_valido(output_dir: Path, cache_meta_filename: str, assinatura_atual: str,
                  arquivos_obrigatorios: list[Path]) -> bool:
    meta_path = output_dir / cache_meta_filename
    if not meta_path.exists():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if meta.get("assinatura") != assinatura_atual:
        return False
    return all(p.exists() for p in arquivos_obrigatorios)


def salvar_cache_meta(output_dir: Path, cache_meta_filename: str, assinatura: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    meta = {"assinatura": assinatura, "gerado_em": datetime.now().isoformat()}
    (output_dir / cache_meta_filename).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _salvar_csv_parquet(df: pd.DataFrame, caminho_parquet: Path | None, caminho_csv: Path | None) -> None:
    if caminho_parquet is not None:
        df.to_parquet(caminho_parquet, index=False)
    if caminho_csv is not None:
        df.to_csv(caminho_csv, index=False, encoding="utf-8-sig")


def escrever_saidas(settings, movimentos_df: pd.DataFrame, processos_df: pd.DataFrame,
                     episodios_df: pd.DataFrame, comparativo_df: pd.DataFrame, fluxos_df: pd.DataFrame,
                     anomalias_df: pd.DataFrame, nao_classificadas_df: pd.DataFrame) -> None:
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    _salvar_csv_parquet(movimentos_df, settings.saida("movimentacoes_parquet"), settings.saida("movimentacoes_csv"))
    _salvar_csv_parquet(processos_df, settings.saida("processos_parquet"), settings.saida("processos_csv"))
    _salvar_csv_parquet(episodios_df, None, settings.saida("episodios_csv"))
    _salvar_csv_parquet(comparativo_df, None, settings.saida("comparativo_csv"))
    _salvar_csv_parquet(fluxos_df, None, settings.saida("fluxos_csv"))
    _salvar_csv_parquet(anomalias_df, None, settings.saida("anomalias_csv"))
    _salvar_csv_parquet(nao_classificadas_df, None, settings.saida("nao_classificadas_csv"))


def escrever_excel_consolidado(settings, movimentos_df: pd.DataFrame, processos_df: pd.DataFrame,
                                episodios_df: pd.DataFrame, comparativo_df: pd.DataFrame,
                                fluxos_df: pd.DataFrame, anomalias_df: pd.DataFrame,
                                nao_classificadas_df: pd.DataFrame, qualidade: dict | None = None,
                                avisos: list[str] | None = None, arquivos_utilizados: list[str] | None = None
                                ) -> Path:
    """Exporta a base consolidada inteira (sem filtros) em uma unica planilha
    Excel com varias abas, para analise direta dos processos fora do
    dashboard. Datas sao gravadas sem timezone (Excel nao suporta datas com
    fuso horario)."""
    caminho = settings.saida("consolidado_excel")
    caminho.parent.mkdir(parents=True, exist_ok=True)

    linhas_resumo = []
    if qualidade:
        linhas_resumo.append({"indicador": "Registros lidos", "valor": qualidade.get("quantidade_registros_lidos")})
        linhas_resumo.append({"indicador": "Quantidade de arquivos", "valor": qualidade.get("quantidade_arquivos")})
        linhas_resumo.append({"indicador": "Duplicidades removidas", "valor": qualidade.get("duplicidades_removidas")})
        linhas_resumo.append({"indicador": "Registros validos", "valor": qualidade.get("registros_validos")})
        linhas_resumo.append({"indicador": "Registros com anomalia", "valor": qualidade.get("registros_com_anomalia")})
        linhas_resumo.append({"indicador": "Registros RESTITUIDO (desconsiderados de todas as analises)", "valor": qualidade.get("registros_restituidos")})
        linhas_resumo.append({"indicador": "Processos distintos", "valor": qualidade.get("processos_distintos")})
        linhas_resumo.append({"indicador": "Unidades nao classificadas", "valor": qualidade.get("unidades_nao_classificadas")})
        linhas_resumo.append({"indicador": "Data minima", "valor": qualidade.get("data_minima")})
        linhas_resumo.append({"indicador": "Data maxima", "valor": qualidade.get("data_maxima")})
    linhas_resumo.append({"indicador": "Gerado em", "valor": datetime.now()})
    if arquivos_utilizados:
        linhas_resumo.append({"indicador": "Arquivos utilizados", "valor": ", ".join(arquivos_utilizados)})
    for aviso in (avisos or []):
        linhas_resumo.append({"indicador": "Aviso", "valor": aviso})
    resumo_df = pd.DataFrame(linhas_resumo)

    planilhas = {
        "Resumo": resumo_df,
        "Processos": remover_timezone(processos_df),
        "Movimentacoes": remover_timezone(movimentos_df),
        "Episodios_Equalizacao": remover_timezone(episodios_df),
        "Comparativo_Unidades": comparativo_df,
        "Fluxos_Equalizacao": fluxos_df,
        "Anomalias": anomalias_df,
        "Unidades_Nao_Classificadas": nao_classificadas_df,
    }

    with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
        for nome_aba, df in planilhas.items():
            df.to_excel(writer, sheet_name=nome_aba, index=False)
            formatar_planilha(writer.sheets[nome_aba], df)

    return caminho


def escrever_log(settings, linhas: list[str]) -> None:
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    caminho = settings.saida("log_processamento")
    with open(caminho, "a", encoding="utf-8") as f:
        f.write(f"\n===== Execucao em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} =====\n")
        for linha in linhas:
            f.write(linha + "\n")


def carregar_saidas_cacheadas(settings) -> dict:
    return {
        "movimentos_df": pd.read_parquet(settings.saida("movimentacoes_parquet")),
        "processos_df": pd.read_parquet(settings.saida("processos_parquet")),
        "episodios_df": pd.read_csv(
            settings.saida("episodios_csv"), encoding="utf-8-sig",
            parse_dates=["data_entrada_triagem", "data_destino_equalizacao"],
        ),
        "anomalias_df": pd.read_csv(settings.saida("anomalias_csv"), encoding="utf-8-sig"),
        "nao_classificadas_df": pd.read_csv(settings.saida("nao_classificadas_csv"), encoding="utf-8-sig"),
    }
