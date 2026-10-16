# Validação manual (amostra-ouro)

Aqui ficam os arquivos da seção 6 do enunciado: o sorteio da amostra-ouro, as
planilhas que cada um de nós preenche, o consenso e a avaliação da heurística
de release corretiva.

## 1. Sorteio (issue #8)

```bash
python -m validacao.sorteio
```

O script sorteia 60 repositórios de `data/amostra.csv` e, de cada um, 5 releases
da janela. As duas etapas usam a semente `42`, definida em
`validacao/sorteio.py`, então rodar de novo sobre a mesma amostra dá o mesmo
resultado. Só entram no sorteio releases que têm uma release anterior, para a
planilha ter o link da lista de commits.

Saídas:

- `amostra_ouro.csv`: os 60 repositórios;
- `releases_ouro.csv`: as releases sorteadas, com os links;
- `rotulos_gabriel.xlsx` e `rotulos_guilherme.xlsx`: uma planilha por avaliador.

Se alguma planilha já existir, o script para sem mexer em nada, para não apagar
rótulos já preenchidos. `--sobrescrever` força a geração de novo.

## 2. Rotulagem (issues #10 e #11)

Cada um preenche só a própria planilha, sem conversar sobre os rótulos até os
dois terminarem, e sem olhar a saída da heurística (o CFR b do dataset ou o
resultado de `validacao.avaliacao`). A aba `instrucoes` explica cada coluna. Em
resumo:

- **tipo_projeto**: `biblioteca/framework`, `aplicacao/servico`,
  `ferramenta CLI` ou `outro`;
- **entregas_reais**: se as releases do repositório são versões que chegam ao
  usuário (`sim`, `nao` ou `incerto`);
- **corretiva**: se o objetivo principal da release é corrigir um defeito
  recente (`sim` ou `nao`), lendo as release notes e a lista de commits.

As colunas de resposta só aceitam as opções da lista. Ao terminar, salve com o
mesmo nome e faça o commit na sua issue de rotulagem.

## 3. Concordância e consenso (issue #12)

```bash
python -m validacao.concordancia
```

O script lê as planilhas `rotulos_*.xlsx`, calcula o kappa de Fleiss de cada
dimensão (com `aggregate_raters` e `fleiss_kappa` do statsmodels, como o
enunciado pede), interpreta o valor pela escala de Landis & Koch e lista os
casos divergentes. Ele se recusa a rodar enquanto alguma planilha estiver
incompleta, então a rotulagem (issues #10 e #11) precisa terminar antes.

O leitor aceita dois layouts de planilha: o padrão, com as abas `repositorios` e
`releases` geradas pelo sorteio, e o achatado, com uma aba e uma linha por
release repetindo os rótulos do repositório (comum em planilhas reexportadas).
Os rótulos são comparados sem diferenciar maiúsculas/acentos (`não` = `nao`,
`aplicação/serviço` = `aplicacao/servico`), e nomes de coluna alternativos como
`entrega_real` e `release_corretiva` também são aceitos.

Para gerar a pauta da discussão de desempate, com o repositório, a tag e os
links de cada caso divergente:

```bash
python -m validacao.concordancia --pauta validacao/pauta_divergencias.csv
```

O CSV traz uma linha por divergência com os rótulos de cada avaliador e duas
colunas em branco (`consenso` e `motivo`) para preencher na reunião.

**Protocolo de desempate** (definido antes de olhar as divergências): cada caso
divergente é discutido pelos avaliadores com a evidência de apoio (release notes
e lista de commits) até chegarem a um acordo, registrado em
`validacao/decisoes_desempate.csv` (colunas `dimensao,id,consenso,motivo`). Se
não houver acordo, o caso vai para reunião e a decisão final, com o motivo, fica
registrada no comentário da issue #12.

O consenso deve ser gravado em dois CSVs, que são a entrada da avaliação
da heurística:

- `consenso_repositorios.csv`: `id_repo`, `full_name`, `tipo_projeto`,
  `entregas_reais`;
- `consenso_releases.csv`: `id_release`, `full_name`, `tag_name`, `corretiva`.

Os valores são os mesmos das planilhas (`sim`/`nao` etc.).

## 4. Avaliação da heurística (issue #9)

```bash
python -m validacao.avaliacao
```

Compara cada versão da heurística de `metricas/corretiva.py` com o
`consenso_releases.csv` e calcula precisão, recall e F1
(`precision_recall_fscore_support` do scikit-learn). O resultado vai para
`avaliacao_heuristica.csv`. O script lê as mensagens de commit de
`data/coleta/`, então a coleta precisa ter rodado antes
(`python -m pipeline --etapas coleta`).
