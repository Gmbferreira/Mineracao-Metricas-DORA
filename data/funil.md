# Funil de selecao

Gerado em: 2026-10-08T17:28:32

| Etapa | Entrada | Saida | Descartados | Motivo |
|---|---:|---:|---:|---|
| Candidatos identificados (stars >1000, pre-filtros) |  | 37372 |  | busca fatiada por faixas de estrelas |
| Candidatos escaneados | 37372 | 207 | 37165 | varredura parcial: parada ao atingir o alvo de 100 (ordem: estrelas decrescentes) |
| E1 - utiliza GitHub Actions | 207 | 196 | 11 | total_count de workflows = 0 |
| E2 - >=50 runs de push no default branch na janela | 196 | 137 | 59 | menos de 50 runs de push na janela |
| E3 - >=5 releases publicadas na janela | 137 | 100 | 37 | menos de 5 releases publicadas na janela |
| Amostra final com metadados completos | 100 | 100 | 0 | contribuidores/idade coletados para todos |

Notas:
- Janela de observacao: 2025-10-02 a 2026-10-02 (12 meses).
- Criterio de inclusao: >= 5 releases publicadas (draft=false e prerelease=false) e >= 50 workflow runs de push no default branch dentro da janela.
- Pre-filtros da busca: stars >= 1000, fork:false, archived:false, pushed:>= 2025-10-02.
- Alvo da sprint: 100 repositorios qualificados; ordem de varredura: estrelas_desc (estrelas decrescentes).
- A varredura de candidatos e parcial por definicao: para ao atingir o alvo e e retomavel (checkpoints em data/checkpoints/).
- Candidatos por faixa de estrelas: 50000..+ = 451; 30000..49999 = 623; 20000..29999 = 847; 15000..19999 = 796; 12500..14999 = 676; 10000..12499 = 939; 8750..9999 = 711; 7500..8749 = 880; 6875..7499 = 587; 6250..6874 = 663; 5625..6249 = 851; 5313..5624 = 454; 5000..5312 = 560; 4625..4999 = 701; 4250..4624 = 848; 3875..4249 = 977; 3688..3874 = 569; 3500..3687 = 621; 3313..3499 = 673; 3125..3312 = 719; 2938..3124 = 855; 2750..2937 = 905; 2657..2749 = 497; 2563..2656 = 558; 2469..2562 = 509; 2375..2468 = 638; 2282..2374 = 633; 2188..2281 = 743; 2094..2187 = 739; 2000..2093 = 838; 1938..1999 = 602; 1875..1937 = 687; 1813..1874 = 637; 1750..1812 = 749; 1688..1749 = 770; 1625..1687 = 782; 1563..1624 = 869; 1500..1562 = 913; 1438..1499 = 937; 1407..1437 = 521; 1375..1406 = 551; 1344..1374 = 551; 1313..1343 = 619; 1282..1312 = 516; 1250..1281 = 627; 1219..1249 = 642; 1188..1218 = 671; 1157..1187 = 713; 1125..1156 = 739; 1094..1124 = 746; 1063..1093 = 776; 1032..1062 = 858; 1000..1031 = 835.
