# Mineração de Métricas DORA — Lab03

Pipeline que seleciona repositórios populares com GitHub Actions, coleta
releases, commits entre releases e workflow runs do default branch, e calcula
as métricas DORA (Issues #1, #2, #4, #5 e #6 do GitHub Projects).

[![testes](https://github.com/Gmbferreira/Mineracao-Metricas-DORA/actions/workflows/testes.yml/badge.svg)](https://github.com/Gmbferreira/Mineracao-Metricas-DORA/actions/workflows/testes.yml)

## Requisitos

- Python 3.12 ou superior
- Um token de acesso do GitHub com escopo `repo` e `project`

```bash
pip install -r requirements.txt
```

## Execução

O pipeline roda com um único comando e lê o token da variável de ambiente
`GITHUB_TOKEN` (o token nunca é gravado em disco nem commitado):

```bash
export GITHUB_TOKEN=ghp_...
python -m pipeline --config config.yaml
```

No PowerShell, troque a primeira linha por `$env:GITHUB_TOKEN = "ghp_..."`.

O comando roda três etapas em sequência:

1. **selecao** — busca os candidatos, aplica os filtros e grava
   `data/amostra.csv` e o funil (Issue #1);
2. **coleta** — para cada repositório da amostra, coleta releases, commits
   entre releases e workflow runs (Issues #4 e #5);
3. **metricas** — calcula as métricas e grava `data/metricas.csv` e
   `data/releases.csv` (Issue #6).

Opções:

| Opção | Efeito |
|---|---|
| `--config caminho` | Arquivo de configuração (padrão: `config.yaml`) |
| `--etapas lista` | Etapas a executar, separadas por vírgula (padrão: `selecao,coleta,metricas`). Ex.: `--etapas coleta,metricas` reaproveita a `data/amostra.csv` existente |
| `--limite-repos N` | Coleta e métricas só dos N primeiros repositórios da amostra (útil para testar) |
| `--paralelo N` | Quantos repositórios são coletados ao mesmo tempo (padrão: 4). Dentro de cada um, os meses de runs e os compares também rodam em paralelo. Use `1` para coleta sequencial |
| `--smoke` | Teste de fumaça da seleção: 20 candidatos, alvo de 3 qualificados |
| `--max-candidatos N` | Limite de candidatos escaneados nesta execução |
| `--reiniciar` | Apaga os checkpoints em `data/checkpoints/` e recomeça |
| `--forcar-atualizacao` | Ignora o cache de respostas nesta execução e busca tudo de novo |

A coleta é **retomável**: cada etapa grava checkpoint em `data/checkpoints/` e
cada resposta da API é guardada no cache em `data/cache/`. Se a execução for
interrompida, rodar o mesmo comando continua de onde parou, sem repetir
requisições já feitas. Os checkpoints pertencem a uma janela/limites
específicos (gravados em `data/checkpoints/meta.json`); mudou a configuração,
use `--reiniciar`. Na coleta, cada repositório terminado vira um arquivo em
`data/coleta/`; rodar de novo pula os que já estão lá e tenta outra vez os que
deram erro.

## Cache, rate limit e resiliência (Issue #2)

- **Cache de respostas:** toda resposta `200` é salva em
  `data/cache/<repos__owner__repo>/<endpoint>__<hash>.json` (a busca de
  repositórios fica em `data/cache/search/`). Cada arquivo guarda a URL, os
  parâmetros, o corpo e os cabeçalhos relevantes (incluindo `Link`, usado na
  contagem de contribuidores). Ao rodar de novo, a resposta vem do cache sem
  tocar a rede; use `--forcar-atualizacao` para re-coletar.
- **Rate limit:** o cliente lê `X-RateLimit-Remaining`/`X-RateLimit-Reset` de
  cada resposta e **pausa automaticamente** antes da próxima requisição quando
  a cota zera, além de respeitar `Retry-After` e o limite de 30 buscas/min.
- **Backoff exponencial:** erros `5xx` e quedas de conexão são repetidos com
  espera crescente (1s, 2s, 4s, 8s, 16s, 32s, teto de 60 s, até 6 tentativas).
  Os valores ficam no bloco `rede:` do `config.yaml`.
- **Respostas reduzidas:** nos endpoints pesados (releases, compare e runs) o
  cache guarda só os campos usados. Uma página de runs passa de 1 MB e cai
  para poucos KB.

## Definições operacionais (Issue #1)

- **Janela de observação:** 2025-10-02 a 2026-10-02 (12 meses).
- **Busca de candidatos:** `stars >= 1000`, `fork:false`, `archived:false`,
  `pushed:>= 2025-10-02`, fatiada por faixas de estrelas com divisão adaptativa
  até ≤ 1000 resultados por consulta (limite da API de busca).
- **Inclusão:** repositório precisa ter, dentro da janela,
  - ≥ 5 releases publicadas (`draft=false` e `prerelease=false`); e
  - ≥ 50 workflow runs disparados por `push` no default branch.
- **Metadados coletados:** estrelas, linguagem principal, idade
  (anos até o fim da janela) e número de contribuidores (com quartis
  calculados sobre a amostra final).
- **Ordem de varredura:** estrelas decrescentes, parando ao atingir o alvo de
  100 repositórios (Sprint 01). A varredura é parcial por definição e continua
  na Sprint 02 até o alvo de 300+.

## Coleta de releases e commits (Issue #4)

- **Releases:** `GET /repos/{owner}/{repo}/releases` com `per_page=100` e
  `page`, até chegar a uma release publicada antes do início da janela (ela é
  a "release anterior" da primeira release da janela) ou ao fim do histórico.
  Todas as releases são guardadas, inclusive drafts e pré-releases, para as
  variantes da RQ 07.
- **Release avaliada:** `draft = false`, `prerelease = false` e `published_at`
  dentro da janela. A release anterior é a release válida imediatamente antes
  dela pela data de publicação, mesmo que fora da janela. A primeira release da
  história do repositório não tem anterior e fica fora do lead time.
- **Commits incluídos:** `GET /repos/{owner}/{repo}/compare/{anterior}...{R}`
  paginado com `per_page=100` e `page` até `total_commits` (o endpoint sem
  paginação para em 250). Tags com `/` ou outros caracteres especiais são
  codificadas na URL.
- **Erros no compare:** `404` (tag apagada ou reescrita) e `422` são
  registrados no `status_compare` da release, que fica fora do lead time e é
  contada em `releases_compare_falho`. Um erro persistente (5xx após o
  backoff) é registrado como `erro` e não interrompe a coleta.

## Coleta de workflow runs (Issue #5)

- `GET /repos/{owner}/{repo}/actions/runs` com `branch=<default_branch>`,
  `event=push` e `exclude_pull_requests=true`.
- A janela é dividida em meses de calendário (`created=AAAA-MM-DDTHH:MM:SSZ..`).
  Se um mês passa do teto de 1000 resultados da API, o intervalo é dividido ao
  meio até caber (chega a horas nos repositórios mais ativos). Se um intervalo
  de 1 minuto ainda passar do teto, ele é contado em `intervalos_no_teto`.
- Os runs são filtrados de novo no código (`event = push` e
  `head_branch = default_branch`) e repetidos são removidos pelo `id`.

## Métricas (Issues #4, #5 e #6)

O código fica no pacote `metricas/`, separado da coleta, e só recebe listas e
dicionários, então os testes não dependem da API.

| Métrica | Definição usada |
|---|---|
| Deployment frequency | releases avaliadas na janela ÷ semanas da janela (365 dias ÷ 7 ≈ 52,1) |
| Lead time (a) por release | `published_at` da release − data de autor do commit mais antigo incluído nela; mediana entre as releases |
| Lead time (b) por commit | `published_at` da release − data de autor de cada commit; mediana de todos os commits de todas as releases |
| CFR (a) proxy de CI | runs com falha ÷ (falhas + sucessos). Falha: `failure`, `timed_out`, `startup_failure`. Sucesso: `success`. O resto é ignorado |
| Tempo de recuperação | por workflow, em ordem de criação: o episódio começa na primeira falha após um sucesso e termina no próximo sucesso. Duração = `updated_at` do sucesso − `run_started_at` da primeira falha. Mediana dos episódios de todos os workflows |
| Classificação DORA (C1) | faixas da tabela de referência do enunciado com deployment frequency, lead time (a), CFR (a) e recuperação; geral = mediana das notas, arredondada para baixo |

Decisões tomadas onde o enunciado deixa margem:

- Release sem commits novos (compare vazio) não tem lead time e é contada em
  `releases_sem_commits`.
- Commit com data de autor depois da publicação da release daria lead time
  negativo; ele é descartado e contado em `commits_data_invalida`.
- Episódio de falha sem sucesso até o fim da janela é **censurado**: não entra
  na mediana e aparece em `episodios_censurados` e `proporcao_censurados`.
- Falhas no começo da janela, antes do primeiro sucesso daquele workflow, não
  têm início conhecido; não abrem episódio e são contadas em
  `falhas_sem_inicio`.
- Na classificação, métrica sem valor (ex.: nenhum episódio de recuperação)
  fica sem classe, e a classe geral usa a mediana das métricas disponíveis
  (`metricas_classificadas` diz quantas foram usadas).

## Saídas

| Arquivo | Conteúdo |
|---|---|
| `data/amostra.csv` | Amostra final com os metadados de cada repositório |
| `data/amostra_meta.json` | Janela, alvo, limites dos quartis e critério de cálculo |
| `data/funil.csv`, `data/funil.md` | Tabela do funil de seleção (candidatos → amostra) |
| `data/metricas.csv` | Uma linha por repositório com as métricas e a classificação DORA |
| `data/releases.csv` | Uma linha por release avaliada, com o resultado do compare e o lead time (a) |
| `data/coleta/` | Um JSON por repositório com releases, commits e runs coletados (gitignorado; base para as próximas sprints) |
| `data/checkpoints/` | JSONL por etapa (gitignorado; permite retomada) |
| `data/cache/` | Respostas da API em JSON (gitignorado; evita repetir chamadas) |

### Situação da coleta (Sprint 01)

A seleção chegou aos 100 repositórios (`data/amostra.csv`). Nesta sprint, a
coleta de releases, commits e runs e as métricas cobrem **48 desses 100**
(`data/metricas.csv`). Os repositórios mais ativos têm dezenas de milhares de
runs por ano (ex.: `NousResearch/hermes-agent` com 46 mil) e consomem mais
chamadas do que a cota de 5.000 por hora de um token. Os 52 restantes serão
coletados na Sprint 02 com o mesmo comando, que continua de onde parou sem
repetir as chamadas já feitas.

### Colunas de `data/metricas.csv`

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `full_name` | texto | — | `owner/repo` |
| `default_branch` | texto | — | campo `default_branch` da API |
| `releases_janela` | inteiro | releases | releases com `draft=false`, `prerelease=false` e `published_at` na janela |
| `deployment_frequency_semana` | decimal | releases/semana | `releases_janela` ÷ semanas da janela |
| `lead_time_a_horas` | decimal | horas | mediana do lead time por release (variante a) |
| `lead_time_b_horas` | decimal | horas | mediana do lead time por commit (variante b) |
| `releases_avaliadas` | inteiro | releases | releases que entraram no lead time |
| `releases_sem_anterior` | inteiro | releases | primeira release da história, sem anterior |
| `releases_compare_falho` | inteiro | releases | compare com 404, 422 ou erro |
| `releases_sem_commits` | inteiro | releases | compare sem commits novos |
| `releases_commits_truncados` | inteiro | releases | compare que passou do limite de 100 páginas (10 mil commits) |
| `commits_avaliados` | inteiro | commits | commits usados na variante (b) |
| `commits_data_invalida` | inteiro | commits | commits com data de autor depois da release |
| `runs_total` | inteiro | runs | workflow runs de push no default branch na janela |
| `runs_sucesso`, `runs_falha`, `runs_ignorados` | inteiro | runs | classificação pelo campo `conclusion` |
| `cfr_a` | decimal | fração (0–1) | `runs_falha` ÷ (`runs_falha` + `runs_sucesso`) |
| `recuperacao_horas` | decimal | horas | mediana dos episódios de falha recuperados |
| `episodios`, `episodios_censurados` | inteiro | episódios | total de episódios e quantos não terminaram na janela |
| `proporcao_censurados` | decimal | fração (0–1) | `episodios_censurados` ÷ `episodios` |
| `falhas_sem_inicio` | inteiro | runs | falhas antes do primeiro sucesso de cada workflow |
| `intervalos_runs`, `intervalos_no_teto` | inteiro | consultas | intervalos de data consultados e quantos ficaram no teto de 1000 |
| `classe_frequencia`, `classe_lead_time`, `classe_cfr`, `classe_recuperacao` | texto | Elite/High/Medium/Low | faixas da tabela de referência |
| `classe_geral` | texto | Elite/High/Medium/Low | mediana das notas, arredondada para baixo (combinação C1) |
| `metricas_classificadas` | inteiro | métricas | quantas das 4 métricas tinham valor |

Campo vazio quer dizer que a métrica não pôde ser calculada (ex.: nenhum
episódio de falha recuperado).

### Colunas de `data/releases.csv`

| Coluna | Tipo | Unidade | Origem / fórmula |
|---|---|---|---|
| `full_name` | texto | — | `owner/repo` |
| `tag_name`, `tag_anterior` | texto | — | tag da release e da release anterior usada no compare |
| `published_at` | data/hora UTC | — | campo `published_at` da release |
| `status_compare` | texto | — | `ok`, `sem_anterior`, `404`, `422` ou `erro` |
| `total_commits` | inteiro | commits | `total_commits` do compare |
| `commits_coletados` | inteiro | commits | commits efetivamente baixados |
| `truncado` | 0/1 | — | 1 se o compare passou do limite de páginas |
| `lead_time_horas` | decimal | horas | lead time (a) da release |
| `html_url` | texto | — | página da release no GitHub |

## Estrutura

```
pipeline/
├── __main__.py   CLI e orquestração das etapas
├── config.py     leitura e validação do config.yaml
├── cliente.py    cliente HTTP próprio (REST), cache, cota e backoff
├── cache.py      cache de respostas da API em JSON
├── busca.py      fatiamento por faixas de estrelas e candidatos
├── selecao.py    E1 (Actions), E2 (runs de push), E3 (releases)
├── metadados.py  idade, contribuidores, quartis
├── funil.py      tabela do funil (csv e md)
├── store.py      checkpoints JSONL e retomada
├── releases.py   releases e commits entre releases (compare)
├── runs.py       workflow runs com divisão da janela por mês
├── coleta.py     coleta por repositório da amostra, com retomada
└── consolidacao.py  metricas.csv e releases.csv
metricas/
├── comum.py      datas e mediana
├── frequencia.py deployment frequency
├── lead_time.py  lead time (a) e (b)
├── cfr.py        CFR (a)
├── recuperacao.py episódios de falha e tempo de recuperação
└── classificacao.py faixas DORA e classificação geral
tests/            testes unitários com fixtures
.github/workflows/testes.yml  CI: pytest com cobertura mínima de 80% em metricas/
artigo/           artigo no template SBC (Introdução e hipóteses)
```

## Artigo

O relatório final segue o template da SBC e é escrito aos poucos, uma seção por
sprint. Esta entrega (Issue #3) traz a Introdução e as hipóteses informais das
RQ 01 a RQ 07 em `artigo/`. Veja [`artigo/README.md`](artigo/README.md) para
instruções de Overleaf e compilação.

Artigo no Overleaf (leitura): <https://www.overleaf.com/read/rxydywpnvjym#6b20e1>

## Testes

```bash
python -m pytest tests/ -v
python -m pytest --cov=metricas --cov-report=term-missing --cov-fail-under=80
```

Os testes usam fixtures montadas à mão, incluindo os exemplos numéricos do
enunciado (release `v1.1` com lead time de 13 dias e o episódio de falha de
1h20), e casos de borda: release sem commits novos, falha nunca recuperada
(censurada), repositório com uma única release, runs `cancelled` e compare com
404. A coleta é testada com um cliente falso, sem acessar a rede.

O GitHub Actions roda os testes a cada push e pull request
(`.github/workflows/testes.yml`) e falha se a cobertura do pacote `metricas`
ficar abaixo de 80%.

## Limitações conhecidas

- A busca de repositórios é parcial (para no alvo da sprint); a tabela do funil
  documenta isso e é atualizada a cada execução.
- Releases são contadas a partir da primeira página (100 itens, mais recentes
  primeiro), com paginação enquanto a página mais antiga ainda estiver dentro
  da janela.
- Em monorepos com várias linhas de release (ex.: `vite@7.x` e
  `create-vite@8.x`) ou com branches de manutenção, a "release anterior" pela
  data pode estar em outro branch, e o compare traz muitos commits antigos.
  Isso infla principalmente a variante (b) do lead time.
- A data do commit é a data de autor; rebase e squash merge podem distorcê-la.
- O tempo de recuperação usa o estado final de cada run. Se um run com falha
  foi reexecutado com sucesso, a API mostra só a última tentativa.
