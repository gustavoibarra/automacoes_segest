"""
main.py

Ponto de entrada único das automações desta pasta. Cada automação vive no
seu próprio projeto (login_pje/, saopje/, projeto_equalizacao/); este
script só pergunta o que fazer e despacha para o projeto certo.

Uso:
    python main.py                          # pergunta a opção interativamente
    python main.py 10                       # baixa o relatório (período padrão)
    python main.py 10 01/07/2026 26/07/2026  # baixa o relatório (período customizado)
    python main.py 20                       # atualiza a base consolidada de equalização
"""

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

OPCOES = {
    "10": {
        "descricao": "Baixar arquivos: relatório de processos distribuídos no primeiro grau",
        "comando": [sys.executable, "-m", "saopje.saopje_download_rel_proc_distribuidos"],
        "cwd": BASE_DIR,
    },
    "20": {
        "descricao": "Atualizar base consolidada do sistema de equalização",
        "comando": [sys.executable, "main.py", "--atualizar"],
        "cwd": BASE_DIR / "projeto_equalizacao",
    },
    "30": {
        "descricao": "Gerar relatório TÉCNICO DOCX",
        "comando": [sys.executable, "main.py", "--relatorio"],
        "cwd": BASE_DIR / "projeto_equalizacao",
    },    
    "31": {
        "descricao": "Gerar relatório NEGOCIAL DOCX",
        "comando": [sys.executable, "main.py"],
        "cwd": BASE_DIR / "resumo_executivo_equalizacao",
    },
    "40": {
        "descricao": "Abrir Dashboard do sistema de equalização",
        "comando": ["streamlit", "run", "app.py"],
        "cwd": BASE_DIR / "projeto_equalizacao",
    },    
}


def _perguntar_opcao() -> str:
    print("O que você deseja fazer?")
    for chave, opcao in OPCOES.items():
        print(f"  {chave} - {opcao['descricao']}")
    escolha = input("Opção: ").strip()
    if escolha not in OPCOES:
        print(f"[ERRO] Opção inválida: {escolha!r}")
        sys.exit(1)
    return escolha


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if argv:
        opcao, extra_args = argv[0], argv[1:]
        if opcao not in OPCOES:
            print(f"[ERRO] Opção inválida: {opcao!r}. Opções válidas: {', '.join(OPCOES)}")
            return 1
    else:
        opcao, extra_args = _perguntar_opcao(), []

    config = OPCOES[opcao]
    resultado = subprocess.run([*config["comando"], *extra_args], cwd=str(config["cwd"]))
    return resultado.returncode


if __name__ == "__main__":
    raise SystemExit(main())
