import argparse
import os

import pandas as pd

ARQ_AMOSTRA = os.path.join("data", "amostra.csv")
ARQ_DATASET = os.path.join("data", "dataset.csv")


def sortear(amostra, n, semente):
    ordenada = amostra.sort_values("full_name").reset_index(drop=True)
    return ordenada.sample(n=min(n, len(ordenada)), random_state=semente).sort_values("full_name")


def ate_max_runs(amostra, dataset, max_runs):
    """So os repositorios com ate `max_runs` workflow runs na janela."""
    leves = set(dataset.loc[dataset["runs_total"] <= max_runs, "full_name"])
    return amostra[amostra["full_name"].isin(leves)]


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="pipeline.subamostra",
        description="Sorteia uma subamostra da amostra final (para a replicacao cruzada).",
    )
    parser.add_argument("--n", type=int, default=30, help="quantidade de repositorios (padrao: 30)")
    parser.add_argument("--semente", type=int, default=42, help="semente do sorteio (padrao: 42)")
    parser.add_argument("--amostra", default=ARQ_AMOSTRA, help=f"amostra de origem (padrao: {ARQ_AMOSTRA})")
    parser.add_argument("--saida", required=True, help="CSV de saida com os repositorios sorteados")
    parser.add_argument("--max-runs", type=int, default=None,
                        help="sorteia so entre repositorios com ate N workflow runs na janela "
                             f"(lidos de {ARQ_DATASET}); deixa a coleta mais curta")
    parser.add_argument("--dataset", default=ARQ_DATASET, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    amostra = pd.read_csv(args.amostra)
    if args.max_runs is not None:
        amostra = ate_max_runs(amostra, pd.read_csv(args.dataset), args.max_runs)
    subamostra = sortear(amostra, args.n, args.semente)
    pasta = os.path.dirname(args.saida)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    subamostra.to_csv(args.saida, index=False)
    print(f"{len(subamostra)} repositorios sorteados (semente {args.semente}) em {args.saida}")


if __name__ == "__main__":
    main()
