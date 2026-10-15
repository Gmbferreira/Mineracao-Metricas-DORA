# Funil de selecao

Gerado em: 2026-10-15T01:05:08

| Etapa | Entrada | Saida | Descartados | Motivo |
|---|---:|---:|---:|---|
| Candidatos identificados (stars >1000, pre-filtros) |  | 37388 |  | busca fatiada por faixas de estrelas |
| Candidatos escaneados | 37388 | 646 | 36742 | varredura parcial: parada ao atingir o alvo de 300 (ordem: estrelas decrescentes) |
| E1 - utiliza GitHub Actions | 646 | 611 | 35 | total_count de workflows = 0 |
| E2 - >=50 runs de push no default branch na janela | 611 | 425 | 186 | menos de 50 runs de push na janela |
| E3 - >=5 releases publicadas na janela | 425 | 300 | 125 | menos de 5 releases publicadas na janela |
| Amostra final com metadados completos | 300 | 300 | 0 | contribuidores/idade coletados para todos |

Notas:
- Janela de observacao: 2025-10-02 a 2026-10-02 (12 meses).
- Criterio de inclusao: >= 5 releases publicadas (draft=false e prerelease=false) e >= 50 workflow runs de push no default branch dentro da janela.
- Pre-filtros da busca: stars >= 1000, fork:false, archived:false, pushed:>= 2025-10-02.
- Alvo da sprint: 300 repositorios qualificados; ordem de varredura: estrelas_desc (estrelas decrescentes).
- A varredura de candidatos e parcial por definicao: para ao atingir o alvo e e retomavel (checkpoints em data/checkpoints/).
- Candidatos por faixa de estrelas: 50000..+ = 451; 30000..49999 = 623; 20000..29999 = 847; 15000..19999 = 797; 12500..14999 = 675; 10000..12499 = 939; 8750..9999 = 711; 7500..8749 = 882; 6875..7499 = 585; 6250..6874 = 664; 5625..6249 = 852; 5313..5624 = 456; 5000..5312 = 558; 4625..4999 = 699; 4250..4624 = 851; 3875..4249 = 978; 3688..3874 = 567; 3500..3687 = 620; 3313..3499 = 673; 3125..3312 = 721; 2938..3124 = 854; 2750..2937 = 911; 2657..2749 = 495; 2563..2656 = 559; 2469..2562 = 509; 2375..2468 = 640; 2282..2374 = 629; 2188..2281 = 742; 2094..2187 = 742; 2000..2093 = 839; 1938..1999 = 600; 1875..1937 = 687; 1813..1874 = 636; 1750..1812 = 752; 1688..1749 = 769; 1625..1687 = 780; 1563..1624 = 871; 1500..1562 = 910; 1438..1499 = 936; 1407..1437 = 524; 1375..1406 = 557; 1344..1374 = 542; 1313..1343 = 622; 1282..1312 = 516; 1250..1281 = 631; 1219..1249 = 636; 1188..1218 = 674; 1157..1187 = 714; 1125..1156 = 740; 1094..1124 = 743; 1063..1093 = 781; 1032..1062 = 861; 1000..1031 = 837.
