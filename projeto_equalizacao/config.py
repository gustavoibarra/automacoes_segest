"""Configuracoes centrais do sistema de analise de equalizacao do TRT12.

Todos os caminhos sao relativos a raiz do projeto (nunca absolutos), para que
o projeto possa ser movido ou executado em qualquer maquina sem ajustes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


# Pasta padrão de onde ler os CSVs de processos: a pasta de downloads do
# projeto saopje (saopje_download_rel_proc_distribuidos.py salva os
# relatórios diários ali). Pode ser sobrescrita via Settings.downloads_dir
# ou `--downloads` na linha de comando, caso os arquivos estejam em outro
# lugar.
DOWNLOADS_DIR_PADRAO = BASE_DIR.parent / "saopje" / "downloads"


@dataclass
class Settings:
    base_dir: Path = BASE_DIR
    downloads_dir: Path = DOWNLOADS_DIR_PADRAO
    output_dir: Path = BASE_DIR / "output"

    # O enunciado cita ora .xls, ora .xlsx para o arquivo de classificacao.
    # O loader procura por ambos, nessa ordem.
    classificacao_candidatos: tuple = (
        "classificacao_unidades.xls",
        "classificacao_unidades.xlsx",
    )

    csv_prefixo: str = "processos_"
    csv_sufixo: str = ".csv"
    csv_encoding: str = "utf-8"
    data_arquivo_formato: str = "%d-%m-%Y"

    colunas_csv_esperadas: tuple = (
        "#Processo",
        "Indicador",
        "Município Sede",
        "Órgão Julgador",
        "Classe Judicial",
        "Data",
    )

    palavra_triagem: str = "TRIAGEM"
    quantidade_unidades_esperada: int = 60

    cache_meta_filename: str = "_cache_meta.json"

    arquivos_saida: dict = field(default_factory=lambda: {
        "movimentacoes_parquet": "movimentacoes_consolidadas.parquet",
        "movimentacoes_csv": "movimentacoes_consolidadas.csv",
        "processos_parquet": "processos_consolidados.parquet",
        "processos_csv": "processos_consolidados.csv",
        "episodios_csv": "episodios_equalizacao.csv",
        "comparativo_csv": "comparativo_unidades.csv",
        "fluxos_csv": "fluxos_equalizacao.csv",
        "anomalias_csv": "anomalias.csv",
        "nao_classificadas_csv": "unidades_nao_classificadas.csv",
        "consolidado_excel": "consolidado_equalizacao.xlsx",
        "relatorio_docx": "relatorio_equalizacao.docx",
        "log_processamento": "log_processamento.txt",
    })

    def classificacao_path(self) -> Path | None:
        for nome in self.classificacao_candidatos:
            caminho = self.base_dir / nome
            if caminho.exists():
                return caminho
        return None

    def saida(self, chave: str) -> Path:
        return self.output_dir / self.arquivos_saida[chave]


SETTINGS = Settings()
