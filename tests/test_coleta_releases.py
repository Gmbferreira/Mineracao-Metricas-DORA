import datetime as dt

from pipeline import releases as coleta
from tests.falsos import ClienteFalso, RespostaFalsa

INICIO = dt.date(2025, 10, 2)
FIM = dt.date(2026, 10, 2)


def _release(tag, publicada, draft=False, pre=False):
    return {
        "id": hash(tag),
        "tag_name": tag,
        "name": tag,
        "draft": draft,
        "prerelease": pre,
        "created_at": publicada,
        "published_at": publicada,
        "html_url": f"https://github.com/o/r/releases/tag/{tag}",
        "body": "notas longas que nao vao para o cache",
    }


def _compare(datas, total=None):
    return {
        "status": "ahead",
        "ahead_by": len(datas),
        "behind_by": 0,
        "total_commits": len(datas) if total is None else total,
        "files": [{"patch": "x" * 1000}],
        "commits": [
            {
                "sha": f"s{i}",
                "commit": {
                    "author": {"date": data},
                    "committer": {"date": data},
                    "message": f"fix: item {i}\n\ncorpo",
                },
            }
            for i, data in enumerate(datas)
        ],
    }


def test_reduzir_releases_mantem_so_campos_usados():
    reduzidas = coleta.reduzir_releases([_release("v1", "2026-01-01T00:00:00Z")])
    assert "body" not in reduzidas[0]
    assert reduzidas[0]["tag_name"] == "v1"
    assert coleta.reduzir_releases({"message": "x"}) == {"message": "x"}


def test_reduzir_compare_tira_arquivos_e_corpo_da_mensagem():
    reduzido = coleta.reduzir_compare(_compare(["2026-01-01T00:00:00Z"]))
    assert "files" not in reduzido
    assert reduzido["commits"][0]["commit"]["message"] == "fix: item 0"
    assert coleta.reduzir_compare("texto") == "texto"


def test_buscar_releases_pagina_ate_passar_do_inicio():
    pagina1 = [_release(f"v{i}", f"2026-0{i}-01T00:00:00Z") for i in range(9, 7, -1)]
    pagina2 = [_release("v7", "2026-07-01T00:00:00Z"), _release("v0", "2025-01-01T00:00:00Z")]
    pagina3 = [_release("vX", "2024-01-01T00:00:00Z")] * 2
    cliente = ClienteFalso({
        ("/repos/o/r/releases", 1): RespostaFalsa(200, pagina1),
        ("/repos/o/r/releases", 2): RespostaFalsa(200, pagina2),
        ("/repos/o/r/releases", 3): RespostaFalsa(200, pagina3),
    })
    releases = coleta.buscar_releases(cliente, "o/r", INICIO, per_page=2)
    assert [r["tag_name"] for r in releases] == ["v9", "v8", "v7", "v0"]
    assert len(cliente.chamadas) == 2


def test_buscar_releases_continua_se_anterior_e_pre_release():
    pagina1 = [_release("v2", "2026-02-01T00:00:00Z"),
               _release("v1-rc", "2025-01-01T00:00:00Z", pre=True)]
    pagina2 = [_release("v1", "2024-12-01T00:00:00Z")]
    cliente = ClienteFalso({
        ("/repos/o/r/releases", 1): RespostaFalsa(200, pagina1),
        ("/repos/o/r/releases", 2): RespostaFalsa(200, pagina2),
    })
    releases = coleta.buscar_releases(cliente, "o/r", INICIO, per_page=2)
    assert [r["tag_name"] for r in releases] == ["v2", "v1-rc", "v1"]


def test_buscar_releases_repositorio_inacessivel():
    cliente = ClienteFalso({"/repos/o/r/releases": RespostaFalsa(404, {})})
    assert coleta.buscar_releases(cliente, "o/r", INICIO) == []


