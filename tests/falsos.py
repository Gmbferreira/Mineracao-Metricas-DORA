class RespostaFalsa:
    def __init__(self, status_code=200, dados=None, headers=None):
        self.status_code = status_code
        self._dados = dados
        self.headers = headers or {}

    def json(self):
        return self._dados


class ClienteFalso:
    """Responde por (caminho, pagina) e registra as chamadas feitas."""

    def __init__(self, rotas):
        self.rotas = rotas
        self.chamadas = []

    def get(self, caminho, params=None, aceitar=(), reduzir=None, **_):
        params = params or {}
        self.chamadas.append((caminho, dict(params)))
        chave = (caminho, params.get("page", 1))
        resposta = self.rotas.get(chave, self.rotas.get(caminho))
        if callable(resposta):
            resposta = resposta(params)
        if resposta is None:
            return RespostaFalsa(200, [])
        if isinstance(resposta, Exception):
            raise resposta
        if resposta.status_code == 200 and reduzir is not None:
            return RespostaFalsa(200, reduzir(resposta.json()), resposta.headers)
        return resposta


def runs_por_intervalo(runs, teto=None):
    """Responde a /actions/runs filtrando `runs` pelo intervalo `created`, como a API.

    Com `teto`, o `total_count` de intervalos maiores que o teto vem certo, mas a
    pagina traz so os primeiros (igual a API, que nao entrega mais que o teto).
    """
    def responder(params):
        inicio, fim = params["created"].split("..")
        dentro = [run for run in runs if inicio <= run["created_at"] <= fim]
        por_pagina = params.get("per_page", 100)
        pagina = params.get("page", 1)
        visiveis = dentro if teto is None else dentro[:teto]
        trecho = visiveis[(pagina - 1) * por_pagina: pagina * por_pagina]
        return RespostaFalsa(200, {"total_count": len(dentro), "workflow_runs": trecho})

    return responder
