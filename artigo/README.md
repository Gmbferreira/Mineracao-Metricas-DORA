# Artigo (template SBC)

Documento do relatório final da disciplina, escrito aos poucos (uma seção por
sprint), no template da SBC. Esta sprint entrega a **Introdução** e as
**hipóteses informais** das RQ 01 a RQ 07 (Issue #3).

Artigo no Overleaf (leitura): <https://www.overleaf.com/read/rxydywpnvjym#6b20e1>

## Arquivos

| Arquivo | Papel |
|---|---|
| `main.tex` | Documento principal (cabeçalho, resumo/abstract, Introdução e hipóteses) |
| `referencias.bib` | Bibliografia (DORA, Accelerate, Wohlin, SemVer, bibliotecas de análise) |
| `sbc-template.sty` | Estilo oficial da SBC (v2017) |
| `sbc.bst` | Estilo bibliográfico da SBC |

## Como abrir no Overleaf

1. Acesse <https://www.overleaf.com/latex/templates/sbc-conferences-template/blbxwjwzdngr>
   e clique em **Open as Template** (ou crie um projeto em branco).
2. Substitua o conteúdo do projeto pelos arquivos desta pasta
   (`main.tex`, `referencias.bib`, `sbc-template.sty`, `sbc.bst`).
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

## Escopo desta entrega

- `main.tex` contém a Introdução e a seção de hipóteses (RQ 01 a RQ 07).
- As seções de Metodologia, Resultados, Discussão, Ameaças à Validade e
  Replicação Cruzada estão comentadas no fim de `main.tex`, como esqueleto para
  as próximas sprints.
- As hipóteses são informais e foram redigidas **antes** da análise dos dados,
  conforme exigido pela disciplina.

## Observações

- Os arquivos de compilação (`*.aux`, `*.bbl`, `*.blg`, `*.log`, `*.out`,
  `*.pdf`) são ignorados pelo Git; não versione o PDF.
- Ao usar `\cite`, garanta que a chave existe em `referencias.bib`.
