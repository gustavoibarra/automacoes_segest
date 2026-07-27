# Sistema de Equalização TRT12

Aplicação 100% local (nenhum dado é enviado a serviços externos) para consolidar, analisar e visualizar os dados de distribuição e redistribuição de processos judiciais do Sistema de Equalização do TRT12.

Produz:

- um banco de dados consolidado (Parquet/CSV/Excel);
- um dashboard interativo (Streamlit + Plotly);
- um relatório gerencial em DOCX;
- arquivos auxiliares de auditoria e qualidade dos dados;
- uma ferramenta de comparação entre a base consolidada e um log externo de processos;
- esta documentação.

## 1. Instalação

Requer Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Estrutura de entrada

```
projeto_equalizacao/
├── classificacao_unidades.xlsx   (ou .xls) — classificação das unidades permanentes
└── downloads/
    ├── processos_01-01-2026.csv
    ├── processos_08-01-2026.csv
    └── ...
```

- Os CSVs devem seguir o padrão de nome `processos_DD-MM-YYYY.csv` e conter as colunas `#Processo`, `Indicador`, `Município Sede`, `Órgão Julgador`, `Classe Judicial`, `Data`.
- **As primeiras linhas do arquivo não fazem parte da tabela.** As exportações do Sistema de Equalização trazem, antes do cabeçalho, algumas linhas de resumo do relatório (período, total de registros, data de geração etc.), normalmente ocupando as 6 primeiras linhas — a tabela de fato começa na linha 7, cujo cabeçalho começa com `#Processo`. O loader (`src/loaders.py`) localiza automaticamente a linha cujo primeiro campo é exatamente `#Processo` e descarta tudo o que vem antes; ele não assume um número fixo de linhas, então continua funcionando mesmo que o resumo tenha um tamanho ligeiramente diferente em algum arquivo.
- O separador de colunas é detectado automaticamente (`;` ou `,`) a partir da própria linha de cabeçalho — as exportações reais observadas usam `;`.
- Pequenas variações/erros de digitação no nome das colunas (ex.: `Municipío Sede` em vez de `Município Sede`, algo já observado em exportações reais) são toleradas: a comparação usa a mesma normalização de texto do restante do sistema (maiúsculas, sem acento), então a coluna é reconhecida mesmo com o acento fora do lugar.
- A coluna `Data` pode conter apenas a data ou data e hora (`01/07/2026` ou `01/07/2026 07:34:12`); ambas são aceitas.
- Encoding esperado: UTF-8.
- O arquivo de classificação deve conter uma coluna com o nome da unidade e outra com a classificação (`CEDENTE`, `NEUTRA` ou `DESTINATARIA`, com ou sem acento, singular ou plural). Os nomes das colunas são detectados automaticamente.
- Uma coluna opcional "Quantidade de Magistrados" habilita o grupo de medidas ponderadas por magistrado (cards, tabelas e gráficos de dispersão adicionais no dashboard, no relatório DOCX e na aba `Comparativo_Unidades` do Excel consolidado). Sem essa coluna, ou com valores ausentes/inválidos para alguma unidade, essas medidas aparecem como N/A para as unidades afetadas — o restante da análise continua funcionando normalmente.
- Unidades cujo nome contenha a palavra `TRIAGEM` nunca são tratadas como unidades permanentes.

`downloads/` e `classificacao_unidades.xlsx`/`.xls` na raiz são reservados para os **seus dados reais** — o projeto não inclui dados de exemplo nesses caminhos. Um conjunto de **dados fictícios** para teste/demonstração fica isolado em `exemplos/dados_ficticios/` (gerado por `scripts/gerar_dados_ficticios.py`), cobrindo os principais cenários de equalização. Para experimentar com eles sem misturar com dados reais:

```bash
python scripts/gerar_dados_ficticios.py
python main.py --downloads "./exemplos/dados_ficticios/downloads" \
  --classificacao "./exemplos/dados_ficticios/classificacao_unidades.xlsx" \
  --output "./exemplos/dados_ficticios/output"
```

## 3. Execução

### Consolidação via linha de comando

```bash
python main.py
```

Com parâmetros customizados:

```bash
python main.py --downloads "./downloads" --classificacao "./classificacao_unidades.xls" --output "./output"
```

