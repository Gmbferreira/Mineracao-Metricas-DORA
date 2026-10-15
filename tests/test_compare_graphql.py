from pipeline import releases as coleta
from tests.falsos import ClienteFalso, RespostaFalsa


class ClienteComGraphql(ClienteFalso):
    """Cliente falso com GraphQL; `compares` mapeia (base, head) para os commits.

    Como a API, a GraphQL so mostra os `limite` commits mais recentes do compare.
    """

    def __init__(self, rotas, compares=None, limite=1000, por_pagina=2, cache_rest=(),
                 falha=None):
        super().__init__(rotas)
        self.compares = compares or {}
        self.limite = limite
        self.por_pagina = por_pagina
        self.cache_rest = set(cache_rest)
        self.falha = falha
        self.consultas = []

    def em_cache(self, caminho, params=None):
        return caminho in self.cache_rest

    def graphql(self, consulta, variaveis=None, repositorio=None):
        self.consultas.append(dict(variaveis))
        if self.falha == "excecao":
            raise RuntimeError("HTTP 502")
        if self.falha == "erros":
            return {"errors": [{"message": "Something went wrong"}]}
        base = variaveis["base"].removeprefix("refs/tags/")
        head = variaveis["head"].removeprefix("refs/tags/")
        if (base, head) not in self.compares:
            return {"data": {"repository": {"ref": None}}}
        todos = self.compares[(base, head)]
        visiveis = todos[-self.limite:]
        inicio = int(variaveis["depois"] or 0)
        trecho = visiveis[inicio: inicio + self.por_pagina]
        fim = inicio + len(trecho)
        return {"data": {"repository": {"ref": {"compare": {"commits": {
            "totalCount": len(todos),
            "pageInfo": {"hasNextPage": fim < len(visiveis), "endCursor": str(fim)},
            "nodes": trecho,
        }}}}}}


def _no(i):
    return {"oid": f"s{i}", "authoredDate": f"2026-01-0{i}T00:00:00Z",
            "message": f"fix: item {i}\n\ncorpo"}


def _compare_rest(shas, total):
    return {
        "total_commits": total,
        "commits": [
            {"sha": sha, "commit": {"author": {"date": "2026-01-01T00:00:00Z"},
                                    "message": f"commit {sha}"}}
            for sha in shas
        ],
    }


def test_commits_pela_graphql_sem_usar_o_rest():
    cliente = ClienteComGraphql({}, {("v1", "v2"): [_no(i) for i in range(1, 6)]})
    resultado = coleta.buscar_commits(cliente, "o/r", "v1", "v2")
    assert resultado["status"] == "ok"
    assert resultado["total_commits"] == 5
    assert [c["sha"] for c in resultado["commits"]] == ["s1", "s2", "s3", "s4", "s5"]
    assert resultado["commits"][0] == {"sha": "s1", "data_autor": "2026-01-01T00:00:00Z",
                                       "mensagem": "fix: item 1"}
    assert not resultado["truncado"]
    assert cliente.chamadas == []
    assert [c["depois"] for c in cliente.consultas] == [None, "2", "4"]
    assert cliente.consultas[0]["base"] == "refs/tags/v1"
    assert cliente.consultas[0]["dono"] == "o"


def test_graphql_converte_a_data_para_utc():
    nos = [{"oid": "a", "authoredDate": "2026-01-01T02:30:00+02:00", "message": None}]
    cliente = ClienteComGraphql({}, {("v1", "v2"): nos})
    commit = coleta.buscar_commits(cliente, "o/r", "v1", "v2")["commits"][0]
    assert commit == {"sha": "a", "data_autor": "2026-01-01T00:30:00Z", "mensagem": ""}


def test_compare_vazio_pela_graphql():
    cliente = ClienteComGraphql({}, {("v1", "v2"): []})
    resultado = coleta.buscar_commits(cliente, "o/r", "v1", "v2")
    assert resultado == {"status": "ok", "total_commits": 0, "commits": [], "truncado": False}


