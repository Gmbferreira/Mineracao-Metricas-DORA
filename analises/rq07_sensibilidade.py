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

from matplotlib.ticker import FuncFormatter  # noqa: E402

from analises.comum import (  # noqa: E402
    CORES, DIR_DADOS, DIR_RESULTADOS, ORDEM_CLASSES, TINTA, TINTA_SECUNDARIA, eixo_limpo,
    garantir_pasta, moda, resumo, tabela_markdown, virgula,
)
from metricas import classificacao  # noqa: E402

COMBINACOES = ("c1", "c2", "c3")
PARES = (("c1", "c2"), ("c1", "c3"), ("c2", "c3"))
METRICAS = ("geral", "frequencia", "lead_time", "cfr", "recuperacao")
# as metricas na ordem em que o artigo as apresenta, com a classe geral no fim
METRICAS_ORDEM = ("frequencia", "lead_time", "cfr", "recuperacao", "geral")
CLASSES = ("Elite", "High", "Medium", "Low")
UNIDADES = ("release", "release_pre", "tag")
# C1 com um fator trocado de cada vez: (nome, unidade, lead time, CFR)
FATORES = (
    ("unidade: release + pre-release", "release_pre", "lead_time_a", "cfr_a"),
    ("unidade: tag", "tag", "lead_time_a", "cfr_a"),
    ("lead time (b)", "release", "lead_time_b", "cfr_a"),
    ("CFR (b)", "release", "lead_time_a", "cfr_b"),
)
# rotulos dos graficos, com acentuacao
ROTULOS_METRICA = {
    "frequencia": "frequência",
    "lead_time": "lead time",
    "cfr": "CFR",
    "recuperacao": "recuperação",
    "geral": "classe geral",
}
ROTULOS_FATOR = {
    "unidade: release + pre-release": "unidade: release + pré-release",
    "unidade: tag": "unidade: tag",
    "lead time (b)": "lead time (b)",
    "CFR (b)": "CFR (b)",
}
CINZA = "#c9c9c9"


def distribuicao(variantes):
    """Proporcao de cada classe geral e a classe mais comum (moda) em cada combinacao."""
    linhas = []
    for combinacao in COMBINACOES:
        classes = variantes[f"classe_geral_{combinacao}"].dropna()
        linha = {"combinacao": combinacao.upper(), "n": int(len(classes))}
        for classe in CLASSES:
            linha[classe] = float((classes == classe).mean()) if len(classes) else None
        linha["moda"] = moda(classes)
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


def classes_combinacao(linha, unidade, lead_time, cfr):
    """Classes de cada metrica de um repositorio numa combinacao qualquer.

    Devolve as cinco classes (frequencia, lead time, CFR, recuperacao e a
    geral); None quando a metrica nao tem dado na combinacao.
    """
    if _valor(linha, f"unidades_{unidade}") is None:
        return {metrica: None for metrica in METRICAS_ORDEM}
    taxa = _valor(linha, "cfr_a") if cfr == "cfr_a" else _valor(linha, f"cfr_b_{unidade}")
    classes = classificacao.classificar_repositorio(
        _valor(linha, f"deployment_frequency_{unidade}"), _valor(linha, f"{lead_time}_{unidade}"),
        taxa, _valor(linha, "recuperacao_horas"),
    )
    return {chave.replace("classe_", ""): (valor or None)
            for chave, valor in classes.items() if chave.startswith("classe_")}


def classe_geral(linha, unidade, lead_time, cfr):
    """Classe geral de um repositorio numa combinacao qualquer de definicoes."""
    return classes_combinacao(linha, unidade, lead_time, cfr)["geral"]


def distribuicao_metricas(variantes):
    """Proporcao de cada classe, por metrica, em cada combinacao."""
    linhas = []
    for metrica in METRICAS_ORDEM:
        for combinacao in COMBINACOES:
            coluna = f"classe_{metrica}_{combinacao}"
            if coluna not in variantes:
                continue
            classes = variantes[coluna].dropna()
            linha = {"metrica": metrica, "combinacao": combinacao.upper(),
                     "n": int(len(classes))}
            for classe in CLASSES:
                linha[classe] = float((classes == classe).mean()) if len(classes) else None
            linha["moda"] = moda(classes)
            linhas.append(linha)
    return pd.DataFrame(linhas)


def fatores_isolados(variantes):
    """Troca um fator de C1 por vez e mede quantos repositorios mudam de classe geral."""
    linhas = []
    for nome, unidade, lead_time, cfr in FATORES:
        classes = variantes.apply(lambda linha: classe_geral(linha, unidade, lead_time, cfr), axis=1)
        linhas.append({"fator": nome, **_concordancia(variantes["classe_geral_c1"], classes)})
    return pd.DataFrame(linhas)


