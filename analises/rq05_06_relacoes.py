"""RQ 05 e RQ 06: relacoes entre metricas e comparacao entre subgrupos.

Le data/dataset.csv e validacao/consenso_repositorios.csv e grava tabelas,
graficos e um resumo em markdown:

    python -m analises.rq05_06_relacoes

RQ 05: correlacao de Spearman entre a frequencia de deploy (RQ 01) e a taxa de
falha (RQ 03), separada nas variantes (a) e (b), e o CFR mediano por faixa de
frequencia, que mostra a dependencia do CFR (b) com a cadencia de releases.

RQ 06: comparacao das metricas DORA entre subgrupos de repositorios, com
Kruskal-Wallis (ou Mann-Whitney quando o fator tem so dois grupos), correcao
de Holm e tamanho de efeito.
"""
import argparse
import itertools
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from matplotlib.ticker import FuncFormatter  # noqa: E402
from scipy.stats import kruskal, mannwhitneyu, spearmanr  # noqa: E402
from statsmodels.stats.multitest import multipletests  # noqa: E402

from analises.comum import (  # noqa: E402
    CORES, DIR_DADOS, DIR_RESULTADOS, TINTA, TINTA_SECUNDARIA, eixo_limpo,
    garantir_pasta, resumo, virgula,
)
from metricas.classificacao import ROTULOS as ROTULOS_CLASSE  # noqa: E402
from metricas.classificacao import nota_frequencia  # noqa: E402

# metricas: chave, rotulo, coluna do dataset e unidade
METRICAS = (
    ("frequencia", "Deployment frequency (RQ 01)", "deployment_frequency_semana",
     "releases por semana"),
    ("lead_time_a", "Lead time por release (RQ 02 a)", "lead_time_a_horas", "horas"),
    ("lead_time_b", "Lead time por commit (RQ 02 b)", "lead_time_b_horas", "horas"),
    ("cfr_a", "CFR proxy de CI (RQ 03 a)", "cfr_a", "proporcao"),
    ("cfr_b", "CFR proxy de entrega (RQ 03 b)", "cfr_b", "proporcao"),
    ("recuperacao", "Tempo de recuperacao (RQ 04)", "recuperacao_horas", "horas"),
)
ROTULOS = {chave: (rotulo, coluna, unidade) for chave, rotulo, coluna, unidade in METRICAS}

# familias de correcao de Holm: a primaria sao as quatro metricas de
# referencia (C1) e a secundaria as duas variantes (b)
FAMILIA_PRIMARIA = ("frequencia", "lead_time_a", "cfr_a", "recuperacao")
FAMILIA_SECUNDARIA = ("lead_time_b", "cfr_b")

# pares da RQ 05: a frequencia contra cada metrica. Os dois primeiros sao os
# exigidos (CFR a e b); os outros completam a discussao velocidade x estabilidade.
PARES = (
    ("frequencia", "cfr_a", "RQ 05"),
    ("frequencia", "cfr_b", "RQ 05"),
    ("frequencia", "lead_time_a", "complemento"),
    ("frequencia", "lead_time_b", "complemento"),
    ("frequencia", "recuperacao", "complemento"),
)

# fatores da RQ 06: chave, rotulo, origem (dataset ou consenso) e coluna
FATORES = (
    ("linguagem", "Linguagem principal", "dataset", "linguagem"),
    ("quartil_estrelas", "Popularidade (quartis de estrelas)", "dataset", "quartil_estrelas"),
    ("quartil_contribuidores", "Contribuidores (quartis)", "dataset", "quartil_contribuidores"),
    ("quartil_idade", "Idade do repositorio (quartis)", "dataset", "quartil_idade"),
    ("tipo_projeto", "Tipo do projeto", "consenso", "tipo_projeto"),
)

# coluna numerica que da origem a cada quartil, para rotular os grupos
ORIGEM_QUARTIL = {
    "quartil_estrelas": ("stars", "estrelas", 0),
    "quartil_contribuidores": ("contributors", "contribuidores", 0),
    "quartil_idade": ("idade_anos", "anos", 1),
}

# uma linguagem com menos repositorios que isso nao entra no fator: o
# Kruskal-Wallis com grupo de n=1 nao diz nada
MINIMO_LINGUAGEM = 15
# grupo com menos que isso e descartado antes do teste
MINIMO_GRUPO = 2
ALFA = 0.05
CINZA = "#c9c9c9"
# faixas de frequencia da C1 (RQ 01), na ordem das notas
FAIXAS_FREQUENCIA = ("Low", "Medium", "High", "Elite")