def test_compare_maior_que_o_limite_completa_com_o_rest():
    # a GraphQL so mostra os 3 mais recentes de 5; os 2 mais antigos vem do REST
    caminho = "/repos/o/r/compare/v1...v2"
    cliente = ClienteComGraphql(
        {(caminho, 1): RespostaFalsa(200, _compare_rest(["s1", "s2"], total=5))},
        {("v1", "v2"): [_no(i) for i in range(1, 6)]},
        limite=3,
    )
    resultado = coleta.buscar_commits(cliente, "o/r", "v1", "v2", per_page=2)
    assert [c["sha"] for c in resultado["commits"]] == ["s1", "s2", "s3", "s4", "s5"]
    assert resultado["total_commits"] == 5
    assert not resultado["truncado"]
    assert [params["page"] for _, params in cliente.chamadas] == [1]


def test_pagina_do_rest_que_encosta_na_graphql_nao_duplica():
    caminho = "/repos/o/r/compare/v1...v2"
    cliente = ClienteComGraphql(
        {(caminho, 1): RespostaFalsa(200, _compare_rest(["s1", "s2", "s3"], total=5))},
        {("v1", "v2"): [_no(i) for i in range(1, 6)]},
        limite=3,
    )
    resultado = coleta.buscar_commits(cliente, "o/r", "v1", "v2", per_page=3)
    assert [c["sha"] for c in resultado["commits"]] == ["s1", "s2", "s3", "s4", "s5"]


def test_compare_gigante_fica_truncado_no_limite_de_paginas_do_rest():
    caminho = "/repos/o/r/compare/v1...v2"
    cliente = ClienteComGraphql(
        {caminho: RespostaFalsa(200, _compare_rest(["s1", "s2"], total=9))},
        {("v1", "v2"): [_no(i) for i in range(1, 10)]},
        limite=3,
        por_pagina=3,
    )
    resultado = coleta.buscar_commits(cliente, "o/r", "v1", "v2", per_page=2, max_paginas=1)
    assert resultado["truncado"]
    assert resultado["total_commits"] == 9
    assert len(resultado["commits"]) == 5


def test_rest_do_compare_maior_com_404_mantem_o_status():
    cliente = ClienteComGraphql(
        {"/repos/o/r/compare/v1...v2": RespostaFalsa(404, {})},
        {("v1", "v2"): [_no(i) for i in range(1, 6)]},
        limite=3,
    )
    assert coleta.buscar_commits(cliente, "o/r", "v1", "v2")["status"] == "404"


def test_tag_apagada_na_graphql_volta_para_o_rest():
    cliente = ClienteComGraphql({"/repos/o/r/compare/v1...v2": RespostaFalsa(404, {})})
    resultado = coleta.buscar_commits(cliente, "o/r", "v1", "v2")
    assert resultado["status"] == "404"
    assert len(cliente.consultas) == 1


def test_erro_na_graphql_volta_para_o_rest():
    for falha in ("erros", "excecao"):
        cliente = ClienteComGraphql(
            {"/repos/o/r/compare/v1...v2": RespostaFalsa(200, _compare_rest(["s1"], total=1))},
            falha=falha,
        )
        resultado = coleta.buscar_commits(cliente, "o/r", "v1", "v2")
        assert resultado["status"] == "ok"
        assert resultado["total_commits"] == 1
        assert len(cliente.chamadas) == 1


def test_compare_que_ja_esta_no_cache_do_rest_nao_vai_para_a_graphql():
    caminho = "/repos/o/r/compare/v1...v2"
    cliente = ClienteComGraphql(
        {caminho: RespostaFalsa(200, _compare_rest(["s1"], total=1))},
        {("v1", "v2"): [_no(1)]},
        cache_rest=[caminho],
    )
    resultado = coleta.buscar_commits(cliente, "o/r", "v1", "v2")
    assert resultado["total_commits"] == 1
    assert cliente.consultas == []
