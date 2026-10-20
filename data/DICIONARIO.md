# Dicionário de dados

Este arquivo descreve cada coluna dos CSVs gerados pelo pipeline e pela
validação manual. Datas estão em UTC, no formato ISO 8601. Campo vazio quer
dizer que o valor não pôde ser calculado (por exemplo, um repositório sem
nenhum episódio de falha recuperado não tem tempo de recuperação).

Todos os arquivos usam a janela de observação de **2025-10-02 a 2026-10-02**
(datas inclusivas), definida no `config.yaml`.

## `data/amostra.csv`

Gerado pela etapa `selecao`. Uma linha por repositório da amostra final.

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `full_name` | texto | — | `owner/repo`, campo `full_name` da busca |
| `html_url` | texto | — | página do repositório no GitHub |
| `stars` | inteiro | estrelas | `stargazers_count` no momento da busca |
| `linguagem` | texto | — | `language` da API (linguagem principal) |
| `idade_anos` | decimal | anos | (fim da janela − `created_at`) ÷ 365,25 |
| `contributors` | inteiro | pessoas | número da última página de `GET /contributors?per_page=1&anon=true` |
| `quartil_contribuidores` | inteiro | 1 a 4 | quartil de `contributors` dentro da amostra |
| `created_at` | data/hora | — | `created_at` da API |
| `default_branch` | texto | — | `default_branch` da API |
| `faixa_estrelas` | texto | — | faixa de estrelas da busca em que o repositório apareceu |

`data/amostra_meta.json` guarda a janela, o alvo e os limites dos quartis de
contribuidores.

## `data/funil.csv`

Uma linha por etapa do funil de seleção (também em `data/funil.md`, com notas).

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `etapa` | texto | — | nome da etapa |
| `entrada` | inteiro | repositórios | quantos chegaram na etapa |
| `saida` | inteiro | repositórios | quantos passaram |
| `descartados` | inteiro | repositórios | `entrada − saida` |
| `motivo` | texto | — | por que os descartados saíram |

## `data/dataset.csv`

Dataset final, gerado pela etapa `metricas`. Uma linha por repositório, com os
metadados da amostra e as métricas DORA em todas as variantes obrigatórias.

**Metadados**

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `full_name`, `html_url`, `linguagem`, `stars`, `idade_anos`, `contributors`, `created_at`, `default_branch` | — | — | iguais a `data/amostra.csv` |
| `quartil_estrelas` | inteiro | 1 a 4 | quartil de `stars` no dataset |
| `quartil_idade` | inteiro | 1 a 4 | quartil de `idade_anos` no dataset |
| `quartil_contribuidores` | inteiro | 1 a 4 | quartil de `contributors` no dataset |

Os quartis usam os percentis 25, 50 e 75 com interpolação linear; um valor igual
ao limite fica no grupo de baixo. Os limites estão em `data/dataset_meta.json`.

**Frequência de deploy (RQ 01)**

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `releases_janela` | inteiro | releases | releases com `draft = false`, `prerelease = false` e `published_at` na janela |
| `deployment_frequency_semana` | decimal | releases por semana | `releases_janela` ÷ (365 ÷ 7) |

**Lead time (RQ 02)**

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `lead_time_a_horas` | decimal | horas | variante (a): para cada release, `published_at` − data de autor do commit mais antigo dela; mediana entre as releases |
| `lead_time_b_horas` | decimal | horas | variante (b): `published_at` da release − data de autor de cada commit; mediana de todos os commits |
| `releases_avaliadas` | inteiro | releases | releases que entraram no lead time |
| `releases_sem_anterior` | inteiro | releases | primeira release da história do repositório (sem anterior para comparar) |
| `releases_compare_falho` | inteiro | releases | `compare` com 404, 422 ou erro; ficam fora do lead time |
| `releases_sem_commits` | inteiro | releases | `compare` sem nenhum commit novo |
| `releases_commits_truncados` | inteiro | releases | `compare` em que nem todos os commits foram baixados: acima de 10 mil commits (100 páginas do REST), ou de 11 mil quando os 1.000 mais recentes vieram da GraphQL |
| `commits_avaliados` | inteiro | commits | commits usados na variante (b) |
| `commits_data_invalida` | inteiro | commits | commits com data de autor depois da publicação da release (descartados) |

