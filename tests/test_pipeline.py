import datetime as dt
import time

import pytest

from pipeline import busca, config, funil, metadados, selecao, store
from pipeline.cache import CacheRespostas, grupo, rotulo
from pipeline.cliente import ClienteGitHub, RespostaCache, ultima_pagina

JANELA_INICIO = dt.date(2025, 10, 2)
JANELA_FIM = dt.date(2026, 10, 2)

YAML_MINIMO = """
janela:
  inicio: "2025-10-02"
  fim: "2026-10-02"
alvo_qualificados: 100
ordem_varredura: estrelas_desc
busca:
  estrelas_min: 1000
  faixas:
    - [1000, 1999]
    - [2000, null]
  pre_filtros:
    fork: false
    archived: false
    pushed_apos_inicio: true
filtros:
  releases_min: 5
  runs_min: 50
"""


class ConfigFake:
    janela_inicio = JANELA_INICIO
    janela_fim = JANELA_FIM
    estrelas_min = 1000
    pre_filtros = {"fork": False, "archived": False, "pushed_apos_inicio": True}
    faixas_iniciais = [(1000, 1999), (2000, None)]
    max_resultados_por_faixa = 1000
    max_paginas_por_faixa = 30
    per_page_busca = 100
    releases_min = 5
    runs_min = 50

    @property
    def janela_runs(self):
        return "2025-10-02..2026-10-02"

    def fingerprint(self):
        return {
            "janela_inicio": self.janela_inicio.isoformat(),
            "janela_fim": self.janela_fim.isoformat(),
            "estrelas_min": self.estrelas_min,
            "pre_filtros": self.pre_filtros,
            "faixas": [[a, b] for a, b in self.faixas_iniciais],
            "releases_min": self.releases_min,
            "runs_min": self.runs_min,
        }


def test_consulta_total_inclui_prefiltros():
    consulta = busca.consulta_total(ConfigFake())
    assert consulta == (
        "stars:>=1000 fork:false archived:false pushed:>=2025-10-02"
    )


def test_consulta_faixa_usa_intervalo_fechado():
    consulta = busca.consulta_faixa(ConfigFake(), (1000, 1999))
    assert consulta.startswith("stars:1000..1999 ")
    aberta = busca.consulta_faixa(ConfigFake(), (50000, None))
    assert aberta.startswith("stars:>=50000 ")


def test_dividir_faixa_sem_sobreposicao():
    partes = busca.dividir_faixa((1000, 1999))
    assert partes == [(1000, 1499), (1500, 1999)]
    aberta = busca.dividir_faixa((50000, None))
    assert aberta == [(50000, 100000), (100001, None)]


def test_dividir_faixa_unica_nao_divide():
    assert busca.dividir_faixa((7, 7)) is None


def test_para_candidato_extrai_metadados():
    item = {
        "full_name": "org/repo",
        "html_url": "https://github.com/org/repo",
        "stargazers_count": 4321,
        "language": "Python",
        "created_at": "2018-05-06T00:00:00Z",
        "default_branch": "main",
    }
    candidato = busca.para_candidato(item, (2000, 4999))
    assert candidato["stars"] == 4321
    assert candidato["linguagem"] == "Python"
    assert candidato["faixa_estrelas"] == "2000..4999"
    assert candidato["default_branch"] == "main"


def test_releases_descarta_draft_prerelease_e_fora_da_janela():
    itens = [
        {"draft": False, "prerelease": False, "published_at": "2025-11-10T10:00:00Z"},
        {"draft": True, "prerelease": False, "published_at": "2025-11-11T10:00:00Z"},
        {"draft": False, "prerelease": True, "published_at": "2025-11-12T10:00:00Z"},
        {"draft": False, "prerelease": False, "published_at": "2025-09-30T10:00:00Z"},
        {"draft": False, "prerelease": False, "published_at": "2026-10-03T10:00:00Z"},
        {"draft": False, "prerelease": False, "published_at": None},
        {"draft": False, "prerelease": False, "published_at": "2026-10-02T23:59:59Z"},
    ]
    total = selecao.releases_na_janela(itens, JANELA_INICIO, JANELA_FIM)
    assert total == 2


