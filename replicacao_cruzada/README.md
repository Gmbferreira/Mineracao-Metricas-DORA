# Replicação cruzada (Issues #22 e #23)

Replicamos o pipeline do grupo de Víctor Gabriel Cruz Pereira, Jonathan Sena da
Silva e Matheus Fernandes de Oliveira
([lab-medicao-e-experimentacao-de-software](https://github.com/Victorgabrielcruz/lab-medicao-e-experimentacao-de-software),
pasta `Lab03`), seguindo só o README deles, numa subamostra de 30 repositórios
do dataset que eles publicaram.

## Versão usada

- Commit `24b366ea2afe70359fc4595cd37ac0e292745efb` do `main` (22/10/2026,
  15:22 UTC).
- Só a pasta `Lab03`. O repositório inteiro tem cerca de 5,8 GB, quase tudo em
  `Lab03/entregas/` (compares e dados brutos compactados em partes de 40 MB),
  que o pipeline não usa para rodar. Ficaram de fora os arquivos `*.part*` e
  `*.zip` de `entregas/compares-500-final`, `entregas/dados-brutos-255` e
  `entregas/dados-brutos-500`.
- Windows 11, Python 3.12.10.

## Passo a passo

1. Clone só da pasta `Lab03`:

   ```bash
   git clone --filter=blob:none --no-checkout --depth 1 https://github.com/Victorgabrielcruz/lab-medicao-e-experimentacao-de-software.git rep-grupo
   cd rep-grupo
   git sparse-checkout init --no-cone
   git sparse-checkout set --no-cone '/Lab03/' \
     '!/Lab03/entregas/compares-500-final/*.part*' \
     '!/Lab03/entregas/dados-brutos-255/*.part*' '!/Lab03/entregas/dados-brutos-500/*.part*' \
     '!/Lab03/entregas/dados-brutos-255/*.zip' '!/Lab03/entregas/dados-brutos-500/*.zip'
   git checkout main
   ```

   No Git Bash do Windows, os caminhos que começam com `/` precisam de
   `MSYS_NO_PATHCONV=1` antes do `git sparse-checkout set`.

2. Ambiente, como no README deles (seção "Como executar"):

   ```powershell
   cd Lab03
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   Instalou sem erro.

3. Testes, como no README deles: `pytest --cov=pipeline --cov-fail-under=80`.
   Passaram 1.170 de 1.171, com cobertura de 95%. A falha é de codificação no
   Windows (problema 2 abaixo).

4. Subamostra: 30 repositórios sorteados do `dataset-500.csv` deles
   (`entregas/s02-03-dataset-500-final/`), com semente 42:

   ```bash
   python -m replicacao_cruzada.sorteio --dataset <Lab03>/entregas/s02-03-dataset-500-final/dataset-500.csv --saida replicacao_cruzada/dados
   ```

   Saem `dados/amostra_30.csv` e `dados/candidatos_30.json`, este no formato
   que o `--candidatos` do pipeline deles lê.

5. Coleta e métricas com o pipeline integrado deles. Uma cópia do `config.yaml`
   só com outras pastas (`caminhos.cache`, `caminhos.raw` e
   `caminhos.processed` em `data/replicacao/`), como o README sugere para
   pilotos:

   ```powershell
   $env:GITHUB_TOKEN = "..."
   .\.venv\Scripts\python.exe -m pipeline.integrado --config config-replicacao.yaml --candidatos <caminho>/candidatos_30.json --alvo 30 --max-candidatos 30
   ```

6. Exportação do CSV, com o comando da seção "Reexportação local" do README da
   entrega final deles:

   ```powershell
   .\.venv\Scripts\python.exe -m pipeline.dataset_csv --raw data/replicacao/raw --processed data/replicacao/processed --saida data/replicacao/dataset-30.csv --manifesto data/replicacao/manifesto.csv.json
   ```

7. Comparação com o CSV original:

   ```bash
   python -m replicacao_cruzada.comparar --original <Lab03>/entregas/s02-03-dataset-500-final/dataset-500.csv --replicado replicacao_cruzada/dados/dataset-30.csv --saida replicacao_cruzada/resultados
   ```

   Para cada métrica, `comparar.py` calcula a diferença relativa
   `(replicado − original) ÷ |original|` de cada repositório e a % de
   repositórios com a mesma classe DORA. A classe geral sai da regra da
   disciplina (mediana das notas de frequência, lead time (a), CFR (a) e
   recuperação, arredondada para baixo), calculada do mesmo jeito nos dois
   CSVs, porque o CSV deles não traz essa coluna.

## Problemas encontrados

Cada problema virou uma issue no repositório do grupo:
[#251](https://github.com/Victorgabrielcruz/lab-medicao-e-experimentacao-de-software/issues/251),
[#252](https://github.com/Victorgabrielcruz/lab-medicao-e-experimentacao-de-software/issues/252),
[#253](https://github.com/Victorgabrielcruz/lab-medicao-e-experimentacao-de-software/issues/253) e
[#254](https://github.com/Victorgabrielcruz/lab-medicao-e-experimentacao-de-software/issues/254),
na ordem abaixo.

1. **O README não explica como rodar o pipeline numa lista definida de
   repositórios.** Ele documenta a coleta completa (busca pela Search API), o
   `--piloto 100` e o `pipeline.integrado --alvo`, mas a replicação pede uma
   subamostra do dataset publicado. O `--candidatos` resolve, mas o formato do
   arquivo não está no README; foi preciso ler `pipeline/candidatos.py` para
   montá-lo.
2. **Um teste falha no Windows.** Em `tests/test_releases_snapshot.py`, linha
   23, `destino.read_text()` lê o JSON sem `encoding="utf-8"`. No Windows o
   padrão é cp1252, e "sequência" volta como "sequ�ncia". O pipeline grava em
   UTF-8 corretamente; só o teste lê errado.
3. **O repositório tem 5,8 GB por causa de `entregas/`.** O README não diz que
   dá para rodar sem esses dados. E, sem eles, dois módulos de teste
   (`test_compares_publicados.py` e `test_publicacao_500.py`) nem são
   carregados, porque importam `entregas/dados-brutos-500/restaurar.py`.

4. **A coleta aborta com 403 na virada da cota.** Quando a cota REST acaba, o
   cliente espera o reset (no nosso caso, 1.027 s). Se o GitHub ainda responde
   403 logo depois do reset, a espera calculada em `pipeline/rate_limit.py`
   (linhas 94 a 99, `max(0, reset + 1 - agora)`) dá zero, e as quatro
   repetições saem em sequência, sem pausa. A coleta terminou com código 2 no
   último repositório:

   ```text
   INFO Rate limit: aguardando 1027.5s antes de consultar /repos/zeroclaw-labs/zeroclaw/compare/v0.8.3...v0.8.4
   WARNING Rate limit HTTP 403: repetição 1/4 após 0.0s (...)
   WARNING Rate limit HTTP 403: repetição 4/4 após 0.0s (...)
   erro: HTTPError: 403 Client Error: Forbidden for url: https://api.github.com/repos/zeroclaw-labs/zeroclaw/compare/v0.8.3...v0.8.4?per_page=100&page=3
   ```

   Repetir o mesmo comando, como o README orienta, retomou do ponto em que
   parou e terminou com código 0 em cerca de um minuto.

## Resultados

**Execução.** A coleta começou às 16:20 e parou às 18:07 (problema 4); a
retomada levou 1 minuto, das 18:08 às 18:09. No total, cerca de 1 h 48 min e
8.663 respostas da API guardadas no cache deles. O `execucao.json` final
registra `execucao_completa=true` e os 30 repositórios elegíveis e completos.
A exportação do CSV funcionou de primeira, com as seis métricas para os 30.

**Comparação** (`resultados/comparacao_resumo.csv`):

| Métrica | Pares | Diferença relativa máxima | Mesma classe |
|---|---|---|---|
| deployment_frequency | 30 | 0 | 100% |
| lead_time_a | 30 | 0 | 100% |
| lead_time_b | 30 | 0 | 100% |
| cfr_a | 30 | 0 | 100% |
| cfr_b | 30 | 0 | 100% |
| tempo_recuperacao | 30 | 0 | 100% |
| classe geral | 30 | — | 100% |

Os valores das seis métricas saíram exatamente iguais aos do CSV original nos
30 repositórios. A coleta deles foi feita entre 14 e 20/10/2026 e a nossa em
22/10/2026, mas a janela (`[2025-10-01, 2026-10-01)`) já estava fechada nas
duas, e os valores iguais mostram que nada do que entra nas métricas mudou no
meio tempo. O que mudou foram só os metadados que não dependem da janela:
estrelas, nos 30
repositórios (até 4.043 a mais), e contribuidores, em 21 (até 63 de diferença).

**Conclusão.** O pipeline é reproduzível: seguindo o README, com uma dúvida
resolvida no código (problema 1) e uma retomada (problema 4), chegamos aos
mesmos valores e às mesmas classes. Não houve divergência de resultado para
relatar; os problemas abertos para o grupo são todos de execução e
documentação.
