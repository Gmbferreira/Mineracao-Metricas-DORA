"""RQ 07: quanto a classificacao DORA depende da definicao operacional.

Compara tres combinacoes de definicoes, a partir de data/variantes.csv:
C1 (release, lead time a, CFR a), C2 (release + pre-release, lead time b,
CFR b) e C3 (tag, lead time b, CFR a).

    python -m analises.rq07_sensibilidade
"""
import argparse
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import cohen_kappa_score  # noqa: E402

from analises.comum import (  # noqa: E402
    DIR_DADOS, DIR_RESULTADOS, ORDEM_CLASSES, garantir_pasta, resumo, tabela_markdown,
)
from metricas import classificacao  # noqa: E402

COMBINACOES = ("c1", "c2", "c3")
PARES = (("c1", "c2"), ("c1", "c3"), ("c2", "c3"))
METRICAS = ("geral", "frequencia", "lead_time", "cfr", "recuperacao")
CLASSES = ("Elite", "High", "Medium", "Low")
UNIDADES = ("release", "release_pre", "tag")
# C1 com um fator trocado de cada vez: (nome, unidade, lead time, CFR)
FATORES = (
    ("unidade: release + pre-release", "release_pre", "lead_time_a", "cfr_a"),
    ("unidade: tag", "tag", "lead_time_a", "cfr_a"),
    ("lead time (b)", "release", "lead_time_b", "cfr_a"),
    ("CFR (b)", "release", "lead_time_a", "cfr_b"),
)


def distribuicao(variantes):
    linhas = []
    for combinacao in COMBINACOES:
        classes = variantes[f"classe_geral_{combinacao}"].dropna()
        linha = {"combinacao": combinacao.upper(), "n": int(len(classes))}
        for classe in CLASSES:
            linha[classe] = float((classes == classe).mean()) if len(classes) else None
        linhas.append(linha)
    return pd.DataFrame(linhas)


def _concordancia(classes_a, classes_b):
    pares = pd.DataFrame({"a": classes_a, "b": classes_b}).dropna()
    codigo_a = pares["a"].map(ORDEM_CLASSES)
    codigo_b = pares["b"].map(ORDEM_CLASSES)
    kappa = None
    if len(pares):
        valor = cohen_kappa_score(codigo_a, codigo_b, weights="linear", labels=[1, 2, 3, 4])
        kappa = None if math.isnan(valor) else float(valor)
    return {
        "n": int(len(pares)),
        "mudou_de_classe": float((codigo_a != codigo_b).mean()) if len(pares) else None,
        "subiu": float((codigo_b > codigo_a).mean()) if len(pares) else None,
        "desceu": float((codigo_b < codigo_a).mean()) if len(pares) else None,
        "kappa_linear": kappa,
    }


def comparar_par(variantes, a, b, metrica="geral"):
    """% de repositorios que mudam de classe e kappa ponderado entre duas combinacoes."""
    return {"par": f"{a.upper()} x {b.upper()}", "metrica": metrica,
            **_concordancia(variantes[f"classe_{metrica}_{a}"], variantes[f"classe_{metrica}_{b}"])}


def _valor(linha, coluna):
    valor = linha.get(coluna)
    return None if valor is None or pd.isna(valor) else float(valor)


def classe_geral(linha, unidade, lead_time, cfr):
    """Classe geral de um repositorio numa combinacao qualquer de definicoes."""
    if _valor(linha, f"unidades_{unidade}") is None:
        return None
    taxa = _valor(linha, "cfr_a") if cfr == "cfr_a" else _valor(linha, f"cfr_b_{unidade}")
    classes = classificacao.classificar_repositorio(
        _valor(linha, f"deployment_frequency_{unidade}"), _valor(linha, f"{lead_time}_{unidade}"),
        taxa, _valor(linha, "recuperacao_horas"),
    )
    return classes["classe_geral"] or None