def test_qualifica_bordas():
    assert selecao.qualifica(1, 50, 5, 50, 5)
    assert not selecao.qualifica(0, 500, 500, 50, 5)
    assert not selecao.qualifica(30, 49, 5, 50, 5)
    assert not selecao.qualifica(30, 50, 4, 50, 5)


def test_idade_anos():
    idade = metadados.idade_anos("2020-10-02T00:00:00Z", JANELA_FIM)
    assert idade == 6.0
    assert metadados.idade_anos("2026-10-02T00:00:00Z", JANELA_FIM) == 0.0


def test_ultima_pagina_do_link():
    header = (
        '<https://api.github.com/repositories/1/contributors?per_page=1&page=2>; '
        'rel="next", '
        '<https://api.github.com/repositories/1/contributors?per_page=1&page=908>; '
        'rel="last"'
    )
    assert ultima_pagina(header) == 908
    assert ultima_pagina(None) is None
    assert ultima_pagina('<https://api.github.com/x?page=2>; rel="next"') is None


def test_quartis_com_empates_no_grupo_inferior():
    valores = [10, 20, 30, 40, 50, 60, 70, 80]
    limites, rotulos = metadados.quartis(valores)
    assert limites["q1"] == 27.5
    assert limites["q2"] == 45.0
    assert limites["q3"] == 62.5
    assert rotulos == [1, 1, 2, 2, 3, 3, 4, 4]


def test_quartis_valores_repetidos():
    limites, rotulos = metadados.quartis([5, 5, 5, 5])
    assert limites == {"q1": 5.0, "q2": 5.0, "q3": 5.0}
    assert rotulos == [1, 1, 1, 1]


def test_quartis_vazio():
    limites, rotulos = metadados.quartis([])
    assert limites["q1"] is None
    assert rotulos == []


def test_funil_contagem_e_motivos():
    linhas = funil.montar_tabela(
        identificados=4000,
        escaneados=412,
        passaram_workflows=300,
        passaram_runs=180,
        qualificados=100,
        amostra=100,
        alvo=100,
    )
    assert linhas[0]["saida"] == 4000
    assert linhas[1]["descartados"] == 4000 - 412
    assert linhas[2]["descartados"] == 412 - 300
    assert linhas[3]["descartados"] == 300 - 180
    assert linhas[4]["descartados"] == 180 - 100
    assert linhas[5]["saida"] == 100
    assert "parcial" in linhas[1]["motivo"]


def test_funil_varredura_completa():
    linhas = funil.montar_tabela(
        identificados=100,
        escaneados=100,
        passaram_workflows=80,
        passaram_runs=60,
        qualificados=40,
        amostra=40,
        alvo=100,
    )
    assert linhas[1]["descartados"] == 0
    assert "completa" in linhas[1]["motivo"]


def test_carregar_config(tmp_path):
    caminho = tmp_path / "config.yaml"
    caminho.write_text(YAML_MINIMO, encoding="utf-8")
    cfg = config.carregar(str(caminho))
    assert cfg.janela_inicio == JANELA_INICIO
    assert cfg.janela_fim == JANELA_FIM
    assert cfg.faixas_iniciais == [(1000, 1999), (2000, None)]
    assert cfg.janela_runs == "2025-10-02..2026-10-02"
    assert cfg.alvo_qualificados == 100
    assert cfg.limite_candidatos == 0
    assert cfg.fingerprint()["releases_min"] == 5


