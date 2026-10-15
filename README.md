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
diferentes) e **versão** SemVer. Dois sinais são usados:

- **patch**: o terceiro número da versão é maior que zero (`2.3.1`);
- **mensagens**: algum commit desde a release anterior tem `fix`, `hotfix`,
  `bugfix` ou `revert` na mensagem. Commits `fix(deps)` de atualização de
  dependência não contam.

Como o enunciado pede para validar a heurística contra o consenso da
amostra-ouro, deixei cinco versões prontas para comparar: só patch, só
mensagens, patch **e** mensagens, patch **ou** mensagens, e patch com a maioria
dos commits sendo correção. Até a validação, o dataset usa `patch e mensagens`.
Depois dela, fica a versão com melhor F1 (a escolhida aparece em
`data/dataset_meta.json`).

"Fix" é a palavra mais comum no começo das mensagens de commit da amostra
(cerca de 20%), então "ter algum commit de fix" sozinho tende a marcar quase
toda release como corretiva. Por isso testo também as versões que combinam os
dois sinais.

## Validação manual (Issues #8 a #12)

O passo a passo está em [`validacao/README.md`](validacao/README.md): sorteio
da amostra-ouro com semente fixa, planilha de cada avaliador, consenso e
avaliação da heurística com precisão, recall e F1.

## Saídas

| Arquivo | Conteúdo |
|---|---|
| `data/amostra.csv` | Amostra final com os metadados de cada repositório |
| `data/amostra_meta.json` | Janela, alvo, limites dos quartis e critério de cálculo |
| `data/funil.csv`, `data/funil.md` | Tabela do funil de seleção (candidatos → amostra) |
| `data/dataset.csv` | Dataset final: uma linha por repositório com metadados, quartis, métricas em todas as variantes e a classificação DORA |
| `data/dataset_meta.json` | Janela, limites dos quartis e versão da heurística usada no CFR (b) |
| `data/releases.csv` | Uma linha por release avaliada, com o resultado do compare e o lead time (a) |
| `data/DICIONARIO.md` | Dicionário de dados de todos os CSVs |
| `data/coleta/` | Um JSON por repositório com releases, commits e runs coletados (gitignorado; base para as próximas sprints) |
| `data/checkpoints/` | JSONL por etapa (gitignorado; permite retomada) |
| `data/cache/` | Respostas da API em JSON (gitignorado; evita repetir chamadas) |

O significado de cada coluna (tipo, unidade e fórmula) está em
[`data/DICIONARIO.md`](data/DICIONARIO.md).

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
└── consolidacao.py  dataset.csv, quartis e releases.csv
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
└── avaliacao.py  precisão, recall e F1 da heurística contra o consenso
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
- O tempo de recuperação usa o estado final de cada run. Se um run com falha
  foi reexecutado com sucesso, a API mostra só a última tentativa.