**Taxa de falha (RQ 03)**

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `runs_total` | inteiro | runs | workflow runs de `push` no default branch criados na janela |
| `runs_sucesso` | inteiro | runs | `conclusion = success` |
| `runs_falha` | inteiro | runs | `conclusion` = `failure`, `timed_out` ou `startup_failure` |
| `runs_ignorados` | inteiro | runs | qualquer outro `conclusion` (`cancelled`, `skipped`, vazio...) |
| `cfr_a` | decimal | fração (0 a 1) | variante (a), proxy de CI: `runs_falha` ÷ (`runs_falha` + `runs_sucesso`) |
| `cfr_b` | decimal | fração (0 a 1) | variante (b), proxy de entrega: `releases_falha_cfr_b` ÷ `releases_avaliadas_cfr_b` |
| `releases_avaliadas_cfr_b` | inteiro | releases | releases da janela com os 7 dias seguintes ainda dentro da janela |
| `releases_falha_cfr_b` | inteiro | releases | releases cuja próxima release da mesma linha saiu em até 7 dias e é corretiva |
| `releases_censuradas_cfr_b` | inteiro | releases | releases dos últimos 7 dias da janela (não dá para saber se houve correção) |
| `releases_corretivas` | inteiro | releases | releases da janela que a heurística marca como corretivas |

A heurística de release corretiva usada no CFR (b) está em
`metricas/corretiva.py`, e o nome da versão em uso fica em
`data/dataset_meta.json` (`heuristica_cfr_b`). A versão atual (v6) marca como
corretiva a release de patch (`2.3.1`) cujas release notes usam palavras de
correção pelo menos tantas vezes quanto palavras de funcionalidade; ela teve F1
de 0,72 contra o consenso da amostra-ouro. "Mesma linha" quer dizer o mesmo
prefixo de tag: em um monorepo, `vite@7.1.0` e `create-vite@8.0.1` são linhas
diferentes.

**Tempo de recuperação (RQ 04)**

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `recuperacao_horas` | decimal | horas | mediana dos episódios recuperados: `updated_at` do sucesso − `run_started_at` da primeira falha, dentro de cada workflow |
| `episodios` | inteiro | episódios | episódios de falha (primeira falha depois de um sucesso) |
| `episodios_censurados` | inteiro | episódios | episódios sem sucesso até o fim da janela |
| `proporcao_censurados` | decimal | fração (0 a 1) | `episodios_censurados` ÷ `episodios` |
| `falhas_sem_inicio` | inteiro | runs | falhas antes do primeiro sucesso de cada workflow na janela (não abrem episódio) |
| `intervalos_runs` | inteiro | consultas | intervalos de data consultados na API de runs |
| `intervalos_no_teto` | inteiro | consultas | intervalos que ficaram no teto de 1000 resultados mesmo com 1 minuto |

**Classificação DORA (combinação C1: release, lead time a, CFR a)**

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `classe_frequencia` | texto | Elite/High/Medium/Low | faixa de `deployment_frequency_semana` |
| `classe_lead_time` | texto | Elite/High/Medium/Low | faixa de `lead_time_a_horas` |
| `classe_cfr` | texto | Elite/High/Medium/Low | faixa de `cfr_a` |
| `classe_recuperacao` | texto | Elite/High/Medium/Low | faixa de `recuperacao_horas` |
| `classe_geral` | texto | Elite/High/Medium/Low | notas 4 a 1 das quatro métricas; mediana arredondada para baixo |
| `metricas_classificadas` | inteiro | métricas | quantas das quatro métricas tinham valor |