def fatores_metricas(variantes):
    """Troca um fator de C1 por vez e mede a mudanca de classe de cada metrica.

    A troca da unidade de deploy mexe na frequencia e no lead time (a), que e
    ancorado na mesma unidade; a variante do lead time mexe so no lead time; e
    a variante do CFR mexe so no CFR.
    """
    linhas = []
    for nome, unidade, lead_time, cfr in FATORES:
        classes = [classes_combinacao(linha, unidade, lead_time, cfr)
                   for _, linha in variantes.iterrows()]
        for metrica in METRICAS_ORDEM:
            coluna = f"classe_{metrica}_c1"
            if coluna not in variantes:
                continue
            novo = pd.Series([classe.get(metrica) for classe in classes],
                             index=variantes.index, dtype=object)
            linhas.append({"fator": nome, "metrica": metrica,
                           **_concordancia(variantes[coluna], novo)})
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


def grafico_classes_e_unidades(variantes, caminho):
    """(a) barras agrupadas da classe geral por combinacao; (b) boxplot da
    frequencia de deploy em cada unidade, com a media marcada."""
    figura, (barras, caixas) = plt.subplots(1, 2, figsize=(7.5, 2.9),
                                            gridspec_kw={"width_ratios": [1.2, 1]})
    largura = 0.27
    for i, combinacao in enumerate(COMBINACOES):
        classes = variantes[f"classe_geral_{combinacao}"].dropna()
        if classes.empty:
            continue
        proporcoes = [100 * float((classes == classe).mean()) for classe in CLASSES]
        posicoes = [x + (i - 1) * largura for x in range(len(CLASSES))]
        retangulos = barras.bar(posicoes, proporcoes, width=largura, color=CORES[i],
                                edgecolor="white", linewidth=1, label=combinacao.upper())
        for retangulo, valor in zip(retangulos, proporcoes):
            barras.text(retangulo.get_x() + retangulo.get_width() / 2, valor + 1, f"{valor:.0f}",
                        ha="center", va="bottom", fontsize=5.5, color=TINTA_SECUNDARIA)
    barras.set_xticks(range(len(CLASSES)), CLASSES)
    barras.set_ylabel("% dos repositórios", fontsize=7.5, color=TINTA)
    barras.set_title("(a) Classe geral em cada combinação", fontsize=8, color=TINTA)
    barras.legend(frameon=False, fontsize=7, labelcolor=TINTA)
    eixo_limpo(barras)

    rotulos = {"release": "release", "release_pre": "release +\npré-release", "tag": "tag"}
    presentes = [u for u in UNIDADES if f"deployment_frequency_{u}" in variantes]
    dados = [variantes[f"deployment_frequency_{u}"].dropna() for u in presentes]
    caixas.boxplot(
        dados, widths=0.45, showmeans=True, patch_artist=True,
        boxprops={"facecolor": "#cde2fb", "edgecolor": CORES[0], "linewidth": 0.8},
        whiskerprops={"color": CORES[0], "linewidth": 0.8},
        capprops={"color": CORES[0], "linewidth": 0.8},
        medianprops={"color": TINTA, "linewidth": 1.4},
        meanprops={"marker": "^", "markerfacecolor": CORES[1], "markeredgecolor": "white",
                   "markersize": 6},
        flierprops={"marker": "o", "markersize": 2.5, "markerfacecolor": "none",
                    "markeredgecolor": TINTA_SECUNDARIA, "alpha": 0.6},
    )
    caixas.set_xticks(range(1, len(presentes) + 1), [rotulos[u] for u in presentes])
    caixas.set_yscale("log")
    caixas.yaxis.set_major_formatter(FuncFormatter(virgula))
    for valor, nome in ((7, "Elite"), (1, "High"), (1 / 4.35, "Medium")):
        caixas.axhline(valor, color=TINTA_SECUNDARIA, linewidth=0.6, linestyle=":")
        caixas.text(len(presentes) + 0.48, valor * 1.08, nome, fontsize=5.5, va="bottom",
                    ha="right", color=TINTA_SECUNDARIA)
    caixas.set_ylabel("deploys por semana (log)", fontsize=7.5, color=TINTA)
    caixas.set_title("(b) Frequência de deploy por unidade", fontsize=8, color=TINTA)
    caixas.plot([], [], color=TINTA, linewidth=1.4, label="mediana")
    caixas.plot([], [], linestyle="none", marker="^", markerfacecolor=CORES[1],
                markeredgecolor="white", markersize=6, label="média")
    caixas.legend(frameon=False, fontsize=6.5, loc="upper left", labelcolor=TINTA)
    eixo_limpo(caixas)
    figura.tight_layout()
    figura.savefig(caminho, dpi=200)
    plt.close(figura)


def _percentual(tabela, metrica, coluna):
    """Porcentual de uma celula da tabela de fatores, zero quando falta."""
    if metrica not in tabela.index:
        return 0.0
    valor = tabela.loc[metrica, coluna]
    if valor is None or pd.isna(valor):
        return 0.0
    return 100.0 * float(valor)