Forçar reprocessamento ignorando o cache:

```bash
python main.py --atualizar
```

Gerar também o relatório gerencial em DOCX pela linha de comando:

```bash
python main.py --relatorio
```

### Dashboard

```bash
streamlit run app.py
```

O dashboard consolida os dados automaticamente na primeira execução (reaproveitando o cache do `main.py`, se existir) e oferece um botão **Atualizar dados** na barra lateral para forçar o reprocessamento quando os arquivos de entrada mudarem, além de **Gerar relatório DOCX** para baixar o relatório com os filtros aplicados no momento e **Baixar Excel consolidado (base completa)** para baixar a base inteira em Excel (sem os filtros da barra lateral — veja a seção 5.1).

### Testes

```bash
pytest
```

A suíte cobre os 9 cenários de aceitação obrigatórios (arquivo `tests/test_scenarios.py` e `tests/test_equalization.py`) além de testes unitários de normalização, histórico e métricas.

## 4. Arquitetura

Pipeline funcional em `src/`, com estágios independentes e testáveis:

```
loaders → validation → histories → equalization → metrics/filters → charts/reports/exports
```

| Módulo | Responsabilidade |
|---|---|
| `src/normalization.py` | Função central de normalização de texto (maiúsculas, sem acento, ordinais, hífens) |
| `src/loaders.py` | Leitura dos CSVs e do arquivo de classificação |
| `src/validation.py` | Deduplicação exata e anomalias de linha |
| `src/histories.py` | Reconstrução cronológica do histórico de cada processo (sem aplicar filtros) |
| `src/equalization.py` | Detecção de episódios de passagem por triagem e classificação da equalização |
| `src/metrics.py` | Cards executivos, cenários com/sem equalização, dispersão, analítico |
| `src/filters.py` | Aplicação dos filtros do dashboard sobre a base já reconstruída |
| `src/charts.py` | Gráficos Plotly reutilizados pelo dashboard e pelo relatório DOCX |
| `src/reports.py` | Geração do relatório gerencial em DOCX |
| `src/exports.py` | Escrita dos arquivos de saída e cache de consolidação |
| `src/pipeline.py` | Orquestração completa, compartilhada por `main.py` e `app.py` |
| `src/xlsx_utils.py` | Formatação compartilhada de planilhas Excel (cabeçalho, congelamento, autofiltro, largura de coluna) |
| `src/comparacao.py` | Comparação entre a base consolidada e um log externo de processos, usada por `comparar_processos.py` |

### Decisão de projeto: cenários com e sem equalização

Cada processo recebe duas colunas na tabela `processos_consolidados`:

- `unidade_final_real`: última unidade permanente do histórico cronológico (cenário **com** equalização);
- `unidade_simulada_sem_equalizacao`: unidade cedente imediatamente anterior à triagem, quando há equalização válida; caso contrário, a própria `unidade_final_real` (cenário **sem** equalização).

Como cada processo recebe exatamente uma unidade em cada cenário, os dois cenários sempre somam a mesma quantidade de "casos novos" — isso é verificado automaticamente (`src/metrics.py::validar_totais_cenarios`) e coberto pelo cenário de aceitação 7.

Episódios de passagem por triagem são detectados varrendo o histórico cronológico em busca de transições `UNIDADE PERMANENTE → TRIAGEM → UNIDADE PERMANENTE`. Todos os episódios de um processo vão para a tabela de auditoria `episodios_equalizacao.csv`; apenas o primeiro episódio **válido** define a origem/destino "oficiais" da equalização do processo (múltiplos episódios são sinalizados como anomalia, sem impedir a contagem única do processo).

Processos cuja unidade relevante não pertence ao universo de unidades classificadas (ex.: órgão julgador não cadastrado no arquivo de classificação) não aparecem nas tabelas por unidade, mas continuam contados em "casos novos" e ficam listados em `unidades_nao_classificadas.csv` — a verificação de consistência dos totais leva isso em conta explicitamente.

### Movimentações RESTITUIDO ("Restituído Por Redistribuição")

