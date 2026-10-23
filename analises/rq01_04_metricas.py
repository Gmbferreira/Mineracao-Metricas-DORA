"""RQ 01 a RQ 04: estatistica descritiva das metricas e classificacao DORA (C1).

Le data/dataset.csv e grava tabelas, graficos e um resumo em markdown:

    python -m analises.rq01_04_metricas

Inclui a comparacao pareada das variantes (a) e (b) do lead time (RQ 02) e do
CFR (RQ 03), repositorio a repositorio, que complementa a comparacao entre as
medianas agregadas.
"""
import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from matplotlib.ticker import FuncFormatter  # noqa: E402

from analises.comum import (  # noqa: E402
    CORES, CORES_CLASSES, DIR_DADOS, DIR_RESULTADOS, TINTA, TINTA_SECUNDARIA,
    eixo_limpo, garantir_pasta, moda, resumo, tabela_markdown, virgula,
)
from metricas import classificacao  # noqa: E402

CLASSES = ("Elite", "High", "Medium", "Low")
DIA = classificacao.DIA
SEMANA = classificacao.SEMANA
MES_EM_SEMANAS = classificacao.MES_EM_SEMANAS
CINZA = "#c9c9c9"

# metricas da analise: chave, rotulo, coluna, unidade, escala log e os cortes
# das faixas DORA (limite, classe a partir do limite)
METRICAS = (
    ("frequencia", "Deployment frequency (RQ 01)", "deployment_frequency_semana",
     "releases por semana", True,
     ((7, "Elite"), (1, "High"), (1 / MES_EM_SEMANAS, "Medium"))),
    ("lead_time_a", "Lead time por release (RQ 02 a)", "lead_time_a_horas", "horas", True,
     ((DIA, "Elite"), (SEMANA, "High"), (30 * DIA, "Medium"))),
    ("lead_time_b", "Lead time por commit (RQ 02 b)", "lead_time_b_horas", "horas", True,
     ((DIA, "Elite"), (SEMANA, "High"), (30 * DIA, "Medium"))),
    ("cfr_a", "CFR proxy de CI (RQ 03 a)", "cfr_a", "proporcao", False,
     ((0.15, "Elite"), (0.30, "High"), (0.45, "Medium"))),
    ("cfr_b", "CFR proxy de entrega (RQ 03 b)", "cfr_b", "proporcao", False,
     ((0.15, "Elite"), (0.30, "High"), (0.45, "Medium"))),
    ("recuperacao", "Tempo de recuperacao (RQ 04)", "recuperacao_horas", "horas", True,
     ((1, "Elite"), (DIA, "High"), (SEMANA, "Medium"))),
)

# pares (a) x (b): nome, coluna de (a), coluna de (b), unidade
PARES = (
    ("lead_time", "lead_time_a_horas", "lead_time_b_horas", "horas"),
    ("cfr", "cfr_a", "cfr_b", "proporcao"),
)

# colunas de classe do dataset, na ordem em que entram na tabela de resumo
CLASSES_COLUNAS = (
    ("geral", "classe_geral"),
    ("frequencia", "classe_frequencia"),
    ("lead_time", "classe_lead_time"),
    ("cfr", "classe_cfr"),
    ("recuperacao", "classe_recuperacao"),
)


def numero(valor):
    """NaN do pandas vira None.

    `metricas.classificacao` testa `is None` em cada faixa, e nao `pd.isna`:
    um NaN cru passaria pelas comparacoes e cairia em "Low" em vez de ficar
    sem valor.
    """
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        return None
    return float(valor)


def coluna(dataset, nome):
    """Serie numerica da coluna, vazia quando a coluna nao existe."""
    if nome not in dataset:
        return pd.Series(dtype=float)
    return pd.to_numeric(dataset[nome], errors="coerce").dropna()


def texto_coluna(dataset, nome):
    """Serie de texto da coluna, vazia quando a coluna nao existe."""
    if nome not in dataset:
        return pd.Series(dtype=object)
    return dataset[nome].dropna()