def test_carregar_config_chave_faltando(tmp_path):
    caminho = tmp_path / "config.yaml"
    caminho.write_text("janela: {}\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        config.carregar(str(caminho))


def test_store_roundtrip_e_mapa(tmp_path):
    dir_ck = str(tmp_path)
    cfg = ConfigFake()
    store.preparar(dir_ck, cfg)
    store.anexar(dir_ck, "e1.jsonl", {"full_name": "a/b", "workflows": 3})
    store.anexar(dir_ck, "e1.jsonl", {"full_name": "c/d", "workflows": 0})
    itens = store.ler(dir_ck, "e1.jsonl")
    assert len(itens) == 2
    assert store.mapa(dir_ck, "e1.jsonl")["c/d"]["workflows"] == 0
    store.preparar(dir_ck, cfg)
    assert len(store.ler(dir_ck, "e1.jsonl")) == 2


def test_store_rejeita_outra_config(tmp_path):
    dir_ck = str(tmp_path)
    store.preparar(dir_ck, ConfigFake())

    class Outra(ConfigFake):
        releases_min = 10

    with pytest.raises(SystemExit):
        store.preparar(dir_ck, Outra())


def test_store_reiniciar_apaga_checkpoints(tmp_path):
    dir_ck = str(tmp_path)
    cfg = ConfigFake()
    store.preparar(dir_ck, cfg)
    store.anexar(dir_ck, "e1.jsonl", {"full_name": "a/b"})
    store.preparar(dir_ck, cfg, reiniciar=True)
    assert store.ler(dir_ck, "e1.jsonl") == []


class RespostaFalsa:
    def __init__(self, status_code=200, dados=None, headers=None, texto=""):
        self.status_code = status_code
        self._dados = dados
        self.headers = headers or {}
        self.text = texto

    def json(self):
        if self._dados is None:
            raise ValueError("resposta sem json")
        return self._dados


class SessaoFalsa:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = 0

    def get(self, url, params=None, timeout=None):
        self.chamadas += 1
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def _cabecalhos_core(remaining="4999", reset="9999999999"):
    return {
        "X-RateLimit-Resource": "core",
        "X-RateLimit-Remaining": remaining,
        "X-RateLimit-Reset": reset,
    }


def cliente_fake(monkeypatch, respostas, cache_dir=None, **kwargs):
    sleeps = []
    monkeypatch.setattr("pipeline.cliente.time.sleep", lambda s: sleeps.append(s))
    cliente = ClienteGitHub(token="x", cache_dir=cache_dir, **kwargs)
    cliente.sessao = SessaoFalsa(respostas)
    return cliente, sleeps


def test_cache_evita_requisicoes_repetidas(monkeypatch, tmp_path):
    resposta = RespostaFalsa(200, {"total_count": 3}, _cabecalhos_core())
    cliente, _ = cliente_fake(monkeypatch, [resposta], cache_dir=str(tmp_path))
    caminho = "/repos/a/b/actions/workflows"
    primeira = cliente.get(caminho, {"per_page": 1})
    segunda = cliente.get(caminho, {"per_page": 1})
    assert primeira.json()["total_count"] == 3
    assert segunda.json()["total_count"] == 3
    assert cliente.chamadas == 1


def test_cache_retomada_entre_execucoes(monkeypatch, tmp_path):
    primeira = RespostaFalsa(200, {"total_count": 7}, _cabecalhos_core())
    cliente1, _ = cliente_fake(monkeypatch, [primeira], cache_dir=str(tmp_path))
    cliente1.get("/repos/a/b/actions/workflows", {"per_page": 1})
    nova = RespostaFalsa(200, {"total_count": 999}, _cabecalhos_core())
    cliente2, _ = cliente_fake(monkeypatch, [nova], cache_dir=str(tmp_path))
    resposta = cliente2.get("/repos/a/b/actions/workflows", {"per_page": 1})
    assert resposta.json()["total_count"] == 7
    assert cliente2.chamadas == 0


def test_cache_chaves_diferentes_por_parametro(monkeypatch, tmp_path):
    respostas = [
        RespostaFalsa(200, {"total_count": 1}, _cabecalhos_core()),
        RespostaFalsa(200, {"total_count": 2}, _cabecalhos_core()),
    ]
    cliente, _ = cliente_fake(monkeypatch, respostas, cache_dir=str(tmp_path))
    cliente.get("/repos/a/b/releases", {"per_page": 1})
    cliente.get("/repos/a/b/releases", {"per_page": 2})
    assert cliente.chamadas == 2


def test_cache_preserva_cabecalho_link(monkeypatch, tmp_path):
    link = '<https://api.github.com/repositories/1/contributors?page=908>; rel="last"'
    cabecalhos = {"Link": link, **_cabecalhos_core()}
    resposta = RespostaFalsa(200, [{"login": "x"}], cabecalhos)
    cliente, _ = cliente_fake(monkeypatch, [resposta], cache_dir=str(tmp_path))
    cliente.get("/repos/a/b/contributors", {"per_page": 1, "anon": "true"})
    em_cache = cliente.get("/repos/a/b/contributors", {"per_page": 1, "anon": "true"})
    assert em_cache.headers.get("Link") == link
    assert ultima_pagina(em_cache.headers.get("Link")) == 908
    assert cliente.chamadas == 1


def test_forcar_ignora_cache(monkeypatch, tmp_path):
    respostas = [
        RespostaFalsa(200, {"total_count": 1}, _cabecalhos_core()),
        RespostaFalsa(200, {"total_count": 2}, _cabecalhos_core()),
    ]
    cliente, _ = cliente_fake(monkeypatch, respostas, cache_dir=str(tmp_path))
    cliente.get("/repos/a/b/releases", {"per_page": 1})
    cliente.get("/repos/a/b/releases", {"per_page": 1}, forcar=True)
    assert cliente.chamadas == 2


def test_backoff_5xx_ate_sucesso(monkeypatch, tmp_path):
    respostas = [
        RespostaFalsa(500, texto="erro"),
        RespostaFalsa(502, texto="erro"),
        RespostaFalsa(200, {"ok": True}, _cabecalhos_core()),
    ]
    cliente, sleeps = cliente_fake(monkeypatch, respostas, cache_dir=None)
    resposta = cliente.get("/repos/a/b/releases")
    assert resposta.status_code == 200
    assert sleeps == [1.0, 2.0]
    assert cliente.chamadas == 3


def test_backoff_5xx_esgotado(monkeypatch, tmp_path):
    respostas = [RespostaFalsa(503, texto="erro") for _ in range(6)]
    cliente, sleeps = cliente_fake(monkeypatch, respostas, cache_dir=None)
    with pytest.raises(RuntimeError):
        cliente.get("/repos/a/b/releases")
    assert sleeps == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0]
    assert cliente.chamadas == 6