def _ptbr(valor, casas=0):
    """Numero no formato brasileiro: ponto de milhar e virgula decimal."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _p_valor(p):
    """p-valor para rotulo de grafico: virgula decimal e 'p < 0,001' no piso."""
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "-"
    if p < 0.001:
        return "p < 0,001"
    return f"p = {p:.3f}".replace(".", ",")


def _formatar(valor, casas):
    """Valor para tabela markdown; numeros muito pequenos viram notacao cientifica."""
    if valor is None:
        return "-"
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, float):
        if math.isnan(valor):
            return "-"
        if valor != 0 and abs(valor) < 10 ** (-casas):
            return f"{valor:.2e}".replace(".", ",")
        texto = f"{valor:.{casas}f}"
        if "." in texto:
            texto = texto.rstrip("0").rstrip(".")
        return texto.replace(".", ",")
    return str(valor)


def tabela_md(tabela, casas=3, casas_coluna=None):
    """DataFrame como tabela Markdown, com numeros no formato brasileiro."""
    casas_coluna = casas_coluna or {}
    colunas = [str(c) for c in tabela.columns]
    linhas = ["| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
    for registro in tabela.itertuples(index=False):
        celulas = []
        for coluna, valor in zip(colunas, registro):
            celulas.append(_formatar(valor, casas_coluna.get(coluna, casas)))
        linhas.append("| " + " | ".join(celulas) + " |")
    return "\n".join(linhas) + "\n"


def forca_rho(rho):
    """Interpretacao do rho de Spearman (convencao usual)."""
    if rho is None or (isinstance(rho, float) and math.isnan(rho)):
        return None
    modulo = abs(rho)
    if modulo < 0.1:
        return "negligivel"
    if modulo < 0.3:
        return "fraco"
    if modulo < 0.5:
        return "moderado"
    return "forte"


def forca_eps2(eps2):
    """Interpretacao do eps2 do Kruskal-Wallis.

    O enunciado da a formula mas nao a escala; os limiares abaixo sao a
    convencao usual para medidas de tamano de efeito por posto, e ainda
    precisam de citacao no artigo.
    """
    if eps2 is None or (isinstance(eps2, float) and math.isnan(eps2)):
        return None
    if eps2 < 0.01:
        return "desprezivel"
    if eps2 < 0.06:
        return "pequeno"
    if eps2 < 0.14:
        return "medio"
    return "grande"


def forca_delta(delta):
    """Interpretacao do Cliff's delta (Romano et al., 2006)."""
    if delta is None or (isinstance(delta, float) and math.isnan(delta)):
        return None
    modulo = abs(delta)
    if modulo < 0.147:
        return "desprezivel"
    if modulo < 0.33:
        return "pequeno"
    if modulo < 0.474:
        return "medio"
    return "grande"


def _numerico(dataset, coluna):
    """Serie numerica de uma coluna, vazia quando a coluna nao existe."""
    if coluna not in dataset:
        return pd.Series(dtype=float)
    return pd.to_numeric(dataset[coluna], errors="coerce")


def _familia(metrica):
    """Familia de correcao de Holm de uma metrica."""
    return "primaria" if metrica in FAMILIA_PRIMARIA else "secundaria"


def corrigir_holm(tabela, familia="familia"):
    """Corrige os p-valores de Holm dentro de cada familia de testes.

    Um teste que nao foi aplicado (sem valor de p) fica de fora da correcao e
    nao invalida os outros da familia. Com `familia=None`, a tabela toda e uma
    familia so.
    """
    tabela = tabela.copy()
    tabela["p_holm"] = float("nan")
    if familia is None:
        partes = [(None, tabela)]
    else:
        partes = list(tabela.groupby(familia))
    for _chave, parte in partes:
        validas = parte["p"].notna()
        if not validas.any():
            continue
        p = parte.loc[validas, "p"].tolist()
        tabela.loc[parte.loc[validas].index, "p_holm"] = multipletests(p, method="holm")[1]
    return tabela