def resumo_metricas(dataset):
    """Mediana, IQR, media e moda de cada metrica e variante."""
    linhas = []
    for chave, rotulo, nome_coluna, unidade, _log, _cortes in METRICAS:
        valores = coluna(dataset, nome_coluna)
        linha = {"metrica": chave, "rotulo": rotulo, "unidade": unidade, **resumo(valores)}
        em_dias = unidade == "horas" and linha["mediana"] is not None
        linha["mediana_dias"] = linha["mediana"] / DIA if em_dias else None
        linha["iqr_dias"] = linha["iqr"] / DIA if em_dias else None
        linhas.append(linha)
    return pd.DataFrame(linhas)


def pares_variantes(dataset):
    """Comparacao pareada das variantes (a) e (b), repositorio a repositorio.

    A tabela de resumo compara as medianas agregadas; aqui cada repositorio e
    comparado consigo mesmo. A razao (b)/(a) so e calculada quando todos os
    valores de (a) sao positivos -- no CFR, doze repositorios tem (a) = 0, e a
    razao nao faz sentido.
    """
    linhas = []
    for nome, coluna_a, coluna_b, unidade in PARES:
        par = pd.concat([coluna(dataset, coluna_a).rename("a"),
                         coluna(dataset, coluna_b).rename("b")], axis=1).dropna()
        razao = (par["b"] / par["a"]).median() if (par["a"] > 0).all() else None
        linhas.append({
            "par": f"{nome} (a) x (b)",
            "n": int(len(par)),
            "unidade": unidade,
            "mediana_a": float(par["a"].median()),
            "mediana_b": float(par["b"].median()),
            "proporcao_b_maior": float((par["b"] > par["a"]).mean()),
            "razao_mediana_b_a": razao,
            "diferenca_mediana_b_a": float((par["b"] - par["a"]).median()),
        })
    return pd.DataFrame(linhas, columns=["par", "n", "unidade", "mediana_a", "mediana_b",
                                         "proporcao_b_maior", "razao_mediana_b_a",
                                         "diferenca_mediana_b_a"])


def censura(dataset):
    """Censura da RQ 04 (episodios de falha) e da RQ 03 (b) (releases corretivas)."""
    episodios = coluna(dataset, "episodios")
    censurados = coluna(dataset, "episodios_censurados")
    proporcao = coluna(dataset, "proporcao_censurados")
    com_valor = coluna(dataset, "recuperacao_horas")
    sem_inicio = coluna(dataset, "falhas_sem_inicio")
    releases_censuradas = coluna(dataset, "releases_censuradas_cfr_b")
    releases_avaliadas = coluna(dataset, "releases_avaliadas_cfr_b")
    cfr_b = coluna(dataset, "cfr_b")
    total = len(dataset)

    n_censurados = int((censurados > 0).sum())
    todos_censurados = int((proporcao == 1).sum())
    resumo_censura = resumo(proporcao)
    linhas = [
        ("RQ 04 - episodios de falha", "episodios no total", int(episodios.sum()),
         "soma de `episodios` dos repositorios"),
        ("RQ 04 - episodios de falha", "episodios censurados", int(censurados.sum()),
         "falha sem sucesso ate o fim da janela"),
        ("RQ 04 - episodios de falha", "proporcao censurada agregada",
         float(censurados.sum() / episodios.sum()) if episodios.sum() else None,
         "episodios censurados / episodios"),
        ("RQ 04 - episodios de falha", "repositorios com tempo de recuperacao",
         int(len(com_valor)), "episodios recuperados no total"),
        ("RQ 04 - episodios de falha", "repositorios sem episodio de falha",
         int((episodios == 0).sum()), "nenhuma falha depois de um sucesso na janela"),
        ("RQ 04 - episodios de falha", "repositorios com ao menos um episodio censurado",
         int(n_censurados), "repositorios com pelo menos um episodio sem fim"),
        ("RQ 04 - episodios de falha", "proporcao desses repositorios",
         float(n_censurados / len(com_valor)) if len(com_valor) else None,
         "sobre os repositorios com tempo de recuperacao"),
        ("RQ 04 - episodios de falha", "repositorios com todos os episodios censurados",
         int(todos_censurados), "toda falha da janela ficou sem recuperacao"),
        ("RQ 04 - censura por repositorio", "mediana da proporcao", resumo_censura["mediana"],
         "`proporcao_censurados` de cada repositorio"),
        ("RQ 04 - censura por repositorio", "q1 da proporcao", resumo_censura["q1"], "1o quartil"),
        ("RQ 04 - censura por repositorio", "q3 da proporcao", resumo_censura["q3"], "3o quartil"),
        ("RQ 04 - censura por repositorio", "iqr da proporcao", resumo_censura["iqr"], "q3 - q1"),
        ("RQ 04 - falhas sem inicio", "runs de falha antes do primeiro sucesso",
         int(sem_inicio.sum()),
         "falhas no comeco da janela, sem sucesso antes: nao abrem episodio"),
        ("RQ 03 (b) - censura", "releases censuradas", int(releases_censuradas.sum()),
         "releases dos ultimos 7 dias da janela, sem como saber se houve correcao"),
        ("RQ 03 (b) - censura", "releases avaliadas", int(releases_avaliadas.sum()),
         "releases com os 7 dias seguintes ainda dentro da janela"),
        ("RQ 03 (b) - censura", "repositorios sem CFR (b)", int(total - len(cfr_b)),
         "todas as releases do repositorio ficaram censuradas"),
    ]
    tabela = pd.DataFrame(linhas, columns=["categoria", "indicador", "valor", "detalhe"],
                          dtype=object)
    return tabela


