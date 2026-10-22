"""Compara o CSV replicado com o CSV original do outro grupo.

Para cada metrica: diferenca relativa por repositorio e % de repositorios com
a mesma classe DORA. A classe geral sai da regra da disciplina (mediana das
notas de frequencia, lead time (a), CFR (a) e recuperacao, arredondada para
baixo), calculada igual nos dois CSVs.

    python -m replicacao_cruzada.comparar --original <dataset-500.csv> --replicado <dataset-30.csv> --saida replicacao_cruzada/resultados
"""
import argparse
import os

import pandas as pd

from analises.comum import garantir_pasta, tabela_markdown
from metricas.classificacao import ROTULOS, nota_geral

METRICAS = ("deployment_frequency", "lead_time_a", "lead_time_b", "cfr_a", "cfr_b", "tempo_recuperacao")
NOTAS = {"Elite": 4, "High": 3, "Medium": 2, "Low": 1}
# classe geral (C1): frequencia, lead time (a), CFR (a) e recuperacao
CLASSES_GERAL = ("classe_deployment_frequency", "classe_lead_time_a", "classe_cfr_a",
                 "classe_tempo_recuperacao")


def classe_geral(linha):
    notas = [NOTAS.get(linha[coluna]) for coluna in CLASSES_GERAL if coluna in linha]
    return ROTULOS.get(nota_geral(notas))


def diferenca_relativa(original, replicado):
    """(replicado - original) / |original|; 0 quando os dois sao 0; None sem um dos dois."""
    if pd.isna(original) or pd.isna(replicado):
        return None
    if original == 0:
        return 0.0 if replicado == 0 else None
    return (replicado - original) / abs(original)


def juntar(original, replicado):
    """Linhas dos repositorios replicados, com os valores originais ao lado."""
    original = original.assign(classe_geral=original.apply(classe_geral, axis=1))
    replicado = replicado.assign(classe_geral=replicado.apply(classe_geral, axis=1))
    colunas = ["full_name", *METRICAS, *(f"classe_{m}" for m in METRICAS), "classe_geral"]
    colunas = [c for c in colunas if c in original and c in replicado]
    return replicado[colunas].merge(original[colunas], on="full_name", how="left",
                                    suffixes=("_replicado", "_original"))


def por_repositorio(juntos):
    tabela = juntos[["full_name"]].copy()
    for metrica in METRICAS:
        if f"{metrica}_original" not in juntos:
            continue
        tabela[f"{metrica}_original"] = juntos[f"{metrica}_original"]
        tabela[f"{metrica}_replicado"] = juntos[f"{metrica}_replicado"]
        tabela[f"{metrica}_dif_rel"] = [
            diferenca_relativa(o, r)
            for o, r in zip(juntos[f"{metrica}_original"], juntos[f"{metrica}_replicado"])
        ]
    tabela["classe_geral_original"] = juntos["classe_geral_original"]
    tabela["classe_geral_replicado"] = juntos["classe_geral_replicado"]
    return tabela


def _mesma_classe(juntos, coluna):
    pares = juntos[[f"{coluna}_original", f"{coluna}_replicado"]].dropna()
    if pares.empty:
        return None, 0
    return float((pares.iloc[:, 0] == pares.iloc[:, 1]).mean()), int(len(pares))


def resumo(juntos, tabela):
    linhas = []
    for metrica in METRICAS:
        if f"{metrica}_dif_rel" not in tabela:
            continue
        dif = pd.to_numeric(tabela[f"{metrica}_dif_rel"], errors="coerce").dropna().abs()
        mesma, n_classes = _mesma_classe(juntos, f"classe_{metrica}")
        linhas.append({
            "metrica": metrica,
            "pares": int(len(dif)),
            "dif_rel_mediana": float(dif.median()) if len(dif) else None,
            "dif_rel_media": float(dif.mean()) if len(dif) else None,
            "dif_rel_max": float(dif.max()) if len(dif) else None,
            "ate_1pct": float((dif <= 0.01).mean()) if len(dif) else None,
            "mesma_classe": mesma,
            "pares_classe": n_classes,
        })
    mesma, n_classes = _mesma_classe(juntos, "classe_geral")
    linhas.append({"metrica": "classe_geral", "pares": n_classes, "dif_rel_mediana": None,
                   "dif_rel_media": None, "dif_rel_max": None, "ate_1pct": None,
                   "mesma_classe": mesma, "pares_classe": n_classes})
    return pd.DataFrame(linhas)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="replicacao_cruzada.comparar", description=__doc__.splitlines()[0])
    parser.add_argument("--original", required=True, help="CSV original do outro grupo")
    parser.add_argument("--replicado", required=True, help="CSV gerado na replicacao")
    parser.add_argument("--saida", required=True)
    args = parser.parse_args(argv)
    pasta = garantir_pasta(args.saida)

    juntos = juntar(pd.read_csv(args.original), pd.read_csv(args.replicado))
    tabela = por_repositorio(juntos)
    sintese = resumo(juntos, tabela)
    tabela.to_csv(os.path.join(pasta, "comparacao_por_repositorio.csv"), index=False)
    sintese.to_csv(os.path.join(pasta, "comparacao_resumo.csv"), index=False)
    texto = "# Replicacao cruzada - comparacao com o CSV original\n\n" + tabela_markdown(sintese)
    with open(os.path.join(pasta, "comparacao.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto, flush=True)


if __name__ == "__main__":
    main()
