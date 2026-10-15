import argparse
import os

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from metricas import corretiva
from pipeline import coleta, config

DIR_VALIDACAO = "validacao"
DIR_COLETA = os.path.join("data", "coleta")
ARQ_CONSENSO = os.path.join(DIR_VALIDACAO, "consenso_releases.csv")
ARQ_RESULTADO = os.path.join(DIR_VALIDACAO, "avaliacao_heuristica.csv")
F1_MINIMO = 0.70


def mensagens_por_tag(dados):
    return {
        item["tag_name"]: [commit["mensagem"] for commit in item.get("commits", [])]
        for item in dados.get("avaliadas", [])
    }


def avaliar(consenso, mensagens, heuristicas=None):
    """Precisao, recall e F1 de cada versao da heuristica contra o consenso.

    `consenso` tem `full_name`, `tag_name` e `corretiva` (sim/nao); `mensagens`
    mapeia (full_name, tag_name) para as mensagens dos commits da release.
    """
    heuristicas = heuristicas or corretiva.HEURISTICAS
    esperado = (consenso["corretiva"].str.strip().str.lower() == "sim").tolist()
    linhas = []
    for nome, heuristica in heuristicas.items():
        previsto = [
            bool(heuristica(release.tag_name, mensagens.get((release.full_name, release.tag_name), [])))
            for release in consenso.itertuples()
        ]
        precisao, recall, f1, _ = precision_recall_fscore_support(
            esperado, previsto, average="binary", pos_label=True, zero_division=0
        )
        linhas.append(
            {
                "versao": nome,
                "precisao": round(float(precisao), 4),
                "recall": round(float(recall), 4),
                "f1": round(float(f1), 4),
                "verdadeiros_positivos": sum(e and p for e, p in zip(esperado, previsto)),
                "falsos_positivos": sum(p and not e for e, p in zip(esperado, previsto)),
                "falsos_negativos": sum(e and not p for e, p in zip(esperado, previsto)),
                "releases": len(esperado),
                "corretivas_no_consenso": sum(esperado),
            }
        )
    return pd.DataFrame(linhas)


def carregar_mensagens(consenso, cfg, dir_coleta=DIR_COLETA):
    mensagens = {}
    faltando = []
    for nome in sorted(consenso["full_name"].unique()):
        dados = coleta.carregar(dir_coleta, nome, cfg)
        if dados is None:
            faltando.append(nome)
            continue
        for tag, lista in mensagens_por_tag(dados).items():
            mensagens[(nome, tag)] = lista
    return mensagens, faltando


def main():
    parser = argparse.ArgumentParser(
        prog="validacao.avaliacao",
        description="Avalia as versoes da heuristica de release corretiva contra o consenso.",
    )
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    if not os.path.exists(ARQ_CONSENSO):
        raise SystemExit(
            f"{ARQ_CONSENSO} ainda nao existe. Ele sai da etapa de consenso, "
            "depois que os dois avaliadores terminam a rotulagem."
        )
    cfg = config.carregar(args.config)
    consenso = pd.read_csv(ARQ_CONSENSO)
    mensagens, faltando = carregar_mensagens(consenso, cfg)
    if faltando:
        raise SystemExit(
            "Faltam dados coletados de: " + ", ".join(faltando)
            + ". Rode antes: python -m pipeline --etapas coleta"
        )
    resultado = avaliar(consenso, mensagens)
    resultado.to_csv(ARQ_RESULTADO, index=False)
    print(resultado.to_string(index=False), flush=True)
    melhor = resultado.sort_values("f1", ascending=False).iloc[0]
    situacao = "atinge" if melhor["f1"] >= F1_MINIMO else "fica abaixo de"
    print(
        f"\nmelhor versao: {melhor['versao']} (F1 = {melhor['f1']:.2f}, "
        f"{situacao} {F1_MINIMO:.2f}); resultado em {ARQ_RESULTADO}",
        flush=True,
    )


if __name__ == "__main__":
    main()
