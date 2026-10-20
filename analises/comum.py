import os

DIR_DADOS = "data"
DIR_RESULTADOS = os.path.join("analises", "resultados")
ORDEM_CLASSES = {"Low": 1, "Medium": 2, "High": 3, "Elite": 4}

# cores dos graficos: as tres primeiras de uma paleta categorica checada para
# daltonismo; texto e eixos ficam em cinza, nunca na cor da serie
CORES = ("#2a78d6", "#eb6834", "#1baf7a")
TINTA = "#0b0b0b"
TINTA_SECUNDARIA = "#52514e"
GRADE = "#e4e3df"


def virgula(valor, _posicao=None):
    """Numero do eixo com virgula decimal (0,5 em vez de 0.5)."""
    return f"{valor:g}".replace(".", ",")


def eixo_limpo(eixo, grade="y"):
    """Eixo discreto: sem moldura em cima e a direita, grade fina e clara."""
    for lado in ("top", "right"):
        eixo.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        eixo.spines[lado].set_color(GRADE)
    eixo.tick_params(colors=TINTA_SECUNDARIA, labelsize=7)
    if grade:
        eixo.grid(axis=grade, color=GRADE, linewidth=0.6)
    eixo.set_axisbelow(True)


def moda(serie):
    """Valor mais frequente (o menor, se houver empate).

    Em dado continuo, em que nenhum valor se repete, a moda nao diz nada e
    volta None.
    """
    contagem = serie.dropna().value_counts()
    if contagem.empty or contagem.iloc[0] < 2:
        return None
    mais_frequentes = contagem[contagem == contagem.iloc[0]].index
    valor = min(mais_frequentes)
    return valor.item() if hasattr(valor, "item") else valor


def resumo(serie):
    """Media, mediana, moda, quartis e IQR de uma metrica."""
    valores = serie.dropna()
    if valores.empty:
        return {"n": 0, "media": None, "mediana": None, "moda": None,
                "q1": None, "q3": None, "iqr": None}
    q1, mediana, q3 = (float(v) for v in valores.quantile([0.25, 0.5, 0.75]))
    return {"n": int(len(valores)), "media": float(valores.mean()), "mediana": mediana,
            "moda": moda(valores), "q1": q1, "q3": q3, "iqr": q3 - q1}


def tabela_markdown(tabela, casas=3):
    """DataFrame como tabela Markdown, para colar no README ou consultar rapido."""
    def formatar(valor):
        if isinstance(valor, float):
            return f"{valor:.{casas}f}"
        return str(valor)

    colunas = [str(c) for c in tabela.columns]
    linhas = ["| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
    for registro in tabela.itertuples(index=False):
        linhas.append("| " + " | ".join(formatar(v) for v in registro) + " |")
    return "\n".join(linhas) + "\n"


def garantir_pasta(pasta):
    os.makedirs(pasta, exist_ok=True)
    return pasta