def correlacoes(dataset):
    """Spearman entre a frequencia de deploy e cada metrica (RQ 05)."""
    linhas = []
    for x, y, papel in PARES:
        coluna_x = ROTULOS[x][1]
        coluna_y = ROTULOS[y][1]
        pares = pd.concat([_numerico(dataset, coluna_x), _numerico(dataset, coluna_y)],
                          axis=1).dropna()
        n = int(len(pares))
        rho, p = float("nan"), float("nan")
        if n >= 3:
            try:
                resultado = spearmanr(pares.iloc[:, 0], pares.iloc[:, 1])
                rho, p = float(resultado.statistic), float(resultado.pvalue)
            except ValueError:
                pass
        linhas.append({
            "par": f"{x} x {y}", "papel": papel, "metrica_x": x, "metrica_y": y,
            "rotulo": f"{ROTULOS[x][0]} x {ROTULOS[y][0]}",
            "n": n, "rho": rho, "p": p,
        })
    tabela = pd.DataFrame(linhas)
    tabela = corrigir_holm(tabela, familia=None)
    tabela["forca"] = [forca_rho(valor) for valor in tabela["rho"]]
    return tabela


def matriz_spearman(dataset):
    """Matriz de Spearman entre todas as metricas."""
    chaves = [chave for chave, _r, _c, _u in METRICAS]
    pares = pd.DataFrame(index=chaves, columns=chaves, dtype=float)
    for x in chaves:
        for y in chaves:
            frame = pd.concat([_numerico(dataset, ROTULOS[x][1]),
                               _numerico(dataset, ROTULOS[y][1])], axis=1).dropna()
            if len(frame) < 3:
                pares.loc[x, y] = float("nan")
                continue
            try:
                pares.loc[x, y] = float(spearmanr(frame.iloc[:, 0], frame.iloc[:, 1]).statistic)
            except ValueError:
                pares.loc[x, y] = float("nan")
    pares.index.name = "metrica"
    return pares


def cfr_por_faixa(dataset):
    """CFR mediano em cada faixa de frequencia de deploy (C1).

    O CFR (b) conta uma release como falha quando existe uma release corretiva
    nos sete dias seguintes: quem publica menos de uma vez por mes raramente
    tem uma release seguinte dentro da janela e fica perto de zero, enquanto
    quem publica toda semana quase sempre tem. A tabela mede esse gradiente e
    e a ressalva da correlacao da RQ 05: o CFR (a), que nao depende da
    cadencia, serve de contraste.
    """
    frequencia = _numerico(dataset, ROTULOS["frequencia"][1])
    faixa = frequencia.map(
        lambda valor: ROTULOS_CLASSE.get(nota_frequencia(valor)) if pd.notna(valor) else None)
    frame = pd.DataFrame({
        "faixa": faixa,
        "frequencia": frequencia,
        "cfr_a": _numerico(dataset, ROTULOS["cfr_a"][1]),
        "cfr_b": _numerico(dataset, ROTULOS["cfr_b"][1]),
    })
    frame = frame[frame["faixa"].notna()]
    linhas = []
    for nome in FAIXAS_FREQUENCIA:
        parte = frame[frame["faixa"] == nome]
        cfr_b = parte["cfr_b"].dropna()
        linhas.append({
            "faixa": nome,
            "n": int(len(parte)),
            "frequencia_mediana": _mediana(parte["frequencia"]),
            "cfr_a_mediana": _mediana(parte["cfr_a"]),
            "cfr_b_mediana": _mediana(cfr_b),
            "cfr_b_n": int(len(cfr_b)),
            "cfr_b_zero": float((cfr_b == 0).mean()) if len(cfr_b) else float("nan"),
        })
    return pd.DataFrame(linhas)


def _mediana(serie):
    """Mediana de uma serie, nan quando nao ha valor."""
    serie = serie.dropna()
    return float(serie.median()) if len(serie) else float("nan")


def montar_fatores(dataset, consenso):
    """Grupos de cada fator da RQ 06, como serie alinhada ao dataset.

    A linguagem entra so com as linguagens que tem repositorios suficientes
    para comparar; os repositorios das outras linguagens ficam fora deste
    fator, mas continuam nos demais.
    """
    fatores = {}
    for chave, _rotulo, origem, coluna in FATORES:
        if origem == "dataset":
            if coluna not in dataset:
                continue
            serie = dataset[coluna]
        else:
            if "full_name" not in dataset or coluna not in consenso:
                continue
            rotulos = consenso.set_index("full_name")[coluna]
            serie = dataset["full_name"].map(rotulos)
        if chave == "linguagem":
            contagem = serie.value_counts()
            linguagens = contagem[contagem >= MINIMO_LINGUAGEM].index
            serie = serie.where(serie.isin(linguagens))
        fatores[chave] = serie
    return fatores


def rotulos_grupos(chave, serie):
    """Rotulo curto de cada grupo: Q1 a Q4 nos quartis, o proprio nome nos outros."""
    if chave in ORIGEM_QUARTIL:
        return {nome: f"Q{nome}" for nome in serie.dropna().unique()}
    return {nome: str(nome) for nome in sorted(serie.dropna().unique(), key=str)}