Movimentações cujo indicador seja "Restituído Por Redistribuição" são classificadas como `RESTITUIDO` (`src/normalization.py::normalize_indicador`) e **permanecem integralmente no histórico completo** (`movimentacoes_consolidadas` / aba `Movimentacoes`), para rastreabilidade — mas são excluídas de toda e qualquer análise: não contam em `quantidade_movimentos` nem `quantidade_redistribuicoes`, não participam da reconstrução do histórico usada para detectar equalização, não geram anomalia de ordem cronológica ambígua e não entram no relatório de unidades não classificadas. Se todas as movimentações de um processo forem RESTITUIDO, esse processo não aparece em `processos_consolidados` (não há nada a analisar), mas seus registros continuam no histórico completo. A quantidade de registros RESTITUIDO é reportada no log de processamento, no relatório DOCX e na aba `Resumo` do Excel consolidado.

## 5. Arquivos de saída (`output/`)

| Arquivo | Conteúdo |
|---|---|
| `movimentacoes_consolidadas.parquet` / `.csv` | Todas as movimentações, deduplicadas e ordenadas cronologicamente |
| `processos_consolidados.parquet` / `.csv` | Um registro por processo, com todos os campos derivados |
| `episodios_equalizacao.csv` | Auditoria de todos os episódios de passagem por triagem |
| `comparativo_unidades.csv` | Tabela unidade × cenário (com/sem equalização) |
| `fluxos_equalizacao.csv` | Rotas cedente → destinatária |
| `anomalias.csv` | Catálogo de anomalias encontradas |
| `unidades_nao_classificadas.csv` | Unidades citadas nos CSVs sem correspondência no arquivo de classificação |
| `consolidado_equalizacao.xlsx` | Base completa em Excel, para análise (ver seção 5.1) |
| `relatorio_equalizacao.docx` | Relatório gerencial |
| `log_processamento.txt` | Log de cada execução |

### 5.1 Exportação para Excel (`consolidado_equalizacao.xlsx`)

Gerado automaticamente a cada processamento (`python main.py`, `python main.py --atualizar`, ou ao abrir/atualizar o dashboard), com toda a base **sem filtros aplicados**, para facilitar análises fora do dashboard (tabelas dinâmicas, filtros do próprio Excel etc.). Contém uma aba por tabela:

| Aba | Conteúdo |
|---|---|
| `Resumo` | Indicadores de qualidade, arquivos utilizados e avisos da última execução |
| `Processos` | Um processo por linha, com todos os campos derivados (equivalente a `processos_consolidados.csv`) |
| `Movimentacoes` | Todas as movimentações consolidadas e ordenadas cronologicamente |
| `Episodios_Equalizacao` | Auditoria de episódios de passagem por triagem |
| `Comparativo_Unidades` | Tabela unidade × cenário (com/sem equalização) |
| `Fluxos_Equalizacao` | Rotas cedente → destinatária |
| `Anomalias` | Catálogo de anomalias encontradas |
| `Unidades_Nao_Classificadas` | Unidades citadas nos CSVs sem correspondência no arquivo de classificação |

Cada aba já vem com cabeçalho em negrito, primeira linha congelada e autofiltro. No dashboard, o botão **Baixar Excel consolidado (base completa)** na barra lateral baixa esse mesmo arquivo diretamente.

A documentação detalhada de cada aba e coluna do `consolidado_equalizacao.xlsx` — conteúdo, tipo e regra de negócio envolvida — está em [docs/Documentacao_Planilha_Consolidada.docx](docs/Documentacao_Planilha_Consolidada.docx). Para regenerá-la após alguma mudança de esquema:

```bash
python scripts/gerar_documentacao_planilhas.py
```

## 6. Comparação com o log de processos (`comparar_processos.py`)

Ferramenta separada para conferir uma relação de processos do log do Sistema de Equalização (um arquivo XLS/XLSX à parte, fora do padrão dos CSVs de entrada) contra a base já consolidada, respondendo a duas perguntas:

1. quais processos do log **não aparecem em lugar nenhum** da base consolidada;
2. para os que aparecem, **por que não foram considerados equalizados** (quando for o caso) — situação calculada (`EQUALIZADO_VALIDO`, `FORA_PADRAO`, `INCOMPLETA`, `NAO_EQUALIZADO`), motivo de invalidade e anomalias associadas (ex.: `PASSAGEM_TRIAGEM_INCOMPLETA`, `ORIGEM_EQUALIZACAO_NAO_CEDENTE`, `UNIDADE_NAO_CLASSIFICADA` etc.).

