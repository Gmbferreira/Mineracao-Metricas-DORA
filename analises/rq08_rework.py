"""RQ 08 (bonus): rework rate de cada repositorio e comparacao com o CFR (b).

Rework rate = releases corretivas / releases da janela, com a mesma heuristica
de release corretiva usada no CFR (b). Roda a partir de data/dataset.csv:

    python -m analises.rq08_rework
"""
import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from matplotlib.ticker import FuncFormatter  # noqa: E402

from analises.comum import (  # noqa: E402
    CORES, DIR_DADOS, DIR_RESULTADOS, TINTA, TINTA_SECUNDARIA, eixo_limpo, garantir_pasta, moda,
    resumo, tabela_markdown, virgula,
)


def rework_rate(dataset):
    tabela = dataset[["full_name", "releases_janela", "releases_corretivas", "cfr_b"]].copy()
    tabela["rework_rate"] = tabela["releases_corretivas"] / tabela["releases_janela"]
    return tabela


def comparar(tabela):
    """Rework rate x CFR (b) nos repositorios que tem os dois valores."""
    pares = tabela.dropna(subset=["rework_rate", "cfr_b"])
    rho, p_spearman = stats.spearmanr(pares["rework_rate"], pares["cfr_b"])
    diferenca = pares["rework_rate"] - pares["cfr_b"]
    wilcoxon = stats.wilcoxon(pares["rework_rate"], pares["cfr_b"])
    return {
        "n": int(len(pares)),
        "spearman_rho": float(rho),
        "spearman_p": float(p_spearman),
        "wilcoxon_p": float(wilcoxon.pvalue),
        "mediana_da_diferenca": float(diferenca.median()),
        "proporcao_rework_maior": float((diferenca > 0).mean()),
        "proporcao_rework_igual": float((diferenca == 0).mean()),
    }


def grafico(tabela, caminho):
    pares = tabela.dropna(subset=["rework_rate", "cfr_b"])
    figura, eixo = plt.subplots(figsize=(4.8, 4.2))
    eixo.scatter(pares["cfr_b"], pares["rework_rate"], s=14, alpha=0.6, color="#2f6db5")
    eixo.plot([0, 1], [0, 1], linestyle="--", color="#888888", linewidth=1)
    eixo.set_xlabel("CFR (b) - proxy de entrega")
    eixo.set_ylabel("Rework rate")
    eixo.set_xlim(-0.02, 1.02)
    eixo.set_ylim(-0.02, 1.02)
    eixo.set_title("RQ 08: rework rate x CFR (b)")
    figura.tight_layout()
    figura.savefig(caminho, dpi=200)
    plt.close(figura)


def grafico_distribuicao(tabela, caminho):
    """Histograma da rework rate e do CFR (b), com media, mediana e moda."""
    metricas = (("rework_rate", "(a) Rework rate"), ("cfr_b", "(b) CFR (b)"))
    figura, eixos = plt.subplots(1, 2, figsize=(7.5, 2.6), sharey=True)
    faixas = [i / 20 for i in range(21)]
    for eixo, (coluna, titulo) in zip(eixos, metricas):
        valores = tabela[coluna].dropna()
        eixo.hist(valores, bins=faixas, color=CORES[0], edgecolor="white", linewidth=0.8)
        media, mediana, mais_comum = valores.mean(), valores.median(), moda(valores)
        eixo.axvline(mediana, color=TINTA, linewidth=1.4,
                     label=f"mediana = {virgula(round(mediana, 2))}")
        eixo.axvline(media, color=CORES[1], linewidth=1.4, linestyle="--",
                     label=f"média = {virgula(round(media, 2))}")
        if mais_comum is not None:
            vezes = int((valores == mais_comum).sum())
            barra = eixo.patches[min(int(mais_comum * 20), 19)]
            eixo.plot(barra.get_x() + barra.get_width() / 2, barra.get_height() + 2.5,
                      linestyle="none", marker="v", markersize=5, color=TINTA,
                      label=f"moda = {virgula(mais_comum)} ({vezes} repositórios)")
        eixo.set_xlim(0, 1)
        eixo.xaxis.set_major_formatter(FuncFormatter(virgula))
        eixo.set_xlabel("proporção por repositório", fontsize=7.5, color=TINTA)
        eixo.set_title(f"{titulo} ({len(valores)} repositórios)", fontsize=8, color=TINTA)
        eixo.legend(frameon=False, fontsize=6.5, loc="upper right", labelcolor=TINTA)
        eixo_limpo(eixo)
    eixos[0].set_ylabel("repositórios", fontsize=7.5, color=TINTA)
    figura.tight_layout()
    figura.savefig(caminho, dpi=200)
    plt.close(figura)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="analises.rq08_rework", description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", default=os.path.join(DIR_DADOS, "dataset.csv"))
    parser.add_argument("--saida", default=DIR_RESULTADOS)
    args = parser.parse_args(argv)
    pasta = garantir_pasta(args.saida)

    tabela = rework_rate(pd.read_csv(args.dataset))
    tabela.to_csv(os.path.join(pasta, "rq08_rework_por_repositorio.csv"), index=False)
    pares = tabela.dropna(subset=["rework_rate", "cfr_b"])
    resumos = pd.DataFrame([
        {"metrica": "rework_rate", **resumo(tabela["rework_rate"])},
        {"metrica": "cfr_b", **resumo(tabela["cfr_b"])},
        {"metrica": "rework_rate - cfr_b", **resumo(pares["rework_rate"] - pares["cfr_b"])},
    ])
    resumos.to_csv(os.path.join(pasta, "rq08_resumo.csv"), index=False)
    comparacao = comparar(tabela)
    pd.DataFrame([comparacao]).to_csv(os.path.join(pasta, "rq08_comparacao.csv"), index=False)
    grafico(tabela, os.path.join(pasta, "rq08_rework_x_cfr_b.png"))
    grafico_distribuicao(tabela, os.path.join(pasta, "rq08_distribuicao.png"))

    texto = ("# RQ 08 - Rework rate\n\n" + tabela_markdown(resumos)
             + "\n" + tabela_markdown(pd.DataFrame([comparacao])))
    with open(os.path.join(pasta, "rq08.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto, flush=True)


if __name__ == "__main__":
    main()
