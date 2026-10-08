# Mineração de Métricas DORA — Lab03

Pipeline de seleção de repositórios, coleta de metadados e registro do funil de
seleção (Issues #1 e #2 do GitHub Projects).

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

Opções:

| Opção | Efeito |
|---|---|
| `--config caminho` | Arquivo de configuração (padrão: `config.yaml`) |
| `--smoke` | Teste de fumaça: 20 candidatos, alvo de 3 qualificados |
| `--max-candidatos N` | Limite de candidatos escaneados nesta execução |
| `--reiniciar` | Apaga os checkpoints em `data/checkpoints/` e recomeça |
| `--forcar-atualizacao` | Ignora o cache de respostas nesta execução e busca tudo de novo |

A coleta é **retomável**: cada etapa grava checkpoint em `data/checkpoints/` e
cada resposta da API é guardada no cache em `data/cache/`. Se a execução for
interrompida, rodar o mesmo comando continua de onde parou, sem repetir
requisições já feitas. Os checkpoints pertencem a uma janela/limites
específicos (gravados em `data/checkpoints/meta.json`); mudou a configuração,
use `--reiniciar`.

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

## Saídas

| Arquivo | Conteúdo |
|---|---|
| `data/amostra.csv` | Amostra final com os metadados de cada repositório |
| `data/amostra_meta.json` | Janela, alvo, limites dos quartis e critério de cálculo |
| `data/funil.csv`, `data/funil.md` | Tabela do funil de seleção (candidatos → amostra) |
| `data/checkpoints/` | JSONL por etapa (gitignorado; permite retomada) |
| `data/cache/` | Respostas da API em JSON (gitignorado; evita repetir chamadas) |

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
└── store.py      checkpoints JSONL e retomada
tests/            testes unitários com fixtures
artigo/           artigo no template SBC (Introdução e hipóteses)
```

## Artigo

O relatório final segue o template da SBC e é escrito aos poucos, uma seção por
sprint. Esta entrega (Issue #3) traz a Introdução e as hipóteses informais das
RQ 01 a RQ 07 em `artigo/`. Veja [`artigo/README.md`](artigo/README.md) para
instruções de Overleaf e compilação.

## Testes

```bash
python -m pytest tests/ -v
python -m pytest tests/ --cov=pipeline --cov-report=term
```

## Limitações conhecidas

- A busca de repositórios é parcial (para no alvo da sprint); a tabela do funil
  documenta isso e é atualizada a cada execução.
- Releases são contadas a partir da primeira página (100 itens, mais recentes
  primeiro), com paginação enquanto a página mais antiga ainda estiver dentro
  da janela.