def faixas_grupos(dataset, chave, serie):
    """Descricao de cada grupo com a faixa de valores, nos fatores de quartil."""
    if chave not in ORIGEM_QUARTIL:
        return {nome: str(nome) for nome in sorted(serie.dropna().unique(), key=str)}
    coluna, unidade, casas = ORIGEM_QUARTIL[chave]
    frame = pd.DataFrame({"grupo": serie, "valor": _numerico(dataset, coluna)}).dropna()
    rotulos = {}
    for nome, parte in frame.groupby("grupo", sort=True):
        rotulos[nome] = (f"Q{nome}: {_ptbr(parte['valor'].min(), casas)}-"
                         f"{_ptbr(parte['valor'].max(), casas)} {unidade}")
    return rotulos


def _grupos(dataset, serie, coluna_metrica):
    """Valores da metrica por grupo, so com os grupos que tem comparacao valida."""
    frame = pd.DataFrame({"grupo": serie, "valor": _numerico(dataset, coluna_metrica)}).dropna()
    grupos = []
    for nome, parte in frame.groupby("grupo", sort=True):
        valores = parte["valor"].to_numpy()
        if len(valores) >= MINIMO_GRUPO:
            grupos.append((nome, valores))
    return grupos


def cliffs_delta(x, y):
    """Cliff's delta: 2 * U1 / (n1 * n2) - 1, com U1 de `mannwhitneyu(x, y)`."""
    x = list(x)
    y = list(y)
    n1, n2 = len(x), len(y)
    if n1 == 0 or n2 == 0:
        return None
    u = mannwhitneyu(x, y, alternative="two-sided").statistic
    return float(2 * u / (n1 * n2) - 1)


def comparar_grupos(dataset, serie, chave_fator, rotulo_fator, metricas):
    """Teste de cada metrica entre os grupos de um fator.

    Com tres ou mais grupos usa Kruskal-Wallis (epsilon ao quadrado); com
    dois grupos usa Mann-Whitney (Cliff's delta).
    """
    rotulos = rotulos_grupos(chave_fator, serie)
    linhas = []
    for metrica in metricas:
        rotulo_metrica, coluna_metrica, _unidade = ROTULOS[metrica]
        grupos = _grupos(dataset, serie, coluna_metrica)
        n = int(sum(len(valores) for _nome, valores in grupos))
        linha = {
            "fator": chave_fator, "rotulo_fator": rotulo_fator, "metrica": metrica,
            "rotulo_metrica": rotulo_metrica, "familia": _familia(metrica),
            "teste": "Kruskal-Wallis" if len(grupos) >= 3 else "Mann-Whitney",
            "n": n, "n_grupos": len(grupos),
            "grupos": "; ".join(f"{rotulos.get(nome, nome)}={len(valores)}"
                                for nome, valores in grupos),
            "H": float("nan"), "U": float("nan"), "p": float("nan"),
            "eps2": float("nan"), "delta": float("nan"), "tamanho": "", "nota": "",
        }
        if len(grupos) < 2:
            linha["nota"] = "menos de dois grupos com dados"
            linhas.append(linha)
            continue
        try:
            if len(grupos) >= 3:
                resultado = kruskal(*[valores for _nome, valores in grupos])
                linha["H"] = float(resultado.statistic)
                linha["p"] = float(resultado.pvalue)
                linha["eps2"] = float(resultado.statistic / (n - 1)) if n > 1 else float("nan")
                linha["tamanho"] = forca_eps2(linha["eps2"]) or ""
            else:
                (nome_a, valores_a), (nome_b, valores_b) = grupos
                resultado = mannwhitneyu(valores_a, valores_b, alternative="two-sided")
                linha["U"] = float(resultado.statistic)
                linha["p"] = float(resultado.pvalue)
                linha["delta"] = cliffs_delta(valores_a, valores_b)
                linha["tamanho"] = forca_delta(linha["delta"]) or ""
        except ValueError as erro:
            linha["nota"] = f"teste nao aplicavel: {erro}"
        linhas.append(linha)
    return pd.DataFrame(linhas)


def comparar_fatores(dataset, fatores):
    """Compara todas as metricas em todos os fatores, com a correcao de Holm."""
    partes = []
    for chave, rotulo, _origem, _coluna in FATORES:
        serie = fatores.get(chave)
        if serie is None:
            continue
        partes.append(comparar_grupos(dataset, serie, chave, rotulo,
                                      list(ROTULOS.keys())))
    if not partes:
        return pd.DataFrame()
    tabela = pd.concat(partes, ignore_index=True)
    return corrigir_holm(tabela)