def test_pausa_por_cota_no_403(monkeypatch, tmp_path):
    reset = int(time.time() + 100)
    respostas = [
        RespostaFalsa(403, headers={"X-RateLimit-Remaining": "0",
                                    "X-RateLimit-Reset": str(reset),
                                    "X-RateLimit-Resource": "core"}),
        RespostaFalsa(200, {"ok": True}, _cabecalhos_core()),
    ]
    cliente, sleeps = cliente_fake(monkeypatch, respostas, cache_dir=None)
    resposta = cliente.get("/repos/a/b/releases")
    assert resposta.status_code == 200
    assert 99 <= sleeps[0] <= 102
    assert cliente.chamadas == 2


def test_pausa_preventiva_antes_da_proxima_requisicao(monkeypatch, tmp_path):
    reset = int(time.time() + 50)
    cabecalhos = _cabecalhos_core(remaining="0", reset=str(reset))
    respostas = [
        RespostaFalsa(200, {"ok": 1}, cabecalhos),
        RespostaFalsa(200, {"ok": 2}, _cabecalhos_core()),
    ]
    cliente, sleeps = cliente_fake(monkeypatch, respostas, cache_dir=None)
    cliente.get("/repos/a/b/releases")
    cliente.get("/repos/a/b/workflows")
    assert len(sleeps) == 1
    assert 49 < sleeps[0] < 52
    assert cliente.chamadas == 2