def grafico_migracao(tabela, caminho):
    """Migracao de classe por metrica em cada troca isolada.

    Cada barra mostra, de um lado, os repositorios que descem de classe, no
    meio os que ficam e do outro os que sobem.
    """
    figura, eixos = plt.subplots(2, 2, figsize=(7.5, 4.4))
    for eixo, (nome, _unidade, _lt, _cfr) in zip(eixos.ravel(), FATORES):
        parte = tabela[tabela["fator"] == nome].set_index("metrica")
        posicoes = list(range(len(METRICAS_ORDEM)))
        desce = [_percentual(parte, metrica, "desceu") for metrica in METRICAS_ORDEM]
        sobe = [_percentual(parte, metrica, "subiu") for metrica in METRICAS_ORDEM]
        fica = [max(0.0, 100.0 - d - s) for d, s in zip(desce, sobe)]
        eixo.barh(posicoes, desce, color=CORES[1], edgecolor="white", linewidth=0.8)
        eixo.barh(posicoes, fica, left=desce, color=CINZA, edgecolor="white", linewidth=0.8)
        eixo.barh(posicoes, sobe, left=[d + f for d, f in zip(desce, fica)],
                  color=CORES[2], edgecolor="white", linewidth=0.8)
        for posicao, valores in enumerate(zip(desce, fica, sobe)):
            inicio = 0.0
            for valor, cor in zip(valores, (CORES[1], CINZA, CORES[2])):
                if 9 <= valor <= 99.5:
                    eixo.text(inicio + valor / 2, posicao, f"{valor:.0f}%", ha="center",
                              va="center", fontsize=5.5, color="white" if cor != CINZA else TINTA)
                inicio += valor
            mudou = desce[posicao] + sobe[posicao]
            if mudou:
                eixo.text(103, posicao, f"mudou {mudou:.0f}%", va="center", fontsize=5.5,
                          color=TINTA_SECUNDARIA)
        eixo.set_yticks(posicoes, [ROTULOS_METRICA[metrica] for metrica in METRICAS_ORDEM],
                        fontsize=6.5)
        eixo.set_xlim(0, 125)
        eixo.set_xticks([0, 25, 50, 75, 100])
        eixo.invert_yaxis()
        eixo.set_title(ROTULOS_FATOR[nome], fontsize=8, color=TINTA)
        eixo.set_xlabel("% dos repositórios", fontsize=7, color=TINTA)
        eixo_limpo(eixo, grade="x")
    figura.tight_layout()
    figura.savefig(caminho, dpi=200)
    plt.close(figura)


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
    dist_metricas = distribuicao_metricas(variantes)
    pares = pd.DataFrame([comparar_par(variantes, a, b, metrica)
                          for metrica in METRICAS for a, b in PARES])
    tabela_unidades = unidades(variantes)
    fatores = fatores_isolados(variantes)
    fatores_por_metrica = fatores_metricas(variantes)
    dist.to_csv(os.path.join(pasta, "rq07_distribuicao.csv"), index=False)
    dist_metricas.to_csv(os.path.join(pasta, "rq07_classes_metricas.csv"), index=False)
    pares.to_csv(os.path.join(pasta, "rq07_pares.csv"), index=False)
    tabela_unidades.to_csv(os.path.join(pasta, "rq07_unidades.csv"), index=False)
    fatores.to_csv(os.path.join(pasta, "rq07_fatores.csv"), index=False)
    fatores_por_metrica.to_csv(os.path.join(pasta, "rq07_fatores_metricas.csv"), index=False)
    for a, b in PARES:
        transicoes(variantes, a, b).to_csv(os.path.join(pasta, f"rq07_transicoes_{a}_{b}.csv"))
    grafico(variantes, os.path.join(pasta, "rq07_transicoes.png"))
    grafico_classes_e_unidades(variantes, os.path.join(pasta, "rq07_classes_e_unidades.png"))
    grafico_migracao(fatores_por_metrica, os.path.join(pasta, "rq07_migracao_metricas.png"))

    texto = ("# RQ 07 - Sensibilidade\n\n## Distribuição da classe geral\n\n" + tabela_markdown(dist)
             + "\n## Classes por métrica\n\n"
             + "Cada métrica tem sua própria distribuição de classes: para cada combinação, a "
             + "tabela traz a proporção de repositórios em cada uma das quatro classes e a "
             + "classe mais comum (moda). O tempo de recuperação é o mesmo nas três "
             + "combinações, porque não depende da definição operacional.\n\n"
             + tabela_markdown(dist_metricas)
             + "\n## Pares de combinações\n\n" + tabela_markdown(pares)
             + "\n## Um fator de cada vez (contra C1)\n\n" + tabela_markdown(fatores)
             + "\n## Um fator de cada vez, por métrica\n\n"
             + "Cada troca isolada mexe em uma métrica por vez: trocar a unidade de deploy "
             + "altera a frequência (e o lead time (a), que é ancorado na mesma unidade), "
             + "trocar a variante do lead time altera a classe de lead time e trocar a "
             + "variante do CFR altera a classe de CFR. Em todos os casos a classe geral, "
             + "que combina as quatro métricas, também se move: a última linha da tabela "
             + "mostra quanto.\n\n"
             + tabela_markdown(fatores_por_metrica)
             + "\n## Unidades de deploy\n\n" + tabela_markdown(tabela_unidades))
    with open(os.path.join(pasta, "rq07.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto, flush=True)


if __name__ == "__main__":
    main()