As faixas são as da tabela de referência do enunciado (seção 5, RQ 07).

## `data/releases.csv`

Uma linha por release da janela (sem draft e sem pré-release).

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `full_name` | texto | — | `owner/repo` |
| `tag_name` | texto | — | tag da release |
| `tag_anterior` | texto | — | release anterior pela data de publicação, usada no `compare` |
| `published_at` | data/hora | — | `published_at` da release |
| `status_compare` | texto | — | `ok`, `sem_anterior`, `404`, `422` ou `erro` |
| `total_commits` | inteiro | commits | `total_commits` do `compare` |
| `commits_coletados` | inteiro | commits | commits efetivamente baixados |
| `truncado` | 0 ou 1 | — | 1 se nem todos os commits do `compare` foram baixados (ver `releases_commits_truncados`) |
| `lead_time_horas` | decimal | horas | lead time (a) da release |
| `html_url` | texto | — | página da release no GitHub |

## `data/variantes.csv`

Gerado pela etapa `metricas`, para a RQ 07. Uma linha por repositório, com as
métricas calculadas em cada unidade de deploy e a classificação nas três
combinações de definições:

| Combinação | Unidade de deploy | Lead time | CFR |
|---|---|---|---|
| C1 (referência) | release | (a) | (a) |
| C2 | release + pré-release | (b) | (b) |
| C3 | tag | (b) | (a) |

O sufixo `<unidade>` das colunas é uma destas:

- `release`: a mesma unidade de `data/dataset.csv` (`draft = false` e
  `prerelease = false`);
- `release_pre`: releases e pré-releases (só `draft = false`). Cada uma é
  comparada com a anterior pela data de publicação, contando as pré-releases;
- `tag`: todas as tags do repositório, datadas pelo commit para o qual apontam
  (`committedDate`; numa tag anotada, o commit apontado por ela). Cada tag é
  comparada com a anterior pela mesma data.

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `full_name` | texto | — | `owner/repo` |
| `unidades_<unidade>` | inteiro | unidades | unidades de deploy na janela |
| `deployment_frequency_<unidade>` | decimal | unidades por semana | `unidades_<unidade>` ÷ (365 ÷ 7) |
| `lead_time_a_<unidade>` | decimal | horas | lead time (a) calculado com essa unidade |
| `lead_time_b_<unidade>` | decimal | horas | lead time (b) calculado com essa unidade |
| `cfr_b_release`, `cfr_b_release_pre` | decimal | fração (0 a 1) | CFR (b) com essa unidade. Tag não tem release notes, então não há `cfr_b_tag` |
| `cfr_a` | decimal | fração (0 a 1) | igual a `data/dataset.csv`; não depende da unidade |
| `recuperacao_horas` | decimal | horas | igual a `data/dataset.csv`; não depende da unidade |
| `classe_<metrica>_<combinacao>` | texto | Elite/High/Medium/Low | faixa de `frequencia`, `lead_time`, `cfr` e `recuperacao`, e a classe `geral`, em `c1`, `c2` e `c3` |

As colunas de C1 repetem a classificação de `data/dataset.csv`. As análises da
RQ 07 e da RQ 08 ficam em `analises/` e gravam os resultados em
`analises/resultados/` (ver o README).

## Validação manual (`validacao/`)

**`validacao/amostra_ouro.csv`**: os 60 repositórios sorteados.

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `id_repo` | inteiro | — | número do repositório na amostra-ouro (1 a 60) |
| `full_name`, `html_url` | texto | — | iguais a `data/amostra.csv` |