def test_montar_pares_usa_anterior_mesmo_fora_da_janela():
    releases = [
        _release("v3", "2026-03-01T00:00:00Z"),
        _release("v2-draft", "2026-02-15T00:00:00Z", draft=True),
        _release("v2", "2026-02-01T00:00:00Z"),
        _release("v2-rc", "2026-01-20T00:00:00Z", pre=True),
        _release("v1", "2025-05-01T00:00:00Z"),
        _release("v4", "2026-11-01T00:00:00Z"),
    ]
    pares = coleta.montar_pares(releases, INICIO, FIM)
    assert [(a["tag_name"], r["tag_name"]) for a, r in pares] == [("v1", "v2"), ("v2", "v3")]
    com_pre = coleta.montar_pares(releases, INICIO, FIM, incluir_pre=True)
    assert [(a["tag_name"], r["tag_name"]) for a, r in com_pre] == [
        ("v1", "v2-rc"), ("v2-rc", "v2"), ("v2", "v3")
    ]


def test_montar_pares_primeira_release_da_historia_sem_anterior():
    pares = coleta.montar_pares([_release("v1", "2026-01-01T00:00:00Z")], INICIO, FIM)
    assert pares[0][0] is None


def test_buscar_commits_pagina_e_codifica_tags():
    caminho = "/repos/o/r/compare/pkg%2Fv1...pkg%2Fv2"
    datas = [f"2026-01-0{i}T00:00:00Z" for i in range(1, 4)]
    cliente = ClienteFalso({
        (caminho, 1): RespostaFalsa(200, _compare(datas[:2], total=3)),
        (caminho, 2): RespostaFalsa(200, _compare(datas[2:], total=3)),
    })
    resultado = coleta.buscar_commits(cliente, "o/r", "pkg/v1", "pkg/v2", per_page=2)
    assert resultado["status"] == "ok"
    assert [c["data_autor"] for c in resultado["commits"]] == datas
    assert resultado["commits"][0]["mensagem"] == "fix: item 0"
    assert not resultado["truncado"]


def test_buscar_commits_marca_truncado_no_limite_de_paginas():
    caminho = "/repos/o/r/compare/v1...v2"
    datas = ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"]
    cliente = ClienteFalso({caminho: RespostaFalsa(200, _compare(datas, total=10))})
    resultado = coleta.buscar_commits(cliente, "o/r", "v1", "v2", per_page=2, max_paginas=2)
    assert len(resultado["commits"]) == 4
    assert resultado["truncado"]


def test_buscar_commits_tag_apagada_devolve_404():
    cliente = ClienteFalso({"/repos/o/r/compare/v1...v2": RespostaFalsa(404, {})})
    resultado = coleta.buscar_commits(cliente, "o/r", "v1", "v2")
    assert resultado["status"] == "404"
    assert resultado["commits"] == []


def test_buscar_commits_erro_persistente_nao_derruba_a_coleta():
    cliente = ClienteFalso({"/repos/o/r/compare/v1...v2": RuntimeError("HTTP 502")})
    resultado = coleta.buscar_commits(cliente, "o/r", "v1", "v2")
    assert resultado["status"] == "erro"


def test_coletar_releases_monta_lista_avaliada():
    releases = [
        _release("v2", "2026-03-15T00:00:00Z"),
        _release("v1", "2026-01-01T00:00:00Z"),
    ]
    cliente = ClienteFalso({
        "/repos/o/r/releases": RespostaFalsa(200, releases),
        "/repos/o/r/compare/v1...v2": RespostaFalsa(
            200, _compare(["2026-03-02T00:00:00Z", "2026-03-14T00:00:00Z"])
        ),
    })
    resultado = coleta.coletar_releases(cliente, "o/r", INICIO, FIM)
    assert len(resultado["releases"]) == 2
    primeira, segunda = resultado["avaliadas"]
    assert primeira["status"] == "sem_anterior"
    assert segunda["tag_anterior"] == "v1"
    assert segunda["total_commits"] == 2