def classes_dora(dataset):
    """Proporcao de repositorios em cada classe DORA (C1), na geral e por metrica."""
    linhas = []
    for metrica, nome_coluna in CLASSES_COLUNAS:
        classes = texto_coluna(dataset, nome_coluna)
        total = len(dataset)
        linha = {"metrica": metrica, "n": int(len(classes))}
        for classe in CLASSES:
            n = int((classes == classe).sum())
            linha[classe] = float(n / len(classes)) if len(classes) else None
        linha["sem_valor"] = total - int(len(classes))
        linha["moda"] = moda(classes)
        linhas.append(linha)
    return pd.DataFrame(linhas)


def conferir_classificacao(dataset):
    """Recalcula a classificacao C1 e compara com as colunas do dataset.

    Devolve as divergencias; uma lista vazia significa que o dataset esta
    de acordo com as faixas de `metricas.classificacao`.
    """
    divergencias = []
    for _, linha in dataset.iterrows():
        classes = classificacao.classificar_repositorio(
            numero(linha.get("deployment_frequency_semana")),
            numero(linha.get("lead_time_a_horas")),
            numero(linha.get("cfr_a")),
            numero(linha.get("recuperacao_horas")),
        )
        esperado = {
            "classe_frequencia": classes["classe_frequencia"],
            "classe_lead_time": classes["classe_lead_time"],
            "classe_cfr": classes["classe_cfr"],
            "classe_recuperacao": classes["classe_recuperacao"],
            "classe_geral": classes["classe_geral"],
        }
        for nome_coluna, valor in esperado.items():
            if nome_coluna not in dataset:
                continue
            do_dataset = linha.get(nome_coluna)
            do_dataset = "" if do_dataset is None or pd.isna(do_dataset) else str(do_dataset)
            if do_dataset != valor:
                divergencias.append({"full_name": linha.get("full_name"), "coluna": nome_coluna,
                                     "dataset": do_dataset, "recalculado": valor})
    return pd.DataFrame(divergencias, columns=["full_name", "coluna", "dataset", "recalculado"])


