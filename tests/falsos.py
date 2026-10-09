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