def test_reduzir_guarda_so_o_resumo_no_cache(monkeypatch, tmp_path):
    resposta = RespostaFalsa(
        200, {"total_count": 1, "pesado": "x" * 1000}, _cabecalhos_core()
    )
    cliente, _ = cliente_fake(monkeypatch, [resposta], cache_dir=str(tmp_path))
    reduzir = lambda dados: {"total_count": dados["total_count"]}
    primeira = cliente.get("/repos/a/b/actions/runs", {"page": 1}, reduzir=reduzir)
    segunda = cliente.get("/repos/a/b/actions/runs", {"page": 1}, reduzir=reduzir)
    assert primeira.json() == {"total_count": 1}
    assert segunda.json() == {"total_count": 1}
    assert cliente.chamadas == 1


def test_reduzir_sem_cache(monkeypatch):
    resposta = RespostaFalsa(200, {"a": 1, "b": 2}, _cabecalhos_core())
    cliente, _ = cliente_fake(monkeypatch, [resposta], cache_dir=None)
    obtida = cliente.get("/repos/a/b/x", reduzir=lambda dados: {"a": dados["a"]})
    assert obtida.json() == {"a": 1}


def test_cache_rotulo_longo_e_cortado(tmp_path):
    cache = CacheRespostas(str(tmp_path))
    url = "https://api.github.com/repos/a/b/compare/" + "t" * 200 + "..." + "u" * 200
    caminho = cache._caminho(cache.grupo(url), url, "abc")
    assert len(caminho.split("repos__a__b")[1]) < 90


def test_cache_chave_canonica(tmp_path):
    cache = CacheRespostas(str(tmp_path))
    url = "https://api.github.com/search/repositories"
    assert cache.chave(url, {"b": 2, "a": 1}) == cache.chave(url, {"a": 1, "b": 2})
    assert cache.chave(url, {"a": 1}) != cache.chave(url, {"a": 2})


def test_cache_grupo_e_rotulo():
    assert grupo("https://api.github.com/repos/a/b/releases") == "repos__a__b"
    assert rotulo("https://api.github.com/repos/a/b/actions/runs") == "actions__runs"
    assert grupo("https://api.github.com/search/repositories") == "search"


def test_resposta_cache_serializa_texto():
    resposta = RespostaCache({"status_code": 200, "headers": {}, "dados": '{"x": 1}'})
    assert resposta.json() == {"x": 1}
    assert resposta.status_code == 200


def test_substituir_tenta_de_novo_se_o_arquivo_estiver_preso(monkeypatch, tmp_path):
    from pipeline import cache as modulo_cache

    origem = tmp_path / "a.tmp"
    origem.write_text("x", encoding="utf-8")
    destino = tmp_path / "a.json"
    falhas = []
    replace_real = modulo_cache.os.replace

    def replace_instavel(a, b):
        if len(falhas) < 2:
            falhas.append(1)
            raise PermissionError("WinError 32")
        replace_real(a, b)

    monkeypatch.setattr(modulo_cache.os, "replace", replace_instavel)
    monkeypatch.setattr(modulo_cache.time, "sleep", lambda s: None)
    modulo_cache.substituir(str(origem), str(destino))
    assert destino.read_text(encoding="utf-8") == "x"
    assert len(falhas) == 2


def test_substituir_desiste_depois_das_tentativas(monkeypatch, tmp_path):
    from pipeline import cache as modulo_cache

    def sempre_preso(a, b):
        raise PermissionError("WinError 32")

    monkeypatch.setattr(modulo_cache.os, "replace", sempre_preso)
    monkeypatch.setattr(modulo_cache.time, "sleep", lambda s: None)
    with pytest.raises(PermissionError):
        modulo_cache.substituir("a", "b", tentativas=3)