def _caixa(eixo, dados, rotulos):
    """Boxplot no estilo do repo: caixa azul, mediana em tinta e media em triangulo."""
    eixo.boxplot(
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
    eixo.set_xticks(range(1, len(rotulos) + 1), rotulos)


def _cortes(eixo, cortes):
    """Linhas tracejadas nos limites das faixas DORA, com o nome da classe."""
    for limite, classe in cortes:
        eixo.axhline(limite, color=TINTA_SECUNDARIA, linewidth=0.6, linestyle=":")
        eixo.text(0.99, limite, classe, transform=eixo.get_yaxis_transform(), ha="right",
                  va="bottom", fontsize=5.5, color=TINTA_SECUNDARIA)


def grafico_distribuicao(dataset, caminho):
    """Boxplot das quatro metricas, com a media marcada e os cortes das faixas."""
    figura, eixos = plt.subplots(2, 2, figsize=(7.5, 5.0))
    # o titulo vem do painel, e nao da primeira metrica: em (b) e (c) a caixa
    # das duas variantes divide o mesmo eixo. Painel de uma caixa so (rotulos
    # None) mostra quantos repositorios entram nela
    paineis = (
        (eixos[0][0], "Deployment frequency", ("frequencia",), None,
         "releases por semana (log)"),
        (eixos[0][1], "Lead time for changes", ("lead_time_a", "lead_time_b"),
         ("(a) por release", "(b) por commit"), "horas (log)"),
        (eixos[1][0], "Change failure rate", ("cfr_a", "cfr_b"),
         ("(a) proxy de CI", "(b) proxy de entrega"), "proporção"),
        (eixos[1][1], "Tempo de recuperação", ("recuperacao",), None, "horas (log)"),
    )
    especificacoes = {metrica[0]: metrica for metrica in METRICAS}
    for i, (eixo, titulo, chaves, rotulos, titulo_y) in enumerate(paineis):
        dados = [coluna(dataset, especificacoes[chave][2]) for chave in chaves]
        if rotulos is None:
            rotulos = [f"{len(valores)} repositórios" for valores in dados]
        if any(len(dados) for dados in dados):
            _caixa(eixo, dados, rotulos)
        _cortes(eixo, especificacoes[chaves[0]][5])
        if especificacoes[chaves[0]][4]:
            eixo.set_yscale("log")
        else:
            # so o CFR e linear: e uma proporcao, de 0 a 1
            eixo.set_yscale("linear")
            eixo.yaxis.set_major_formatter(FuncFormatter(virgula))
            eixo.set_ylim(-0.02, 1.02)
        eixo.set_ylabel(titulo_y, fontsize=7.5, color=TINTA)
        eixo.set_title(f"({'abcd'[i]}) {titulo}", fontsize=8, color=TINTA)
        eixo_limpo(eixo)
    figura.tight_layout()
    figura.savefig(caminho, dpi=200)
    plt.close(figura)


def grafico_classes(dataset, caminho):
    """(a) classe geral em barras; (b) classes de cada metrica em barras empilhadas."""
    figura, (geral, por_metrica) = plt.subplots(1, 2, figsize=(7.5, 3.2),
                                                gridspec_kw={"width_ratios": [1, 1.25]})
    classes = texto_coluna(dataset, "classe_geral")
    contagem = [int((classes == classe).sum()) for classe in CLASSES]
    total = sum(contagem)
    proporcoes = [100 * n / total if total else 0 for n in contagem]
    barras = geral.bar(range(len(CLASSES)), proporcoes, color=CORES_CLASSES,
                        edgecolor="white", linewidth=1)
    for barra, valor, n in zip(barras, proporcoes, contagem):
        geral.text(barra.get_x() + barra.get_width() / 2, valor + 1.5, str(n),
                   ha="center", va="bottom", fontsize=6.5, color=TINTA_SECUNDARIA)
    geral.set_xticks(range(len(CLASSES)), CLASSES)
    geral.set_ylabel("% dos repositórios", fontsize=7.5, color=TINTA)
    geral.set_title("(a) Classe geral (C1)", fontsize=8, color=TINTA)
    eixo_limpo(geral)

    nomes = ("classe_frequencia", "classe_lead_time", "classe_cfr", "classe_recuperacao")
    base = [0.0] * len(nomes)
    for i, classe in enumerate(CLASSES):
        valores = []
        for nome_coluna in nomes:
            serie = texto_coluna(dataset, nome_coluna)
            valores.append(100 * int((serie == classe).sum()) / len(serie) if len(serie) else 0.0)
        por_metrica.barh(range(len(nomes)), valores, left=base, color=CORES_CLASSES[i],
                         edgecolor="white", linewidth=1, label=classe)
        base = [b + v for b, v in zip(base, valores)]
    sem_valor = []
    for nome_coluna in nomes:
        serie = texto_coluna(dataset, nome_coluna)
        sem_valor.append(100 * (1 - len(serie) / len(dataset)) if len(dataset) else 0.0)
    por_metrica.barh(range(len(nomes)), sem_valor, left=base, color=CINZA,
                     edgecolor="white", linewidth=1, label="sem valor")
    por_metrica.set_yticks(range(len(nomes)), ["Frequência", "Lead time", "CFR", "Recuperação"])
    por_metrica.invert_yaxis()
    por_metrica.set_xlabel("% dos repositórios", fontsize=7.5, color=TINTA)
    por_metrica.set_title("(b) Classe de cada métrica", fontsize=8, color=TINTA)
    por_metrica.set_xlim(0, 100)
    eixo_limpo(por_metrica, grade="x")
    alvos, rotulos = por_metrica.get_legend_handles_labels()
    figura.legend(alvos, rotulos, loc="lower center", ncol=5, frameon=False, fontsize=6.5,
                  labelcolor=TINTA, bbox_to_anchor=(0.5, 0.01))
    figura.tight_layout(rect=(0, 0.15, 1, 1))
    figura.savefig(caminho, dpi=200)
    plt.close(figura)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="analises.rq01_04_metricas",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", default=os.path.join(DIR_DADOS, "dataset.csv"))
    parser.add_argument("--saida", default=DIR_RESULTADOS)
    args = parser.parse_args(argv)
    pasta = garantir_pasta(args.saida)

    dataset = pd.read_csv(args.dataset)
    resumos = resumo_metricas(dataset)
    tabela_pares = pares_variantes(dataset)
    tabela_censura = censura(dataset)
    tabela_classes = classes_dora(dataset)
    divergencias = conferir_classificacao(dataset)

    resumos.to_csv(os.path.join(pasta, "rq01_04_resumo.csv"), index=False)
    tabela_pares.to_csv(os.path.join(pasta, "rq01_04_pares.csv"), index=False)
    tabela_censura.to_csv(os.path.join(pasta, "rq01_04_censura.csv"), index=False)
    tabela_classes.to_csv(os.path.join(pasta, "rq01_04_classes.csv"), index=False)
    grafico_distribuicao(dataset, os.path.join(pasta, "rq01_04_distribuicao.png"))
    grafico_classes(dataset, os.path.join(pasta, "rq01_04_classes.png"))

    n = len(dataset)
    geral = tabela_classes.set_index("metrica").loc["geral"]
    contagem = ", ".join(
        f"{classe} {int(geral[classe] * geral['n'])} ({virgula(round(100 * geral[classe], 1))}%)"
        for classe in CLASSES
    )
    if divergencias.empty:
        verificacao = (
            f"Recalculada do zero com `metricas.classificacao.classificar_repositorio`, a "
            f"classificação C1 bate com as colunas `classe_*` do dataset nos {n} repositórios, "
            "sem divergência."
        )
    else:
        verificacao = (
            f"**{len(divergencias)} divergências** entre a classificação C1 recalculada e as "
            f"colunas `classe_*` do dataset:\n\n" + tabela_markdown(divergencias)
        )
    zeros_cfr = int((coluna(dataset, "cfr_a") == 0).sum())
    nota_razao = (
        f"A razão só é calculada quando todos os valores de (a) são positivos; no CFR, "
        f"{zeros_cfr} repositórios têm (a) = 0, então ela fica vazia."
        if zeros_cfr else
        "A razão só é calculada quando todos os valores de (a) são positivos."
    )
    texto = (
        "# RQ 01 a RQ 04 - Métricas e classificação DORA\n\n"
        f"Estatística descritiva das RQ 01 a RQ 04 e classificação DORA de referência (C1), "
        f"sobre os {n} repositórios de `data/dataset.csv`. O enunciado pede mediana e IQR, e não "
        "média e desvio-padrão, porque as distribuições são muito assimétricas; média e moda "
        "entram como complemento. Lead time e tempo de recuperação também são mostrados em "
        "dias, para facilitar a leitura.\n\n"
        "## Resumo das métricas\n\n" + tabela_markdown(resumos)
        + "\n## Comparação entre as variantes (a) e (b)\n\n"
        "Cada repositório comparado consigo mesmo: `proporcao_b_maior` é a fração de "
        "repositórios em que (b) > (a), `razao_mediana_b_a` é a mediana da razão (b)/(a) e "
        "`diferenca_mediana_b_a` é a mediana da diferença (b) - (a), na unidade da métrica. "
        + nota_razao + "\n\n"
        + tabela_markdown(tabela_pares)
        + "\n## Censura\n\n" + tabela_markdown(tabela_censura)
        + "\n## Classes DORA (C1)\n\n" + tabela_markdown(tabela_classes)
        + f"\nNa classe geral, {contagem}.\n\n"
        + "## Verificação da classificação\n\n" + verificacao + "\n"
    )
    with open(os.path.join(pasta, "rq01_04.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto, flush=True)


if __name__ == "__main__":
    main()