def pos_hoc(dataset, fatores, tabela_grupos):
    """Comparacao par a par dos grupos de cada teste que passou pela correcao.

    Usa Mann-Whitney com Cliff's delta, corrigido por Holm dentro de cada
    familia (fator x metrica).
    """
    linhas = []
    for _, linha in tabela_grupos.iterrows():
        p_holm = linha.get("p_holm")
        if p_holm is None or (isinstance(p_holm, float) and math.isnan(p_holm)):
            continue
        if p_holm >= ALFA:
            continue
        serie = fatores.get(linha["fator"])
        if serie is None:
            continue
        rotulos = rotulos_grupos(linha["fator"], serie)
        faixas = faixas_grupos(dataset, linha["fator"], serie)
        grupos = _grupos(dataset, serie, ROTULOS[linha["metrica"]][1])
        for (nome_a, valores_a), (nome_b, valores_b) in itertools.combinations(grupos, 2):
            try:
                resultado = mannwhitneyu(valores_a, valores_b, alternative="two-sided")
            except ValueError:
                continue
            linhas.append({
                "fator": linha["fator"], "metrica": linha["metrica"],
                "grupo_a": rotulos.get(nome_a, str(nome_a)),
                "grupo_b": rotulos.get(nome_b, str(nome_b)),
                "faixa_a": faixas.get(nome_a, str(nome_a)),
                "faixa_b": faixas.get(nome_b, str(nome_b)),
                "n_a": int(len(valores_a)), "n_b": int(len(valores_b)),
                "U": float(resultado.statistic), "p": float(resultado.pvalue),
                "delta": cliffs_delta(valores_a, valores_b),
            })
    if not linhas:
        return pd.DataFrame(columns=["fator", "metrica", "grupo_a", "grupo_b", "faixa_a",
                                     "faixa_b", "n_a", "n_b", "U", "p", "p_holm", "delta",
                                     "tamanho"])
    tabela = pd.DataFrame(linhas)
    tabela = corrigir_holm(tabela, familia=["fator", "metrica"])
    tabela["tamanho"] = [forca_delta(valor) for valor in tabela["delta"]]
    return tabela


def medianas_por_grupo(dataset, fatores):
    """Mediana, quartis e IQR de cada metrica em cada grupo de cada fator."""
    linhas = []
    for chave, rotulo, _origem, _coluna in FATORES:
        serie = fatores.get(chave)
        if serie is None:
            continue
        rotulos = rotulos_grupos(chave, serie)
        faixas = faixas_grupos(dataset, chave, serie)
        for metrica, rotulo_metrica, coluna_metrica, _unidade in METRICAS:
            for nome, valores in _grupos(dataset, serie, coluna_metrica):
                linha = {"fator": chave, "rotulo_fator": rotulo, "metrica": metrica,
                         "rotulo_metrica": rotulo_metrica,
                         "grupo": rotulos.get(nome, str(nome)),
                         "faixa": faixas.get(nome, str(nome)),
                         **resumo(pd.Series(valores))}
                linhas.append(linha)
    return pd.DataFrame(linhas)


def descricao_fatores(dataset, fatores):
    """Fatores usados na RQ 06, com os grupos e o numero de repositorios."""
    linhas = []
    for chave, rotulo, _origem, _coluna in FATORES:
        serie = fatores.get(chave)
        if serie is None:
            continue
        faixas = faixas_grupos(dataset, chave, serie)
        grupos = [(nome, int((serie == nome).sum()))
                  for nome in sorted(serie.dropna().unique(), key=str)]
        observacao = ""
        if chave == "linguagem":
            fora = int(dataset["linguagem"].notna().sum() - sum(n for _n, n in grupos))
            observacao = (f"linguagens com n >= {MINIMO_LINGUAGEM}; "
                          f"{fora} repositorios fora do fator")
        if chave == "tipo_projeto":
            observacao = "rotulo manual da amostra-ouro (60 repositorios)"
        linhas.append({
            "fator": chave, "rotulo": rotulo, "n": int(serie.notna().sum()),
            "grupos": "; ".join(f"{faixas.get(nome, nome)}={n}" for nome, n in grupos),
            "observacao": observacao,
        })
    return pd.DataFrame(linhas)


