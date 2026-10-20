# Mineração de Métricas DORA — Lab03

Pipeline que seleciona repositórios populares com GitHub Actions, coleta
releases, commits entre releases e workflow runs do default branch, e calcula
as métricas DORA (Issues #1, #2, #4, #5 e #6 do GitHub Projects). Na Sprint 02
entram a amostra final, o CFR (b) e a validação manual (Issues #7 a #13).

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
3. **metricas** — calcula as métricas e grava o dataset final
   `data/dataset.csv` e `data/releases.csv` (Issues #6 e #7).

Opções:

| Opção | Efeito |
|---|---|
| `--config caminho` | Arquivo de configuração (padrão: `config.yaml`) |
| `--etapas lista` | Etapas a executar, separadas por vírgula (padrão: `selecao,coleta,metricas`). Ex.: `--etapas coleta,metricas` reaproveita a `data/amostra.csv` existente |
| `--limite-repos N` | Coleta e métricas só dos N primeiros repositórios da amostra (útil para testar) |
| `--amostra caminho` | CSV com os repositórios da coleta e das métricas (padrão: `data/amostra.csv`); serve para rodar uma subamostra |
| `--saida pasta` | Pasta onde gravar `dataset.csv`, `releases.csv`, `variantes.csv` e `dataset_meta.json` (padrão: `data`) |
| `--paralelo N` | Quantos repositórios são coletados ao mesmo tempo (padrão: 4). Dentro de cada um, os meses de runs e os compares também rodam em paralelo, com no máximo 3 requisições por vez. Use `1` para coleta sequencial |
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

## Replicação em uma subamostra (Issue #21)

Para o grupo que vai replicar o estudo em 30 repositórios do nosso dataset. Não
é preciso refazer a seleção: a subamostra sai da nossa amostra final
(`data/amostra.csv`), e os nossos valores para os mesmos repositórios estão em
`data/dataset.csv` e `data/variantes.csv`.

1. Clone o repositório e instale as dependências (Python 3.12):

   ```bash
   git clone https://github.com/Gmbferreira/Mineracao-Metricas-DORA.git
   cd Mineracao-Metricas-DORA
   python -m venv .venv
   source .venv/bin/activate        # no Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

   No Windows, clone numa pasta de caminho curto (por exemplo `C:\rep`). Um
   arquivo do scikit-learn passa de 260 caracteres dentro de `.venv` quando o
   caminho é longo, e o `pip install` falha com "Long Path support".

2. Defina o token do GitHub (não precisa de escopo especial, os repositórios
   são públicos): `export GITHUB_TOKEN=ghp_...`, ou no PowerShell
   `$env:GITHUB_TOKEN = "ghp_..."`.

3. Sorteie os 30 repositórios (semente fixa, o resultado é sempre o mesmo):

   ```bash
   python -m pipeline.subamostra --n 30 --semente 42 --max-runs 20000 --saida replicacao/amostra_30.csv
   ```

   O `--max-runs 20000` deixa de fora os repositórios com mais de 20 mil
   workflow runs na janela (31 dos 300). Sem ele, a semente 42 sorteia, por
   exemplo, o `openclaw/openclaw`, que sozinho tem 414 mil runs e consome horas
   da cota de 5.000 chamadas REST por hora. Com o filtro, a coleta dos 30
   repositórios leva por volta de uma a duas horas; sem ele, pode passar de seis.

4. Rode a coleta e as métricas só para a subamostra, gravando os resultados em
   outra pasta para não sobrescrever os nossos:

   ```bash
   python -m pipeline --config config.yaml --etapas coleta,metricas --amostra replicacao/amostra_30.csv --saida replicacao
   ```

   Se a execução parar (cota, rede ou `Ctrl+C`), é só rodar o mesmo comando:
   ela continua de onde parou.

5. Compare `replicacao/dataset.csv` e `replicacao/variantes.csv` com as linhas
   dos mesmos repositórios em `data/dataset.csv` e `data/variantes.csv`. As
   colunas estão em [`data/DICIONARIO.md`](data/DICIONARIO.md).

Diferenças pequenas são esperadas: releases e tags podem ter sido apagadas ou
reescritas depois da nossa coleta, e os quartis (`quartil_*`) são calculados
sobre os repositórios do próprio CSV, então mudam numa subamostra de 30. A janela
de observação é fixa (`config.yaml`), por isso commits e runs novos não entram.
A coluna `intervalos_runs` também pode mudar sem afetar as métricas: ela conta
as consultas feitas na API de runs, e parte dos nossos repositórios foi coletada
mês a mês na Sprint 01, antes de a coleta passar a tentar a janela inteira
primeiro.

Testamos estes passos num clone novo do repositório, com uma subamostra de 2
repositórios (`--n 2 --max-runs 300`): a coleta levou cerca de 1 minuto (6
chamadas REST e 46 GraphQL), e as métricas saíram iguais às nossas.

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
  300 repositórios (amostra final da Sprint 02; na Sprint 01 o alvo era 100). A
  varredura é parcial por definição, e o funil mostra quantos candidatos
  ficaram sem olhar.

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
- **Commits incluídos:** o compare entre a release anterior e a release R.
  Na Sprint 01 ele saía todo do REST
  (`GET /repos/{owner}/{repo}/compare/{anterior}...{R}`, paginado com
  `per_page=100` e `page` até `total_commits`). O compare era 61% das chamadas
  da coleta, então na Sprint 02 ele passou a sair primeiro da API GraphQL
  (objeto `Comparison`), que tem uma cota própria de 5.000 pontos por hora e
  deixa a cota REST para os workflow runs. A GraphQL devolve os mesmos commits
  do REST, na mesma ordem, mas só os 1.000 mais recentes; quando o compare é
  maior que isso, os mais antigos vêm das primeiras páginas do REST. Antes de
  trocar, comparei os dois em 150 pares de releases sorteados entre os
  repositórios já coletados (8 deles com mais de 1.000 commits): os 150 deram
  os mesmos commits, as mesmas datas de autor e as mesmas mensagens. Se a
  GraphQL responder com erro, o compare sai todo pelo REST, como antes.
- **Erros no compare:** `404` (tag apagada ou reescrita) e `422` são
  registrados no `status_compare` da release, que fica fora do lead time e é
  contada em `releases_compare_falho`. Um erro persistente (5xx após o
  backoff) é registrado como `erro` e não interrompe a coleta.

## Coleta de workflow runs (Issue #5)

- `GET /repos/{owner}/{repo}/actions/runs` com `branch=<default_branch>`,
  `event=push` e `exclude_pull_requests=true`.
- Primeiro vai uma consulta da janela inteira. Se ela tem até 1.000 runs (o
  teto da API com filtros), a coleta usa essa consulta e pronto. Senão, a
  janela é dividida em meses de calendário (`created=AAAA-MM-DDTHH:MM:SSZ..`),
  como o enunciado pede para repositórios muito ativos. Se um mês passa do
  teto, o intervalo é dividido ao meio até caber (chega a horas nos
  repositórios mais ativos). Se um intervalo de 1 minuto ainda passar do teto,
  ele é contado em `intervalos_no_teto`.
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
| CFR (b) proxy de entrega | releases que falharam ÷ releases avaliadas. A release falha quando a próxima release da mesma linha sai em até 7 dias e é corretiva. Releases dos últimos 7 dias da janela ficam fora (censura) |
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

### Heurística de release corretiva (Issue #9)

Fica em `metricas/corretiva.py`. A tag é separada em **linha** (o prefixo, que
em monorepos identifica o pacote: `vite@7.1.0` e `create-vite@8.0.1` são linhas
diferentes) e **versão** SemVer. Três sinais são usados:

- **patch**: o terceiro número da versão é maior que zero (`2.3.1`);
- **mensagens**: algum commit desde a release anterior tem `fix`, `hotfix`,
  `bugfix` ou `revert` na mensagem. Commits `fix(deps)` de atualização de
  dependência não contam;
- **notas**: as release notes usam palavras de correção (`fix`, `bug`,
  `regression`, `crash`, `security`, `CVE`...) pelo menos tantas vezes quanto
  palavras de funcionalidade (`feature`, `add`, `new`, `support`,
  `improve`...). Release sem notas conta como empate.

**Validação contra o consenso da amostra-ouro** (300 releases, 107 corretivas
no consenso; `python -m validacao.avaliacao`, resultado em
`validacao/avaliacao_heuristica.csv`):

| Versão | Regra | Precisão | Recall | F1 |
|---|---|---|---|---|
| v1 | patch | 0,48 | 0,86 | 0,62 |
| v2 | mensagens | 0,36 | 0,83 | 0,50 |
| v3 | patch **e** mensagens | 0,51 | 0,74 | 0,60 |
| v4 | patch **ou** mensagens | 0,36 | 0,95 | 0,53 |
| v5 | patch e maioria dos commits é correção | 0,68 | 0,25 | 0,37 |
| **v6** | **patch e notas** | **0,67** | **0,78** | **0,72** |

As cinco primeiras versões foram escritas antes da rotulagem e nenhuma chegou a
0,70. "Fix" é a palavra mais comum no começo das mensagens de commit da amostra
(cerca de 20%), então os sinais das mensagens erram muito: marcam como corretiva
quase toda release com algum conserto no meio. Olhando os erros da v1, os falsos
positivos eram patches que traziam funcionalidade nova, e era nas release notes
que isso aparecia. A v6 foi criada depois dessa análise e é a usada no CFR (b)
do dataset (o nome fica em `data/dataset_meta.json`). Antes de chegar nela,
testei estas regras contra o mesmo consenso, sem transformá-las em versões do
código:

| Regra exploratória | Precisão | Recall | F1 |
|---|---|---|---|
| patch e nenhum commit `feat:` | 0,62 | 0,69 | 0,66 |
| patch e commits de correção ≥ commits de funcionalidade | 0,54 | 0,85 | 0,66 |
| patch e proporção de commits de correção ≥ 0,2 | 0,57 | 0,69 | 0,63 |
| patch e nenhum commit de funcionalidade (`add`, `new`, `support`...) | 0,71 | 0,50 | 0,58 |
| patch e até 7 dias depois da release anterior | 0,53 | 0,63 | 0,57 |
| patch e até 50 commits | 0,50 | 0,59 | 0,54 |
| notas com alguma palavra de correção e correção ≥ funcionalidade, sem exigir patch* | 0,64 | 0,72 | 0,68 |
| patch e notas sem seção de funcionalidade* | 0,57 | 0,76 | 0,65 |

\* calculadas com os primeiros 1.500 caracteres das release notes; a v6 usa as
notas inteiras.

Como a v6 foi escolhida olhando os mesmos 300 casos, o F1 dela tende a sair um
pouco otimista. Separando os 60 repositórios em metades, ele variou entre 0,64
e 0,79 (ids ímpares 0,64; pares 0,79; 1 a 30 0,73; 31 a 60 0,72). As release
notes vêm da API GraphQL (`pipeline/notas.py`) e ficam no JSON de cada
repositório em `data/coleta/`.

## Validação manual (Issues #8 a #12)

O passo a passo está em [`validacao/README.md`](validacao/README.md): sorteio
da amostra-ouro com semente fixa, planilha de cada avaliador, consenso e
avaliação da heurística com precisão, recall e F1.

## Variantes da RQ 07 (Issue #14)

A RQ 07 compara a classificação DORA em três combinações de definições:

| Combinação | Unidade de deploy | Lead time | CFR |
|---|---|---|---|
| C1 (referência) | release | (a) | (a) |
| C2 | release + pré-release | (b) | (b) |
| C3 | tag | (b) | (a) |

Para isso a etapa `coleta` junta duas unidades de deploy além da release
(`pipeline/variantes.py`):

- **release + pré-release:** sai da lista de releases já coletada, agora sem
  tirar as pré-releases. As release notes das pré-releases são buscadas para o
  CFR (b).
- **tag:** a lista vem da API GraphQL (`refs` ordenadas pela data do commit),
  porque o `GET /tags` do REST não traz data. Cada tag é datada pelo commit
  para o qual aponta, como pede o enunciado.

Os commits de cada par (unidade anterior, unidade) vêm do mesmo `compare` do
lead time. Os pares que já existiam na release principal são reaproveitados, e
os novos vão em consultas GraphQL de 25 pares por vez; um par com mais de 100
commits, ou que volte com erro, é refeito sozinho pelo caminho normal (GraphQL
e REST). Repositório que já tinha sido coletado recebe só as variantes, sem
repetir o resto.

A etapa `metricas` grava `data/variantes.csv`, com as métricas de cada unidade
e a classificação em C1, C2 e C3 (colunas no dicionário de dados).

## Análises (Issues #17 e #18)

Cada análise é um script que lê os CSVs de `data/` e grava tabelas, gráficos e
um resumo em markdown em `analises/resultados/`:

```bash
python -m analises.rq07_sensibilidade
python -m analises.rq08_rework
```

Os resumos de cada métrica trazem média, mediana, moda, quartis e IQR
(`analises/comum.py`). As métricas são muito assimétricas, então a mediana é o
valor principal; a média e a moda entram como complemento. Em dado contínuo, em
que nenhum valor se repete, a moda fica vazia.

- **RQ 07** (`rq07_sensibilidade.py`): distribuição e moda da classe geral em
  cada combinação; para cada par (C1×C2, C1×C3, C2×C3) e cada métrica, a % de
  repositórios que mudam de classe e o kappa de Cohen ponderado
  (`cohen_kappa_score(..., weights="linear")`); as matrizes de transição; e o
  efeito de trocar um fator de cada vez em relação à C1 (unidade, lead time ou
  CFR). Gráficos: matrizes de transição (`rq07_transicoes.png`) e barras da
  classe geral por combinação com boxplot da frequência por unidade
  (`rq07_classes_e_unidades.png`).
- **RQ 08** (`rq08_rework.py`): rework rate de cada repositório
  (`releases_corretivas ÷ releases_janela`, com a mesma heurística do CFR (b)),
  média, mediana, moda e IQR, e a comparação com o CFR (b): Spearman, Wilcoxon
  pareado e diferença pareada. Gráficos: histograma das duas métricas com média,
  mediana e moda (`rq08_distribuicao.png`) e dispersão rework rate × CFR (b)
  (`rq08_rework_x_cfr_b.png`).

## Saídas

| Arquivo | Conteúdo |
|---|---|
| `data/amostra.csv` | Amostra final com os metadados de cada repositório |
| `data/amostra_meta.json` | Janela, alvo, limites dos quartis e critério de cálculo |
| `data/funil.csv`, `data/funil.md` | Tabela do funil de seleção (candidatos → amostra) |
| `data/dataset.csv` | Dataset final: uma linha por repositório com metadados, quartis, métricas em todas as variantes e a classificação DORA |
| `data/dataset_meta.json` | Janela, limites dos quartis e versão da heurística usada no CFR (b) |
| `data/releases.csv` | Uma linha por release avaliada, com o resultado do compare e o lead time (a) |
| `data/variantes.csv` | Métricas por unidade de deploy e classificação em C1, C2 e C3 (RQ 07) |
| `data/DICIONARIO.md` | Dicionário de dados de todos os CSVs |
| `analises/resultados/` | Tabelas, gráficos e resumos das análises da RQ 07 e da RQ 08 |
| `data/coleta/` | Um JSON por repositório com releases, commits e runs coletados (gitignorado; base para as próximas sprints) |
| `data/checkpoints/` | JSONL por etapa (gitignorado; permite retomada) |
| `data/cache/` | Respostas da API em JSON (gitignorado; evita repetir chamadas) |

O significado de cada coluna (tipo, unidade e fórmula) está em
[`data/DICIONARIO.md`](data/DICIONARIO.md).

### Situação da coleta (Sprint 02)

A amostra final tem 300 repositórios, e a coleta terminou para todos, sem
nenhum erro: 21.203 releases na janela e cerca de 3 milhões de workflow runs.
A última rodada, depois da troca do compare para a GraphQL, usou 23.210
chamadas REST e 13.510 GraphQL em cerca de 5 horas. Os 100 repositórios da
Sprint 01 continuam com exatamente os mesmos valores.

O CFR (b) do dataset usa a v6 da heurística (patch e notas), escolhida na
validação com a amostra-ouro (Issue #9). Com ela, a mediana do CFR (b) ficou em
0,22 (IQR de 0,08 a 0,44), em 299 repositórios; só o `expo/expo` fica sem valor,
pela censura.

### Situação da coleta (Sprint 03)

As variantes da RQ 07 (pré-releases e tags) foram coletadas para os 300
repositórios, sem erros. Quase todos saíram em poucas horas; o que demorou foram
os repositórios com tags em vários branches (ClickHouse, node, php-src), em que
a tag anterior pela data costuma estar em outro branch e o compare traz milhares
de commits, e o `pytorch/pytorch`, com 9.674 tags na janela, quase todas criadas
pela CI (`ciflow/*`, `trunk/<sha>`, `viable/strict/*`). No meio da coleta, a
API GraphQL passou a recusar consultas com o erro `RATE_LIMIT` mesmo com pontos
sobrando no cabeçalho `X-RateLimit-Remaining`; o cliente agora reconhece esse
erro e espera o reset (Issue #21).

## Estrutura

```
pipeline/
├── __main__.py   CLI e orquestração das etapas
├── config.py     leitura e validação do config.yaml
├── cliente.py    cliente HTTP próprio (REST e GraphQL), cache, cota e backoff
├── cache.py      cache de respostas da API em JSON
├── busca.py      fatiamento por faixas de estrelas e candidatos
├── selecao.py    E1 (Actions), E2 (runs de push), E3 (releases)
├── metadados.py  idade, contribuidores, quartis
├── funil.py      tabela do funil (csv e md)
├── store.py      checkpoints JSONL e retomada
├── releases.py   releases e commits entre releases (compare)
├── notas.py      release notes (GraphQL)
├── variantes.py  pré-releases e tags para a RQ 07
├── runs.py       workflow runs com divisão da janela por mês
├── coleta.py     coleta por repositório da amostra, com retomada
├── consolidacao.py  dataset.csv, quartis, releases.csv e variantes.csv
└── subamostra.py sorteio da subamostra para a replicação
metricas/
├── comum.py      datas e mediana
├── frequencia.py deployment frequency
├── lead_time.py  lead time (a) e (b)
├── cfr.py        CFR (a) e CFR (b)
├── corretiva.py  heurística de release corretiva (versões avaliadas)
├── recuperacao.py episódios de falha e tempo de recuperação
└── classificacao.py faixas DORA e classificação geral
validacao/
├── sorteio.py    sorteio da amostra-ouro e planilhas de rotulagem
├── concordancia.py kappa de Fleiss entre os avaliadores
├── consenso.py   rótulos de consenso depois do desempate
└── avaliacao.py  precisão, recall e F1 da heurística contra o consenso
analises/
├── comum.py      mediana, IQR e tabelas
├── rq07_sensibilidade.py  RQ 07: mudança de classe e kappa entre C1, C2 e C3
└── rq08_rework.py RQ 08: rework rate e comparação com o CFR (b)
tests/            testes unitários com fixtures
.github/workflows/testes.yml  CI: pytest com cobertura mínima de 80% em metricas/
artigo/           artigo no template SBC
```

## Artigo

O relatório final segue o template da SBC e é escrito aos poucos, uma seção por
sprint: Introdução e hipóteses na Sprint 01 (Issue #3), Metodologia na Sprint
02 (Issue #13), Resultados e Discussão na Sprint 03 (Issues #19 e #20) e
Ameaças à Validade e Replicação Cruzada na entrega final (Issues #25 e #26).
Veja [`artigo/README.md`](artigo/README.md) para instruções de Overleaf e
compilação.

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

Na Sprint 02 entraram os testes da heurística de release corretiva e do CFR (b)
(com o exemplo `v2.3.0 → v2.3.1` do enunciado, monorepos, prazo de 7 dias e
censura no fim da janela), do sorteio (mesmo resultado com a mesma semente e
planilha sem a saída da heurística) e da avaliação (o exemplo de precisão 0,75
e recall 0,60 da seção 6).

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
- Alguns repositórios publicam muitas releases de uma vez. O `expo/expo`
  publicou as 267 releases da janela entre 29/09 e 01/10/2026: isso infla a
  frequência de deploy e deixa o CFR (b) sem valor, porque todas caem nos
  últimos 7 dias da janela e são censuradas.
- O tempo de recuperação usa o estado final de cada run. Se um run com falha
  foi reexecutado com sucesso, a API mostra só a última tentativa.
- Na variante por tag (RQ 07) entram todas as tags, como pede o enunciado,
  inclusive as que a CI cria para disparar workflows (o `pytorch/pytorch` tem
  9.674 na janela). A tag é datada pelo commit para o qual aponta, que pode ser
  bem anterior à criação da tag.
