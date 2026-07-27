from src.normalization import (
    is_unidade_triagem,
    normalize_classificacao,
    normalize_indicador,
    normalize_processo_numero,
    normalize_text,
    normalize_unit_name,
)


def test_maiusculas_e_acentos():
    assert normalize_text("órgão júlgador") == "ORGAO JULGADOR"


def test_espacos_duplicados():
    assert normalize_text("VARA   DO   TRABALHO") == "VARA DO TRABALHO"


def test_espacos_inicio_fim():
    assert normalize_text("  VARA DO TRABALHO  ") == "VARA DO TRABALHO"


def test_ordinais_equivalentes():
    a = normalize_text("1ª VARA DO TRABALHO DE FLORIANOPOLIS")
    b = normalize_text("1A VARA DO TRABALHO DE FLORIANOPOLIS")
    c = normalize_text("1º VARA DO TRABALHO DE FLORIANOPOLIS")
    assert a == b == c == "1 VARA DO TRABALHO DE FLORIANOPOLIS"


def test_hifen_normalizado():
    assert normalize_text("VARA – DO TRABALHO") == normalize_text("VARA - DO TRABALHO")


def test_nao_faz_correspondencia_aproximada():
    assert normalize_text("1 VARA DO TRABALHO DE FLORIANOPOLIS") != normalize_text("2 VARA DO TRABALHO DE FLORIANOPOLIS")


def test_indicador_redistribuicao_antes_de_distribuicao():
    assert normalize_indicador("Redistribuição") == "REDISTRIBUICAO"
    assert normalize_indicador("Distribuição") == "DISTRIBUICAO"
    assert normalize_indicador("Redistribuicao por prevencao") == "REDISTRIBUICAO"


def test_indicador_outro_e_nao_identificado():
    assert normalize_indicador("Baixa definitiva") == "OUTRO"
    assert normalize_indicador("") == "NAO_IDENTIFICADO"
    assert normalize_indicador(None) == "NAO_IDENTIFICADO"


def test_classificacao_com_variacoes():
    assert normalize_classificacao("Cedente") == "CEDENTE"
    assert normalize_classificacao("cedentes") == "CEDENTE"
    assert normalize_classificacao("Destinatária") == "DESTINATARIA"
    assert normalize_classificacao("Destinatarias") == "DESTINATARIA"
    assert normalize_classificacao("NEUTRAS") == "NEUTRA"
    assert normalize_classificacao("desconhecido") is None


def test_processo_preserva_zeros_e_pontuacao():
    assert normalize_processo_numero("0001234-56.2024.5.12.0001") == "0001234-56.2024.5.12.0001"
    assert normalize_processo_numero("  0001234-56.2024.5.12.0001  ") == "0001234-56.2024.5.12.0001"


def test_unidade_triagem_insensivel_a_caixa_e_acento():
    assert is_unidade_triagem(normalize_unit_name("Setor de Triagem 1")) is True
    assert is_unidade_triagem(normalize_unit_name("triagem")) is True
    assert is_unidade_triagem(normalize_unit_name("1 Vara do Trabalho")) is False