O arquivo de log deve conter as colunas `Processo`, `Unidade de Origem`, `Situação`, `Fase`, `Observação`, `Ocorrências Triagem`, `Erros Triagem`, `Ocorrências Territorial`, `Erros Territorial` (pequenas variações de acentuação/maiúsculas nos nomes das colunas são toleradas, como no restante do sistema).

```bash
python main.py                       # garante que output/consolidado_equalizacao.xlsx esta atualizado
python comparar_processos.py --log "./caminho/log_processos.xlsx"
```

Parâmetros opcionais: `--consolidado` (padrão `output/consolidado_equalizacao.xlsx`) e `--saida` (padrão `output/comparacao_log_equalizacao.xlsx`).

O relatório gerado (`comparacao_log_equalizacao.xlsx`) tem 5 abas: `Resumo` (contadores), `Nao_Encontrados`, `Encontrados_Nao_Equalizados`, `Encontrados_Equalizados` e `Todos` (tabela completa com as colunas originais do log mais os campos calculados da base).

## 7. Solução de erros comuns

**"Arquivo de classificacao de unidades nao encontrado"** — Verifique se `classificacao_unidades.xlsx` (ou `.xls`) existe na raiz do projeto, ou informe o caminho com `--classificacao`.

**"Nao foi possivel identificar as colunas do arquivo de classificacao"** — O arquivo precisa de uma coluna com o nome da unidade (ex.: `Unidade` ou `Órgão Julgador`) e uma com a classificação (ex.: `Classificação`). A mensagem de erro lista as colunas encontradas.

**"Nenhum arquivo no padrao processos_DD-MM-YYYY.csv foi encontrado"** — Confira o nome dos arquivos na pasta `downloads/` e o formato de data (`DD-MM-YYYY`). A extensão `.CSV`/`.csv` é aceita em qualquer caixa.

**"Nao foi possivel localizar a linha de cabecalho (iniciada por '#Processo')"** — O arquivo não segue o padrão de linhas de resumo + cabeçalho esperado, ou o cabeçalho está a mais de 50 linhas do início do arquivo. Abra o CSV e confirme que existe uma linha cujo primeiro campo é exatamente `#Processo`.

**"O arquivo ... nao contem as colunas esperadas"** — O cabeçalho foi localizado, mas alguma coluna obrigatória não foi reconhecida mesmo após a comparação tolerante a acento/maiúsculas. Confira o nome exato da coluna no arquivo (a mensagem lista as colunas encontradas) contra as esperadas: `#Processo`, `Indicador`, `Município Sede`, `Órgão Julgador`, `Classe Judicial`, `Data`.

**Aviso "quantidade de unidades diferente da esperada (62)"** — É apenas um alerta informativo; o processamento continua normalmente. Ajuste `quantidade_unidades_esperada` em `config.py` se o número correto para o seu tribunal for diferente de 62.

**Gráficos não aparecem no DOCX** — A geração de imagens usa o pacote `kaleido`. Se ele não estiver disponível no ambiente, o sistema tenta um gráfico de barras simplificado via `matplotlib` como contingência; instale `kaleido` (`pip install kaleido`) para os gráficos completos em alta resolução.

**Dashboard não atualiza após trocar os arquivos em `downloads/`** — Clique em "Atualizar dados" na barra lateral, ou rode `python main.py --atualizar`. O cache é invalidado automaticamente quando o tamanho ou a data de modificação de qualquer arquivo de entrada muda.

**`comparar_processos.py` — "Arquivo consolidado nao encontrado"** — Rode `python main.py` antes, para gerar `output/consolidado_equalizacao.xlsx`.

**`comparar_processos.py` — "O arquivo de log ... nao contem as colunas esperadas"** — Confira se o arquivo de log tem as 9 colunas esperadas (seção 6); a mensagem lista quais foram encontradas.

## 8. Convenções de contagem e formatação

- "Processo" é sempre `COUNT DISTINCT` do número do processo; "movimentação" conta linhas; "episódio" conta episódios de passagem por triagem; "unidade" conta unidades permanentes.
- Datas em `dd/mm/aaaa`, separador decimal por vírgula, separador de milhar por ponto, percentuais com uma ou duas casas decimais (`src/formatting.py`).