def _quintis(serie, n=5):
    """Divide a serie em n faixas de tamanho igual, por posto (empates nao quebram)."""
    return pd.qcut(serie.rank(method="first"), n, labels=False)


def grafico_dispersao(dataset, tabela_spearman, caminho):
    """Dispersao da frequencia de deploy contra o CFR, nas variantes (a) e (b).

    O eixo x e logaritmico porque a frequencia varia ordens de grandeza; o CFR
    e uma proporcao e tem zeros, entao fica em escala linear. A linha de
    tendencia e a mediana do CFR em cada quintil da frequencia: Spearman mede
    monotonicidade, e nao ajuste de reta.
    """
    figura, eixos = plt.subplots(1, 2, figsize=(7.5, 3.0))
    frequencia = _numerico(dataset, ROTULOS["frequencia"][1])
    for eixo, (chave, titulo) in zip(eixos, (("cfr_a", "(a) CFR proxy de CI"),
                                              ("cfr_b", "(b) CFR proxy de entrega"))):
        cfr = _numerico(dataset, ROTULOS[chave][1])
        frame = pd.DataFrame({"frequencia": frequencia, "cfr": cfr}).dropna()
        eixo.scatter(frame["frequencia"], frame["cfr"], s=8, color=CORES[0], alpha=0.35,
                     linewidths=0, zorder=2)
        if len(frame) >= 5:
            faixas = _quintis(frame["frequencia"])
            tendencia = frame.groupby(faixas)["cfr"].median()
            centro = frame.groupby(faixas)["frequencia"].median()
            eixo.plot(centro, tendencia, color=CORES[1], linewidth=1.6, zorder=3,
                      label="mediana por quintil")
        linha = tabela_spearman[tabela_spearman["metrica_y"] == chave]
        if len(linha):
            item = linha.iloc[0]
            rho = f"{item['rho']:+.3f}".replace(".", ",")
            eixo.set_title(f"{titulo}: \u03c1 = {rho} "
                           f"({_p_valor(item['p'])}, n = {int(item['n'])})",
                           fontsize=7.5, color=TINTA)
        eixo.set_xscale("log")
        eixo.set_ylim(-0.03, 1.03)
        eixo.set_xlabel("releases por semana (log)", fontsize=7.5, color=TINTA)
        eixo.set_ylabel("CFR", fontsize=7.5, color=TINTA)
        eixo.yaxis.set_major_formatter(FuncFormatter(virgula))
        eixo_limpo(eixo)
    eixos[0].legend(frameon=False, fontsize=6.5, labelcolor=TINTA, loc="upper left")
    figura.tight_layout()
    figura.savefig(caminho, dpi=200)
    plt.close(figura)


