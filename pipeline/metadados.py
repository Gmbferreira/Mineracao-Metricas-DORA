import datetime as dt
import math

from pipeline.cliente import ultima_pagina


def idade_anos(created_at, janela_fim):
    criado = dt.date.fromisoformat(created_at[:10])
    return round((janela_fim - criado).days / 365.25, 2)


def contar_contribuidores(cliente, nome):
    resposta = cliente.get(
        f"/repos/{nome}/contributors",
        {"per_page": 1, "anon": "true"},
        aceitar=(403, 404),
    )
    if resposta.status_code != 200:
        return 0
    total = ultima_pagina(resposta.headers.get("Link"))
    if total:
        return total
    itens = resposta.json()
    return len(itens) if isinstance(itens, list) else 0


def percentil(valores_ordenados, p):
    if not valores_ordenados:
        return None
    if len(valores_ordenados) == 1:
        return float(valores_ordenados[0])
    posicao = (len(valores_ordenados) - 1) * p
    inferior = math.floor(posicao)
    superior = math.ceil(posicao)
    if inferior == superior:
        return float(valores_ordenados[int(posicao)])
    return (
        valores_ordenados[inferior]
        + (valores_ordenados[superior] - valores_ordenados[inferior])
        * (posicao - inferior)
    )


def quartis(valores):
    ordenados = sorted(valores)
    limites = {
        "q1": percentil(ordenados, 0.25),
        "q2": percentil(ordenados, 0.50),
        "q3": percentil(ordenados, 0.75),
    }
    if limites["q1"] is None:
        return limites, []

    def rotulo(valor):
        if valor <= limites["q1"]:
            return 1
        if valor <= limites["q2"]:
            return 2
        if valor <= limites["q3"]:
            return 3
        return 4

    return limites, [rotulo(valor) for valor in valores]
