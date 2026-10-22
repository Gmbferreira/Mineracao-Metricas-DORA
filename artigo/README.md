# Artigo (template SBC)

Documento do relatório final da disciplina, escrito aos poucos (uma seção por
sprint), no template da SBC: Introdução e hipóteses (Sprint 01), Metodologia
(Sprint 02), Resultados e Discussão (Sprint 03), Ameaças à Validade e
Replicação Cruzada (entrega final).

Artigo no Overleaf (leitura): <https://www.overleaf.com/read/rxydywpnvjym#6b20e1>

## Arquivos

| Arquivo | Papel |
|---|---|
| `main.tex` | Documento principal |
| `figuras/` | Figuras geradas pelas análises (`analises/resultados/`) |
| `referencias.bib` | Bibliografia (DORA, Accelerate, Wohlin, SemVer, bibliotecas de análise) |
| `sbc-template.sty` | Estilo oficial da SBC (v2017) |
| `sbc.bst` | Estilo bibliográfico da SBC |

## Como abrir no Overleaf

1. Acesse <https://www.overleaf.com/latex/templates/sbc-conferences-template/blbxwjwzdngr>
   e clique em **Open as Template** (ou crie um projeto em branco).
2. Substitua o conteúdo do projeto pelos arquivos desta pasta
   (`main.tex`, `referencias.bib`, `sbc-template.sty`, `sbc.bst` e a pasta
   `figuras/`). O `artigo.zip` já traz tudo isso.
3. Defina **Menu → Main document = `main.tex`**.
4. Compile. A bibliografia exige a sequência
   `pdfLaTeX → BibTeX → pdfLaTeX → pdfLaTeX` (o Overleaf costuma fazer isso
   automaticamente ao detectar o `\bibliography`).

## Como compilar localmente (opcional)

Requer uma distribuição TeX com `pdflatex` e `bibtex` (TeX Live ou MiKTeX):

```bash
pdflatex main
bibtex main
pdflatex main
pdflatex main
```

## Conteúdo atual

- Introdução e hipóteses informais das RQ 01 a RQ 07, redigidas **antes** da
  análise dos dados (RQ 08 é bônus, sem hipótese).
- Metodologia: fonte de dados e funil de seleção, janela e definições
  operacionais, variantes obrigatórias, protocolo e resultado da validação
  manual. Os rótulos e o desempate da amostra-ouro foram feitos com apoio de
  modelos de linguagem, com autorização da disciplina.
- Resultados das RQ 01 a RQ 08: métricas e classificação DORA (RQ 01-04),
  relação velocidade × estabilidade (RQ 05), características associadas ao
  desempenho (RQ 06), análise de sensibilidade (RQ 07) e \emph{rework rate}
  (RQ 08).
- Discussão confrontando as hipóteses com os resultados (RQ 01-07).
- Ameaças à Validade nas quatro categorias (Issue #25).
- A Replicação Cruzada entra pela Issue #26.

## Observações

- Os arquivos de compilação (`*.aux`, `*.bbl`, `*.blg`, `*.log`, `*.out`,
  `*.pdf`) são ignorados pelo Git; não versione o PDF.
- Ao usar `\cite`, garanta que a chave existe em `referencias.bib`.