def grafico_efeitos(tabela_grupos, caminho):
    """Tamanho de efeito (epsilon ao quadrado) de cada fator em cada metrica.

    Azul quando o p corrigido por Holm fica abaixo de 0,05; cinza quando nao.
    """
    metrics = [chave for chave, _r, _c, _u in METRICAS]
    fatores = [fator for fator, _r, _o, _c in FATORES if fator in set(tabela_grupos["fator"])]
    figura, eixos = plt.subplots(2, 3, figsize=(7.5, 4.2))
    for eixo, metrica in zip(eixos.ravel(), metrics):
        rotulo_metrica, _coluna, _unidade = ROTULOS[metrica]
        parte = tabela_grupos[tabela_grupos["metrica"] == metrica]
        valores, cores, rotulos = [], [], []
        for fator in fatores:
            item = parte[parte["fator"] == fator]
            if item.empty:
                valores.append(0.0)
                cores.append(CINZA)
            else:
                item = item.iloc[0]
                valores.append(0.0 if pd.isna(item["eps2"]) else float(item["eps2"]))
                significativo = (not pd.isna(item["p_holm"])) and item["p_holm"] < ALFA
                cores.append(CORES[0] if significativo else CINZA)
            rotulos.append(fator.replace("quartil_", "quartil de "))
        posicoes = range(len(fatores))
        eixo.barh(list(posicoes), valores, color=cores, edgecolor="white", linewidth=0.8)
        for posicao, valor in zip(posicoes, valores):
            if valor > 0:
                eixo.text(valor + 0.004, posicao, f"{valor:.3f}", va="center",
                          fontsize=5.5, color=TINTA_SECUNDARIA)
        eixo.set_yticks(list(posicoes), rotulos, fontsize=6.5)
        eixo.set_xlim(0, max(0.05, max(valores) * 1.25))
        eixo.set_title(rotulo_metrica.split(" (")[0], fontsize=7.5, color=TINTA)
        eixo.set_xlabel("eps2", fontsize=7, color=TINTA)
        eixo_limpo(eixo, grade="x")
    figura.tight_layout()
    figura.savefig(caminho, dpi=200)
    plt.close(figura)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="analises.rq05_06_relacoes",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", default=os.path.join(DIR_DADOS, "dataset.csv"))
    parser.add_argument("--consenso",
                        default=os.path.join("validacao", "consenso_repositorios.csv"))
    parser.add_argument("--saida", default=DIR_RESULTADOS)
    args = parser.parse_args(argv)
    pasta = garantir_pasta(args.saida)

    dataset = pd.read_csv(args.dataset)
    consenso = pd.read_csv(args.consenso)

    tabela_spearman = correlacoes(dataset)
    matriz = matriz_spearman(dataset)
    tabela_faixas = cfr_por_faixa(dataset)
    fatores = montar_fatores(dataset, consenso)
    tabela_fatores = descricao_fatores(dataset, fatores)
    tabela_grupos = comparar_fatores(dataset, fatores)
    tabela_pos = pos_hoc(dataset, fatores, tabela_grupos)
    tabela_medianas = medianas_por_grupo(dataset, fatores)

    tabela_spearman.to_csv(os.path.join(pasta, "rq05_spearman.csv"), index=False)
    matriz.to_csv(os.path.join(pasta, "rq05_matriz_spearman.csv"))
    tabela_faixas.to_csv(os.path.join(pasta, "rq05_cfr_por_faixa.csv"), index=False)
    tabela_grupos.to_csv(os.path.join(pasta, "rq06_grupos.csv"), index=False)
    tabela_medianas.to_csv(os.path.join(pasta, "rq06_medianas.csv"), index=False)
    tabela_pos.to_csv(os.path.join(pasta, "rq06_pos_hoc.csv"), index=False)
    grafico_dispersao(dataset, tabela_spearman, os.path.join(pasta, "rq05_dispersao.png"))
    grafico_efeitos(tabela_grupos, os.path.join(pasta, "rq06_efeitos.png"))

    texto = _texto_resultado(dataset, tabela_fatores, tabela_spearman, tabela_faixas,
                              matriz, tabela_grupos, tabela_pos, tabela_medianas)
    with open(os.path.join(pasta, "rq05_06.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    print(texto, flush=True)


def _texto_resultado(dataset, tabela_fatores, tabela_spearman, tabela_faixas, matriz,
                      tabela_grupos, tabela_pos, tabela_medianas):
    """Resumo em markdown das duas RQs."""
    n = len(dataset)
    casas_p = {"p": 5, "p_holm": 5, "rho": 3, "eps2": 4, "delta": 4, "H": 3, "U": 3,
               "media": 2, "mediana": 2, "q1": 2, "q3": 2, "iqr": 2}
    destaque = tabela_spearman[tabela_spearman["papel"] == "RQ 05"]
    linhas_destaque = []
    for _i, linha in destaque.iterrows():
        linhas_destaque.append(
            f"- **{linha['metrica_y']}**: rho = {linha['rho']:+.3f} "
            f"(p = {linha['p']:.3g}, n = {int(linha['n'])}; "
            f"{forca_rho(linha['rho'])} apos Holm: p = {linha['p_holm']:.3g})"
        )

    primaria = tabela_grupos[tabela_grupos["familia"] == "primaria"]
    secundaria = tabela_grupos[tabela_grupos["familia"] == "secundaria"]
    significativas = tabela_grupos[
        tabela_grupos["p_holm"].notna() & (tabela_grupos["p_holm"] < ALFA)]
    pares_significativos = tabela_pos[
        tabela_pos["p_holm"].notna() & (tabela_pos["p_holm"] < ALFA)] if len(tabela_pos) else tabela_pos

    mediana_significativa = tabela_medianas.merge(
        significativas[["fator", "metrica"]], on=["fator", "metrica"], how="inner")

    colunas_grupos = ["fator", "metrica", "teste", "n", "grupos", "H", "p", "p_holm",
                      "eps2", "delta", "tamanho"]
    colunas_pos = ["fator", "metrica", "grupo_a", "grupo_b", "n_a", "n_b", "U", "p",
                   "p_holm", "delta", "tamanho"]
    colunas_medianas = ["fator", "metrica", "grupo", "n", "mediana", "q1", "q3", "iqr"]
    n_fatores = int(tabela_grupos["fator"].nunique())

    return (
        "# RQ 05 e RQ 06 - Correlacoes e comparacao entre grupos\n\n"
        f"RQ 05 (a frequencia de deploy se relaciona com a taxa de falha?) e RQ 06 (quais "
        f"caracteristicas do repositorio se associam as metricas DORA?), sobre os {n} "
        "repositorios de `data/dataset.csv`. A RQ 06 usa os rotulos de tipo de projeto da "
        "amostra-ouro, em `validacao/consenso_repositorios.csv`.\n\n"
        "## RQ 05 - frequencia de deploy e taxa de falha\n\n"
        "Correlacao de Spearman entre a frequencia de deploy (RQ 01) e a taxa de falha "
        "(RQ 03), calculada separadamente nas variantes (a) e (b). A dispersao "
        "(`rq05_dispersao.png`) tem o eixo da frequencia em escala logaritmica, porque a "
        "frequencia varia ordens de grandeza; o CFR e uma proporcao e tem zeros, entao fica "
        "em escala linear. A linha de tendencia e a mediana do CFR em cada quintil da "
        "frequencia: Spearman mede monotonicidade, e nao ajuste de reta.\n\n"
        "### Pares\n\n" + tabela_md(tabela_spearman, casas_coluna=casas_p)
        + "\nOs dois pares exigidos pela RQ 05:\n\n" + "\n".join(linhas_destaque) + "\n\n"
        + "### CFR por faixa de frequencia\n\n"
        "A taxa de falha (b) depende da cadencia: uma release so conta como falha quando "
        "existe uma release corretiva nos sete dias seguintes. Quem publica menos de uma vez "
        "por mes raramente tem uma release seguinte dentro da janela, e o CFR (b) fica perto "
        "de zero; quem publica toda semana quase sempre tem. A coluna `cfr_b_zero` e a "
        "proporcao de repositorios da faixa com CFR (b) exatamente zero. O CFR (a), que nao "
        "depende da cadencia de releases, fica estavel entre as faixas e serve de contraste.\n\n"
        + tabela_md(tabela_faixas, casas=3)
        + "\n### Matriz de Spearman\n\n" + tabela_md(matriz, casas=3)
        + "\n## RQ 06 - metricas DORA entre subgrupos\n\n"
        "### Fatores\n\n" + tabela_md(tabela_fatores)
        + "\nOs quartis vem das colunas da coleta (`data/dataset_meta.json` tem os limites). "
        "A linguagem entra so com as linguagens com repositorios suficientes para comparar; "
        "os repositorios das outras linguagens ficam fora deste fator, mas continuam nos "
        "demais.\n\n"
        f"### Familia primaria - as {len(FAMILIA_PRIMARIA)} metricas de referencia (C1)\n\n"
        f"{len(primaria)} testes ({n_fatores} fatores x {len(FAMILIA_PRIMARIA)} metricas), "
        "com correcao de Holm dentro da familia.\n\n"
        + tabela_md(primaria[colunas_grupos], casas_coluna=casas_p)
        + f"\n### Familia secundaria - as {len(FAMILIA_SECUNDARIA)} variantes (b)\n\n"
        f"{len(secundaria)} testes ({n_fatores} fatores x {len(FAMILIA_SECUNDARIA)} "
        "metricas), com correcao de Holm dentro da familia.\n\n"
        + tabela_md(secundaria[colunas_grupos], casas_coluna=casas_p)
        + "\n### Comparacao par a par dos testes que passaram pela correcao\n\n"
        "Mann-Whitney com Cliff's delta entre os grupos de cada combinacao com p corrigido "
        "abaixo de 0,05, com Holm dentro de cada familia (fator x metrica). O delta segue a "
        "escala de Romano et al. (2006): |delta| < 0,147 desprezivel; < 0,33 pequeno; "
        "< 0,474 medio; >= 0,474 grande.\n\n"
        + (tabela_md(pares_significativos[colunas_pos], casas_coluna=casas_p)
           if len(pares_significativos)
           else "Nenhuma comparacao par a par: nenhum teste passou pela correcao de Holm.\n")
        + "\n### Mediana e IQR por grupo (das combinacoes com p corrigido abaixo de 0,05)\n\n"
        + (tabela_md(mediana_significativa[colunas_medianas], casas_coluna=casas_p)
           if len(mediana_significativa)
           else "Nenhuma combinacao com p corrigido abaixo de 0,05.\n")
        + "\nA tabela completa com todas as combinacoes esta em `rq06_medianas.csv`; o "
        "tamanho de efeito de cada uma, em `rq06_grupos.csv`.\n"
    )


if __name__ == "__main__":
    main()
