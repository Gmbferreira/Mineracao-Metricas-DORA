import datetime as dt

import pytest

from pipeline import variantes

INICIO = dt.date(2025, 10, 2)
FIM = dt.date(2026, 10, 2)


def _no_tag(nome, data, anotada=False, tipo="Commit"):
    commit = {"__typename": tipo, "oid": f"sha-{nome}", "committedDate": data}
    if anotada:
        return {"name": nome, "target": {"__typename": "Tag", "target": commit}}
    return {"name": nome, "target": commit}


class ClienteTags:
    def __init__(self, paginas, erro=False):
        self.paginas = paginas
        self.erro = erro
        self.consultas = 0

    def graphql(self, consulta, variaveis=None, repositorio=None):
        self.consultas += 1
        if self.erro:
            return {"errors": [{"message": "boom"}]}
        indice = int(variaveis["depois"] or 0)
        return {"data": {"repository": {"refs": {
            "pageInfo": {"hasNextPage": indice + 1 < len(self.paginas), "endCursor": str(indice + 1)},
            "nodes": self.paginas[indice],
        }}}}


def test_buscar_tags_le_tags_leves_e_anotadas_e_para_no_inicio_da_janela():
    cliente = ClienteTags([
        [_no_tag("v3", "2026-05-01T00:00:00Z"), _no_tag("v2", "2026-01-01T00:00:00Z", anotada=True),
         _no_tag("arvore", "2026-01-01T00:00:00Z", tipo="Tree")],
        [_no_tag("v1", "2025-06-01T00:00:00Z")],
        [_no_tag("v0", "2024-01-01T00:00:00Z")],
    ])
    tags = variantes.buscar_tags(cliente, "o/r", INICIO)
    assert [t["tag_name"] for t in tags] == ["v3", "v2", "v1"]
    assert tags[1]["sha"] == "sha-v2"
    assert tags[1]["published_at"] == "2026-01-01T00:00:00Z"
    assert cliente.consultas == 2


def test_buscar_tags_com_erro():
    with pytest.raises(RuntimeError, match="tags de o/r"):
        variantes.buscar_tags(ClienteTags([[]], erro=True), "o/r", INICIO)


def test_pares_de_tags_usa_a_anterior_mesmo_fora_da_janela():
    tags = [{"tag_name": "v2", "published_at": "2026-02-01T00:00:00Z"},
            {"tag_name": "v1", "published_at": "2025-06-01T00:00:00Z"},
            {"tag_name": "v3", "published_at": "2026-11-01T00:00:00Z"},
            {"tag_name": "b", "published_at": "2026-03-01T00:00:00Z"},
            {"tag_name": "a", "published_at": "2026-03-01T00:00:00Z"}]
    pares = variantes.pares_de_tags(tags, INICIO, FIM)
    assert [(a["tag_name"] if a else None, t["tag_name"]) for a, t in pares] == [
        ("v1", "v2"), ("v2", "a"), ("a", "b")]
    so_uma = variantes.pares_de_tags([{"tag_name": "v1", "published_at": "2026-01-01T00:00:00Z"}],
                                     INICIO, FIM)
    assert so_uma[0][0] is None


def test_consulta_de_lote_tem_um_alias_por_compare():
    consulta = variantes._consulta_de_lote(3)
    assert consulta.count("compare(headRef:") == 3
    assert "$b2: String!, $h2: String!" in consulta
    assert "c2: ref(qualifiedName: $b2)" in consulta


class ClienteCompares:
    """Responde aos lotes de compare; `compares` mapeia (base, head) -> datas."""

    def __init__(self, compares, falhar_lote_maior_que=None, grandes=(), apagadas=()):
        self.compares = compares
        self.falhar = falhar_lote_maior_que
        self.grandes = set(grandes)
        self.apagadas = set(apagadas)
        self.lotes = []

    def graphql(self, consulta, variaveis=None, repositorio=None):
        quantidade = consulta.count("compare(headRef:")
        self.lotes.append(quantidade)
        if self.falhar is not None and quantidade > self.falhar:
            raise RuntimeError("timeout")
        repo = {}
        for i in range(quantidade):
            par = (variaveis[f"b{i}"].removeprefix("refs/tags/"),
                   variaveis[f"h{i}"].removeprefix("refs/tags/"))
            if par in self.apagadas:
                repo[f"c{i}"] = None
                continue
            datas = self.compares[par]
            repo[f"c{i}"] = {"compare": {"commits": {
                "totalCount": len(datas),
                "pageInfo": {"hasNextPage": par in self.grandes},
                "nodes": [{"oid": f"{par[1]}-{k}", "authoredDate": d} for k, d in enumerate(datas)],
            }}}
        return {"data": {"repository": repo}}


@pytest.fixture
def sozinho(monkeypatch):
    chamados = []

    def falso(cliente, nome, base, head):
        chamados.append((base, head))
        if base == "apagada":
            return {"status": "404", "total_commits": None, "commits": [], "truncado": False}
        return {"status": "ok", "total_commits": 1, "truncado": False,
                "commits": [{"sha": "x", "data_autor": "2026-01-01T00:00:00Z", "mensagem": "m"}]}

    monkeypatch.setattr(variantes.releases, "buscar_commits", falso)
    return chamados


def test_commits_em_lote_numa_consulta(sozinho):
    compares = {("v1", "v2"): ["2026-01-01T00:00:00Z"], ("v2", "v3"): []}
    cliente = ClienteCompares(compares)
    resultado = variantes.commits_em_lote(cliente, "o/r", list(compares))
    assert cliente.lotes == [2]
    assert resultado[("v1", "v2")] == {"status": "ok", "total_commits": 1, "truncado": False,
                                       "commits": [{"sha": "v2-0", "data_autor": "2026-01-01T00:00:00Z"}]}
    assert resultado[("v2", "v3")]["total_commits"] == 0
    assert sozinho == []


