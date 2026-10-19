import time

import pytest
import requests

from pipeline.cliente import ClienteGitHub


class Resposta:
    def __init__(self, status_code=200, dados=None, headers=None, texto=""):
        self.status_code = status_code
        self._dados = dados
        self.headers = headers or {}
        self.text = texto

    def json(self):
        if self._dados is None:
            raise ValueError("resposta sem json")
        return self._dados


class Sessao:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.corpos = []

    def get(self, url, params=None, timeout=None):
        return self._proxima()

    def post(self, url, json=None, timeout=None):
        self.corpos.append(json)
        return self._proxima()

    def _proxima(self):
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def _cabecalhos(recurso="graphql", remaining="4999", reset="9999999999"):
    return {"X-RateLimit-Resource": recurso, "X-RateLimit-Remaining": remaining,
            "X-RateLimit-Reset": reset}


def _cliente(monkeypatch, respostas, cache_dir=None):
    sleeps = []
    monkeypatch.setattr("pipeline.cliente.time.sleep", lambda s: sleeps.append(s))
    cliente = ClienteGitHub(token="x", cache_dir=cache_dir)
    cliente.sessao = Sessao(respostas)
    return cliente, sleeps


def test_graphql_guarda_no_cache_e_nao_repete(monkeypatch, tmp_path):
    ok = Resposta(200, {"data": {"x": 1}}, _cabecalhos())
    cliente, _ = _cliente(monkeypatch, [ok], cache_dir=str(tmp_path))
    primeira = cliente.graphql("query { x }", {"a": 1}, repositorio="o/r")
    segunda = cliente.graphql("query { x }", {"a": 1}, repositorio="o/r")
    assert primeira == segunda == {"data": {"x": 1}}
    assert cliente.chamadas_graphql == 1
    assert cliente.chamadas == 0
    assert cliente.sessao.corpos[0] == {"query": "query { x }", "variables": {"a": 1}}
    assert (tmp_path / "repos__o__r").is_dir()


def test_graphql_com_erro_nao_vai_para_o_cache(monkeypatch, tmp_path):
    erro = Resposta(200, {"errors": [{"message": "x"}]}, _cabecalhos())
    ok = Resposta(200, {"data": {"x": 2}}, _cabecalhos())
    cliente, _ = _cliente(monkeypatch, [erro, ok], cache_dir=str(tmp_path))
    assert "errors" in cliente.graphql("query { x }")
    assert cliente.graphql("query { x }") == {"data": {"x": 2}}
    assert cliente.chamadas_graphql == 2


def test_graphql_espera_a_cota_quando_limitada(monkeypatch):
    reset = int(time.time() + 40)
    limitada = Resposta(200, {"errors": [{"type": "RATE_LIMITED"}]},
                        _cabecalhos(remaining="0", reset=str(reset)))
    ok = Resposta(200, {"data": {"x": 1}}, _cabecalhos())
    cliente, sleeps = _cliente(monkeypatch, [limitada, ok])
    assert cliente.graphql("query { x }") == {"data": {"x": 1}}
    assert len(sleeps) == 1 and 39 <= sleeps[0] <= 42


def test_graphql_limitada_sem_cabecalho_de_reset(monkeypatch):
    limitada = Resposta(200, {"errors": [{"type": "RATE_LIMITED"}]}, {})
    ok = Resposta(200, {"data": {"x": 1}}, _cabecalhos())
    cliente, sleeps = _cliente(monkeypatch, [limitada, ok])
    assert cliente.graphql("query { x }") == {"data": {"x": 1}}
    assert len(sleeps) == 1 and 55 <= sleeps[0] <= 62


def test_graphql_limite_ja_excedido_com_cota_sobrando(monkeypatch):
    # resposta real do GitHub com a cota da hora ainda com pontos
    limitada = Resposta(200, {"errors": [{"type": "RATE_LIMIT", "code": "graphql_rate_limit",
                                          "message": "API rate limit already exceeded"}]},
                        _cabecalhos(remaining="3835", reset=str(int(time.time() + 10))))
    ok = Resposta(200, {"data": {"x": 1}}, _cabecalhos())
    cliente, sleeps = _cliente(monkeypatch, [limitada, ok])
    assert cliente.graphql("query { x }") == {"data": {"x": 1}}
    assert len(sleeps) == 1 and 59 <= sleeps[0] <= 62


def test_cota_da_graphql_nao_trava_o_rest(monkeypatch):
    reset = int(time.time() + 40)
    respostas = [
        Resposta(200, {"data": {}}, _cabecalhos(remaining="0", reset=str(reset))),
        Resposta(200, {"ok": 1}, _cabecalhos(recurso="core")),
    ]
    cliente, sleeps = _cliente(monkeypatch, respostas)
    cliente.graphql("query { x }")
    cliente.get("/repos/a/b")
    assert sleeps == []


def test_graphql_backoff_em_5xx_queda_e_resposta_sem_json(monkeypatch):
    respostas = [
        Resposta(502, texto="bad gateway"),
        requests.ConnectionError("caiu"),
        Resposta(200, None, _cabecalhos(), texto="<html>"),
        Resposta(200, {"data": {"x": 1}}, _cabecalhos()),
    ]
    cliente, sleeps = _cliente(monkeypatch, respostas)
    assert cliente.graphql("query { x }") == {"data": {"x": 1}}
    assert sleeps == [1.0, 2.0, 4.0]


def test_graphql_cota_secundaria_403(monkeypatch):
    respostas = [
        Resposta(403, headers={"Retry-After": "5"}),
        Resposta(200, {"data": {"x": 1}}, _cabecalhos()),
    ]
    cliente, sleeps = _cliente(monkeypatch, respostas)
    assert cliente.graphql("query { x }") == {"data": {"x": 1}}
    assert sleeps == [6]


def test_graphql_erro_definitivo_e_tentativas_esgotadas(monkeypatch):
    cliente, _ = _cliente(monkeypatch, [Resposta(401, texto="bad credentials")])
    with pytest.raises(RuntimeError, match="HTTP 401"):
        cliente.graphql("query { x }")
    cliente, _ = _cliente(monkeypatch, [Resposta(503, texto="x") for _ in range(6)])
    with pytest.raises(RuntimeError, match="tentativas esgotadas"):
        cliente.graphql("query { x }")


def test_em_cache(monkeypatch, tmp_path):
    resposta = Resposta(200, {"total_count": 1}, _cabecalhos(recurso="core"))
    cliente, _ = _cliente(monkeypatch, [resposta], cache_dir=str(tmp_path))
    assert not cliente.em_cache("/repos/a/b/compare/x...y", {"page": 1})
    cliente.get("/repos/a/b/compare/x...y", {"page": 1})
    assert cliente.em_cache("/repos/a/b/compare/x...y", {"page": 1})
    sem_cache, _ = _cliente(monkeypatch, [], cache_dir=None)
    assert not sem_cache.em_cache("/repos/a/b/compare/x...y", {"page": 1})
