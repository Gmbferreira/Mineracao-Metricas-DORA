import os

DIR_DADOS = "data"
DIR_RESULTADOS = os.path.join("analises", "resultados")
ORDEM_CLASSES = {"Low": 1, "Medium": 2, "High": 3, "Elite": 4}


def resumo(serie):
    """Mediana e IQR (o enunciado pede essas duas, e nao media e desvio)."""
    valores = serie.dropna()
    if valores.empty:
        return {"n": 0, "mediana": None, "q1": None, "q3": None, "iqr": None}
    q1, mediana, q3 = (float(v) for v in valores.quantile([0.25, 0.5, 0.75]))
    return {"n": int(len(valores)), "mediana": mediana, "q1": q1, "q3": q3, "iqr": q3 - q1}


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