def test_lote_que_falha_e_dividido(sozinho):
    compares = {(f"v{i}", f"v{i + 1}"): ["2026-01-01T00:00:00Z"] for i in range(4)}
    cliente = ClienteCompares(compares, falhar_lote_maior_que=2)
    resultado = variantes.commits_em_lote(cliente, "o/r", list(compares), tamanho=4)
    assert sorted(cliente.lotes) == [2, 2, 4]
    assert all(r["status"] == "ok" for r in resultado.values())
    assert sozinho == []


def test_compare_grande_tag_apagada_e_lote_unitario_falho_vao_pelo_caminho_normal(sozinho):
    compares = {("v1", "v2"): ["2026-01-01T00:00:00Z"], ("v2", "v3"): ["2026-01-02T00:00:00Z"]}
    cliente = ClienteCompares(compares, grandes=[("v2", "v3")], apagadas=[("apagada", "v4")])
    resultado = variantes.commits_em_lote(cliente, "o/r", [("v1", "v2"), ("v2", "v3"), ("apagada", "v4")])
    assert sozinho == [("v2", "v3"), ("apagada", "v4")]
    assert resultado[("apagada", "v4")]["status"] == "404"
    assert resultado[("v2", "v3")]["commits"] == [{"sha": "x", "data_autor": "2026-01-01T00:00:00Z"}]
    sozinho.clear()
    unitario = ClienteCompares(compares, falhar_lote_maior_que=0)
    variantes.commits_em_lote(unitario, "o/r", [("v1", "v2")])
    assert sozinho == [("v1", "v2")]


class ClienteVariantes(ClienteCompares):
    """Responde a tags, compares em lote e release notes."""

    def __init__(self, tags, compares, notas):
        super().__init__(compares)
        self.tags = tags
        self.notas = notas

    def graphql(self, consulta, variaveis=None, repositorio=None):
        if "refs(" in consulta:
            return {"data": {"repository": {"refs": {
                "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": self.tags}}}}
        if "releases(" in consulta:
            return {"data": {"repository": {"releases": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [{"tagName": t, "createdAt": "2026-01-01T00:00:00Z", "description": d}
                          for t, d in self.notas.items()]}}}}
        return super().graphql(consulta, variaveis, repositorio)


def test_coletar_variantes_reaproveita_pares_ja_coletados(sozinho):
    def release(tag, data, pre=False):
        return {"tag_name": tag, "draft": False, "prerelease": pre, "published_at": data}

    dados = {
        "releases": [release("v1.0.0", "2025-09-01T00:00:00Z"), release("v1.1.0-rc", "2026-01-01T00:00:00Z", True),
                     release("v1.1.0", "2026-02-01T00:00:00Z")],
        "avaliadas": [{"tag_name": "v1.1.0", "tag_anterior": "v1.0.0", "published_at": "2026-02-01T00:00:00Z",
                       "status": "ok", "total_commits": 1, "truncado": False,
                       "commits": [{"sha": "s", "data_autor": "2026-01-20T00:00:00Z", "mensagem": "m"}]}],
        "notas": {"v1.1.0": "Bug fixes"},
    }
    tags = [_no_tag("v1.1.0", "2026-02-01T00:00:00Z"), _no_tag("v1.1.0-rc", "2026-01-01T00:00:00Z"),
            _no_tag("v1.0.0", "2025-09-01T00:00:00Z"), _no_tag("depois", "2026-12-01T00:00:00Z")]
    compares = {("v1.0.0", "v1.1.0-rc"): ["2025-12-01T00:00:00Z"],
                ("v1.1.0-rc", "v1.1.0"): ["2026-01-15T00:00:00Z"]}
    cliente = ClienteVariantes(tags, compares, {"v1.1.0-rc": "Release candidate"})
    resultado = variantes.coletar_variantes(cliente, "o/r", INICIO, FIM, dados)

    pre = resultado["release_pre"]["avaliadas"]
    assert [(i["tag_anterior"], i["tag_name"]) for i in pre] == [
        ("v1.0.0", "v1.1.0-rc"), ("v1.1.0-rc", "v1.1.0")]
    assert pre[0]["commits"] == [{"sha": "v1.1.0-rc-0", "data_autor": "2025-12-01T00:00:00Z"}]
    tag = resultado["tag"]
    assert [t["tag_name"] for t in tag["tags"]] == ["v1.1.0", "v1.1.0-rc", "v1.0.0"]
    assert [i["tag_name"] for i in tag["avaliadas"]] == ["v1.1.0-rc", "v1.1.0"]
    assert resultado["notas"] == {"v1.1.0-rc": "Release candidate"}
    assert cliente.lotes == [2]
    assert sozinho == []


def test_coletar_variantes_sem_pre_releases_nao_busca_notas(sozinho):
    dados = {
        "releases": [{"tag_name": "v1", "draft": False, "prerelease": False,
                      "published_at": "2026-01-01T00:00:00Z"}],
        "avaliadas": [],
        "notas": {"v1": ""},
    }
    cliente = ClienteVariantes([_no_tag("v1", "2026-01-01T00:00:00Z")], {}, {})
    resultado = variantes.coletar_variantes(cliente, "o/r", INICIO, FIM, dados)
    assert resultado["release_pre"]["avaliadas"][0]["status"] == "sem_anterior"
    assert resultado["tag"]["avaliadas"][0]["status"] == "sem_anterior"
    assert resultado["notas"] == {}