def fatores_isolados(variantes):
    """Troca um fator de C1 por vez e mede quantos repositorios mudam de classe geral."""
    linhas = []
    for nome, unidade, lead_time, cfr in FATORES:
        classes = variantes.apply(lambda linha: classe_geral(linha, unidade, lead_time, cfr), axis=1)
        linhas.append({"fator": nome, **_concordancia(variantes["classe_geral_c1"], classes)})
    return pd.DataFrame(linhas)


def transicoes(variantes, a, b):
    """Matriz de transicao da classe geral: linhas em `a`, colunas em `b`."""
    pares = variantes[[f"classe_geral_{a}", f"classe_geral_{b}"]].dropna()
    matriz = pd.crosstab(pares.iloc[:, 0], pares.iloc[:, 1])
    return matriz.reindex(index=list(CLASSES), columns=list(CLASSES), fill_value=0)


def unidades(variantes):
    """Mediana e IQR da frequencia e do lead time em cada unidade de deploy."""
    linhas = []
    for unidade in UNIDADES:
        for metrica in ("unidades", "deployment_frequency", "lead_time_a", "lead_time_b"):
            coluna = f"{metrica}_{unidade}"
            if coluna in variantes:
                linhas.append({"unidade": unidade, "metrica": metrica, **resumo(variantes[coluna])})
    return pd.DataFrame(linhas)


def grafico(variantes, caminho):
    # tamanho pensado para a largura do texto no artigo (cerca de 15 cm)
    figura, eixos = plt.subplots(1, len(PARES), figsize=(7.5, 2.7))
    for eixo, (a, b) in zip(eixos, PARES):
        matriz = transicoes(variantes, a, b)
        eixo.imshow(matriz.values, cmap="Blues")
        for i in range(len(CLASSES)):
            for j in range(len(CLASSES)):
                valor = int(matriz.values[i, j])
                cor = "white" if valor > matriz.values.max() / 2 else "black"
                eixo.text(j, i, str(valor), ha="center", va="center", color=cor, fontsize=8)
        eixo.set_xticks(range(len(CLASSES)), CLASSES, fontsize=7)
        eixo.set_yticks(range(len(CLASSES)), CLASSES, fontsize=7)
        eixo.set_xlabel(f"classe em {b.upper()}", fontsize=8)
        eixo.set_ylabel(f"classe em {a.upper()}", fontsize=8)
        eixo.set_title(f"{a.upper()} x {b.upper()}", fontsize=9)
    figura.tight_layout()
    figura.savefig(caminho, dpi=200)
    plt.close(figura)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="analises.rq07_sensibilidade",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--variantes", default=os.path.join(DIR_DADOS, "variantes.csv"))
    parser.add_argument("--saida", default=DIR_RESULTADOS)
    args = parser.parse_args(argv)
    pasta = garantir_pasta(args.saida)

    variantes = pd.read_csv(args.variantes)
    dist = distribuicao(variantes)
    pares = pd.DataFrame([comparar_par(variantes, a, b, metrica)
                          for metrica in METRICAS for a, b in PARES])
    tabela_unidades = unidades(variantes)
    fatores = fatores_isolados(variantes)
    dist.to_csv(os.path.join(pasta, "rq07_distribuicao.csv"), index=False)
    pares.to_csv(os.path.join(pasta, "rq07_pares.csv"), index=False)
    tabela_unidades.to_csv(os.path.join(pasta, "rq07_unidades.csv"), index=False)
    fatores.to_csv(os.path.join(pasta, "rq07_fatores.csv"), index=False)
    for a, b in PARES:
        transicoes(variantes, a, b).to_csv(os.path.join(pasta, f"rq07_transicoes_{a}_{b}.csv"))
    grafico(variantes, os.path.join(pasta, "rq07_transicoes.png"))

    texto = ("# RQ 07 - Sensibilidade\n\n## Distribuicao da classe geral\n\n" + tabela_markdown(dist)
             + "\n## Pares de combinacoes\n\n" + tabela_markdown(pares)
             + "\n## Um fator de cada vez (contra C1)\n\n" + tabela_markdown(fatores)
             + "\n## Unidades de deploy\n\n" + tabela_markdown(tabela_unidades))
    with open(os.path.join(pasta, "rq07.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto, flush=True)


if __name__ == "__main__":
    main()
