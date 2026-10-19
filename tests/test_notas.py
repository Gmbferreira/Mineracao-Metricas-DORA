import datetime as dt

import pytest

from pipeline import notas

INICIO = dt.date(2025, 10, 2)


class ClienteNotas:
    """Responde a consulta de releases em paginas, como a GraphQL."""

    def __init__(self, paginas, erro=None, sem_repositorio=False):
        self.paginas = paginas
        self.erro = erro
        self.sem_repositorio = sem_repositorio
        self.consultas = []

    def graphql(self, consulta, variaveis=None, repositorio=None):
        self.consultas.append(dict(variaveis))
        if self.erro:
            return {"errors": [{"message": self.erro}]}
        if self.sem_repositorio:
            return {"data": {"repository": None}}
        indice = int(variaveis["depois"] or 0)
        return {"data": {"repository": {"releases": {
            "pageInfo": {"hasNextPage": indice + 1 < len(self.paginas),
                         "endCursor": str(indice + 1)},
            "nodes": self.paginas[indice],
        }}}}


def _no(tag, criada, descricao="notas"):
    return {"tagName": tag, "createdAt": criada, "description": descricao}


def test_coleta_as_notas_das_tags_pedidas():
    cliente = ClienteNotas([[_no("v2", "2026-05-01T00:00:00Z", "Bug fixes"),
                             _no("v1", "2026-04-01T00:00:00Z", None),
                             _no("outra", "2026-03-01T00:00:00Z")]])
    resultado = notas.coletar_notas(cliente, "o/r", INICIO, ["v1", "v2"])
    assert resultado == {"v2": "Bug fixes", "v1": ""}
    assert cliente.consultas[0]["dono"] == "o" and cliente.consultas[0]["nome"] == "r"


def test_para_quando_ja_achou_todas_as_tags():
    cliente = ClienteNotas([[_no("v2", "2026-05-01T00:00:00Z")],
                            [_no("v1", "2026-04-01T00:00:00Z")],
                            [_no("v0", "2026-03-01T00:00:00Z")]])
    notas.coletar_notas(cliente, "o/r", INICIO, ["v2", "v1"])
    assert len(cliente.consultas) == 2


def test_para_quando_passa_do_inicio_da_janela():
    cliente = ClienteNotas([[_no("v2", "2026-05-01T00:00:00Z")],
                            [_no("antiga", "2025-01-01T00:00:00Z")],
                            [_no("v-sumida", "2024-01-01T00:00:00Z")]])
    resultado = notas.coletar_notas(cliente, "o/r", INICIO, ["v2", "tag-apagada"])
    assert resultado == {"v2": "notas"}
    assert len(cliente.consultas) == 2


def test_sem_tags_nao_consulta():
    cliente = ClienteNotas([[]])
    assert notas.coletar_notas(cliente, "o/r", INICIO, []) == {}
    assert cliente.consultas == []


def test_erro_ou_repositorio_sumido_vira_runtime_error():
    with pytest.raises(RuntimeError, match="release notes"):
        notas.coletar_notas(ClienteNotas([], erro="boom"), "o/r", INICIO, ["v1"])
    with pytest.raises(RuntimeError):
        notas.coletar_notas(ClienteNotas([], sem_repositorio=True), "o/r", INICIO, ["v1"])
