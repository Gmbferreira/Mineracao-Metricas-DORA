"""Sorteia a subamostra de 30 repositorios do dataset do outro grupo.

Gera o CSV da subamostra e o arquivo de candidatos no formato que o
`pipeline.integrado --candidatos` do outro grupo le.

    python -m replicacao_cruzada.sorteio --dataset <dataset-500.csv> --saida replicacao_cruzada/dados
"""
import argparse
import json
import os

import pandas as pd

N_PADRAO = 30
SEMENTE = 42


def sortear(dataset, n=N_PADRAO, semente=SEMENTE):
    """Sorteio reproduzivel: ordena por nome antes, para nao depender da ordem do CSV."""
    ordenado = dataset.sort_values("full_name").reset_index(drop=True)
    return ordenado.sample(n=min(n, len(ordenado)), random_state=semente).sort_values("full_name")


def candidatos(amostra):
    """Lista no formato de `raw/candidatos.json` do outro grupo."""
    return {
        "total_candidatos": int(len(amostra)),
        "candidatos": [
            {
                "id": int(linha.id),
                "full_name": linha.full_name,
                "html_url": f"https://github.com/{linha.full_name}",
                "estrelas": int(linha.estrelas),
                "linguagem": None if pd.isna(linha.linguagem) else linha.linguagem,
            }
            for linha in amostra.itertuples()
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="replicacao_cruzada.sorteio", description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", required=True, help="CSV original do outro grupo")
    parser.add_argument("--saida", required=True, help="pasta de saida")
    parser.add_argument("--n", type=int, default=N_PADRAO)
    parser.add_argument("--semente", type=int, default=SEMENTE)
    args = parser.parse_args(argv)

    amostra = sortear(pd.read_csv(args.dataset), args.n, args.semente)
    os.makedirs(args.saida, exist_ok=True)
    amostra.to_csv(os.path.join(args.saida, f"amostra_{len(amostra)}.csv"), index=False)
    with open(os.path.join(args.saida, f"candidatos_{len(amostra)}.json"), "w", encoding="utf-8") as f:
        json.dump(candidatos(amostra), f, ensure_ascii=False, indent=2)
    print(f"{len(amostra)} repositorios sorteados (semente {args.semente}) em {args.saida}")


if __name__ == "__main__":
    main()
