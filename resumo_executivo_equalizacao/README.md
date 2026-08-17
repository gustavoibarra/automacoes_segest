# Resumo Executivo do Sistema de Equalização TRT12

Gera um resumo executivo em DOCX a partir do arquivo consolidado produzido pelo `projeto_equalizacao` (pasta irmã), no padrão visual e estrutural de `Relatorio_Executivo_Sistema_Equalizacao_Atualizado_29-07-2026.docx`: capa com faixa de indicadores, análise em duas dimensões (quantidade de processos por unidade e carga de trabalho por magistrado), comparação por grupo de unidades (cedentes/destinatárias/neutras) e anexos detalhados por unidade.

Projeto independente — não importa nada de `projeto_equalizacao`, apenas lê o arquivo `.xlsx` que ele gera.

## Instalação

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

```bash
python main.py
```

Sem parâmetros, usa `../projeto_equalizacao/output/consolidado_equalizacao.xlsx` e o período integral disponível na base (da primeira `data_caso_novo` até a última `data_ultimo_movimento`).

Parâmetros opcionais:

```bash
python main.py --arquivo "./caminho/outro_consolidado.xlsx"
python main.py --inicio 01/07/2026 --fim 29/07/2026
python main.py --saida "./output/meu_relatorio.docx"
```

O nome do arquivo de saída, quando não informado, inclui o período resolvido: `Resumo_Executivo_Equalizacao_DD-MM-AAAA_a_DD-MM-AAAA.docx`.

## O que é lido do consolidado

Apenas 3 abas do `consolidado_equalizacao.xlsx`:

- **Processos** — um registro por processo, usado para os indicadores de "casos novos" (por `data_caso_novo`) e para localizar a unidade final real / simulada sem equalização / cedente / destinatária de cada processo.
- **Movimentacoes** — usada para determinar quais processos tiveram alguma movimentação (exceto `RESTITUIDO`) dentro do período analisado.
- **Comparativo_Unidades** — fornece a lista mestra de unidades permanentes (nome, classificação, quantidade de magistrados), estática e independente do período.

## Duas contagens de processos, por design

O relatório distingue deliberadamente:

- **Casos novos**: processos cuja `data_caso_novo` cai dentro do período — usados nos KPIs "casos novos" e "processos equalizados".
- **Processos movimentados**: processos com qualquer movimentação (exceto `RESTITUIDO`) dentro do período — usados em todas as tabelas comparativas por unidade (Figuras 1/2, comparação por grupo, anexos). Esse universo pode incluir processos cuja distribuição inicial é anterior ao período, mas que tiveram uma redistribuição dentro dele.

Os dois totais podem divergir; quando isso acontece, o relatório inclui automaticamente uma nota explicando a diferença.

## Indicador central: coeficiente de variação (CV)

Diferente do `relatorio_equalizacao.docx` do projeto principal (que usa a redução do MAD como indicador central), este resumo executivo usa a **redução do coeficiente de variação** como indicador de eficiência, classificado em 5 faixas:

| CV | Classificação |
|---|---|
| 0% a 10% | Distribuição bastante homogênea |
| Acima de 10% a 20% | Dispersão relativamente baixa |
| Acima de 20% a 30% | Dispersão relevante |
| Acima de 30% a 40% | Dispersão elevada |
| Acima de 40% | Dispersão muito elevada |

## Testes

```bash
pytest
```

## Estrutura

```
resumo_executivo_equalizacao/
├── main.py            # CLI
├── config.py           # caminhos padrao, cores, fontes, faixas de CV
├── assets/
│   └── logo_trt12.png  # logo usado no cabecalho (extraido do documento de referencia)
├── src/
│   ├── formatting.py    # formatacao pt-BR (numero, percentual, data)
│   ├── dados.py          # leitura do consolidado, resolucao de periodo, casos novos x movimentados
│   ├── metricas.py        # KPIs, dispersao com faixa de CV, comparacao por grupo, convergencia, anexos
│   ├── graficos.py         # graficos matplotlib (comparativo por grupo, CV com faixas coloridas)
│   └── relatorio.py         # montagem completa do DOCX
└── tests/
```