**`validacao/releases_ouro.csv`**: as 5 releases sorteadas de cada repositório.

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `id_release` | inteiro | — | número da release na amostra-ouro |
| `id_repo` | inteiro | — | repositório ao qual a release pertence |
| `full_name`, `tag_name`, `tag_anterior`, `published_at` | — | — | iguais a `data/releases.csv` |
| `link_release` | texto | — | página da release (release notes) |
| `link_commits` | texto | — | página do GitHub com os commits entre `tag_anterior` e `tag_name` |

**`validacao/rotulos_<avaliador>.xlsx`**: planilha de cada avaliador. Repete as
colunas acima e acrescenta as respostas:

| Coluna | Aba | Valores |
|---|---|---|
| `tipo_projeto` | repositorios | `biblioteca/framework`, `aplicacao/servico`, `ferramenta CLI`, `outro` |
| `entregas_reais` | repositorios | `sim`, `nao`, `incerto` |
| `corretiva` | releases | `sim`, `nao` |
| `observacao` | as duas | texto livre |

**`validacao/concordancia.csv`**: uma linha por dimensão rotulada
(`python -m validacao.concordancia --saida validacao/concordancia.csv`).

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `dimensao` | texto | — | `tipo_projeto`, `entregas_reais` ou `corretiva` |
| `itens` | inteiro | itens | repositórios (60) ou releases (300) comparados |
| `avaliadores` | inteiro | pessoas | número de planilhas comparadas |
| `concordancia_bruta` | decimal | fração (0 a 1) | itens em que todos os avaliadores deram o mesmo rótulo ÷ itens |
| `kappa` | decimal | −1 a 1 | kappa de Fleiss (`aggregate_raters` e `fleiss_kappa` do statsmodels) |
| `interpretacao` | texto | — | escala de Landis & Koch (pobre, leve, razoavel, moderada, substancial, quase perfeita) |
| `divergencias` | inteiro | itens | itens sem unanimidade |

**`validacao/pauta_divergencias.csv`**: os casos divergentes, com o material de
apoio e a decisão do desempate.

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `dimensao`, `id` | texto, inteiro | — | dimensão e `id_repo`/`id_release` do caso |
| `full_name`, `tag` | texto | — | repositório e, nas releases, a tag |
| `link_release`, `link_commits` | texto | — | página da release (ou do repositório) e lista de commits |
| `gabriel`, `guilherme` | texto | — | rótulo de cada avaliador |
| `consenso`, `motivo` | texto | — | rótulo final e motivo, iguais a `decisoes_desempate.csv` |

**`validacao/decisoes_desempate.csv`**: uma linha por caso em que as duas
planilhas discordaram.

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `dimensao` | texto | — | `tipo_projeto`, `entregas_reais` ou `corretiva` |
| `id` | inteiro | — | `id_repo` (nas duas primeiras dimensões) ou `id_release` |
| `consenso` | texto | — | rótulo final, com os mesmos valores das planilhas |
| `motivo` | texto | — | por que esse rótulo foi escolhido |

**`validacao/consenso_repositorios.csv`** e **`validacao/consenso_releases.csv`**:
rótulo final depois do desempate. Têm as mesmas colunas de identificação
(`id_repo`/`id_release`, `full_name` e, nas releases, `tag_name`) e as colunas
de resposta acima, com os mesmos valores.

**`validacao/avaliacao_heuristica.csv`**: uma linha por versão da heurística de
release corretiva.

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `versao` | texto | — | nome da versão em `metricas/corretiva.py` |
| `precisao` | decimal | fração (0 a 1) | das releases que a heurística marcou, quantas o consenso confirma |
| `recall` | decimal | fração (0 a 1) | das corretivas do consenso, quantas a heurística achou |
| `f1` | decimal | fração (0 a 1) | 2 · precisão · recall ÷ (precisão + recall) |
| `verdadeiros_positivos`, `falsos_positivos`, `falsos_negativos` | inteiro | releases | contagens usadas no cálculo |
| `releases` | inteiro | releases | releases avaliadas |
| `corretivas_no_consenso` | inteiro | releases | releases marcadas como corretivas no consenso |
