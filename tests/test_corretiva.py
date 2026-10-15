import datetime as dt

import pytest

from metricas import cfr, corretiva

FIM = dt.date(2026, 10, 2)


def _release(tag, publicada, mensagens=()):
    return {"tag_name": tag, "published_at": publicada, "mensagens": list(mensagens)}


@pytest.fixture
def exemplo_enunciado():
    # secao 5 (RQ 03 b): v2.3.0 seguida de v2.3.1 com correcao falha;
    # v2.4.0 seguida de v2.5.0 nao falha
    return [
        _release("v2.3.0", "2026-05-10T12:00:00Z", ["feat: abrir arquivos grandes"]),
        _release("v2.3.1", "2026-05-12T12:00:00Z", ["fix: crash ao abrir arquivo"]),
        _release("v2.4.0", "2026-06-01T12:00:00Z", ["feat: exportar pdf"]),
        _release("v2.5.0", "2026-06-20T12:00:00Z", ["feat: tema escuro"]),
    ]


@pytest.mark.parametrize("tag, esperado", [
    ("v1.2.3", (1, 2, 3)),
    ("1.2", (1, 2, 0)),
    ("langchain-core==0.3.15", (0, 3, 15)),
    ("v1.23.12811.0", (1, 23, 12811)),
    ("b8492", None),
    ("", None),
    (None, None),
])
def test_versao(tag, esperado):
    assert corretiva.versao(tag) == esperado


@pytest.mark.parametrize("tag, esperado", [
    ("v1.2.3", ""),
    ("1.2.3", ""),
    ("vite@7.1.0", "vite"),
    ("create-vite@8.0.1", "create-vite"),
    ("langchain-core==0.3.15", "langchain-core"),
    ("@tauri-apps/cli-v2.1.0", "@tauri-apps/cli"),
    ("release-v1.0.0", "release"),
    ("Puppeteer-V24.1.0", "puppeteer"),
    ("b8492", "b"),
    ("r181", "r"),
    ("nightly", "nightly"),
])
def test_linha(tag, esperado):
    assert corretiva.linha(tag) == esperado


@pytest.mark.parametrize("tag, esperado", [
    ("v2.3.1", True),
    ("v2.4.0", False),
    ("v3.0", False),
    ("2026.10.1", True),
    ("b8492", False),
])
def test_e_patch(tag, esperado):
    assert corretiva.e_patch(tag) is esperado


@pytest.mark.parametrize("mensagem, esperado", [
    ("fix: crash ao abrir arquivo", True),
    ("fix(parser): aceitar tag vazia", True),
    ("Fixes #123", True),
    ("Fixed typo in README", True),
    ('Revert "feat: novo cache"', True),
    ("hotfix login", True),
    ("bugfix: timeout", True),
    ("bug fix for windows", True),
    ("Merge pull request #10 from user/fix-crash", True),
    ("fix(deps): update dependency react to v19", False),
    ("fix(deps-dev): bump vitest", False),
    ("add prefix option", False),
    ("update fixtures", False),
    ("feat: suffix support", False),
    ("", False),
    (None, False),
])
def test_mensagem_de_correcao(mensagem, esperado):
    assert corretiva.e_mensagem_de_correcao(mensagem) is esperado


def test_proporcao_ignora_merges():
    mensagens = [
        "fix: a",
        "Merge pull request #1 from x/fix-a",
        "Merge branch 'main' into dev",
        "feat: b",
    ]
    assert corretiva.proporcao_de_correcoes(mensagens) == 0.5
    assert corretiva.proporcao_de_correcoes([]) == 0.0
    assert corretiva.proporcao_de_correcoes(["Merge branch 'x'"]) == 0.0


@pytest.mark.parametrize("versao_heuristica, tag, mensagens, esperado", [
    ("v1_patch", "v1.0.1", ["feat: x"], True),
    ("v1_patch", "v1.1.0", ["fix: x"], False),
    ("v2_mensagens", "v1.1.0", ["fix: x"], True),
    ("v2_mensagens", "v1.0.1", ["feat: x"], False),
    ("v3_patch_e_mensagens", "v1.0.1", ["fix: x"], True),
    ("v3_patch_e_mensagens", "v1.0.1", ["feat: x"], False),
    ("v3_patch_e_mensagens", "v1.1.0", ["fix: x"], False),
    ("v4_patch_ou_mensagens", "v1.1.0", ["fix: x"], True),
    ("v4_patch_ou_mensagens", "v1.1.0", ["feat: x"], False),
    ("v5_patch_e_maioria", "v1.0.1", ["fix: a", "fix: b", "feat: c"], True),
    ("v5_patch_e_maioria", "v1.0.1", ["fix: a", "feat: b", "docs: c"], False),
    ("v5_patch_e_maioria", "v1.1.0", ["fix: a"], False),
])
def test_versoes_da_heuristica(versao_heuristica, tag, mensagens, esperado):
    assert corretiva.HEURISTICAS[versao_heuristica](tag, mensagens) is esperado


def test_padrao_esta_entre_as_versoes():
    assert corretiva.PADRAO in corretiva.HEURISTICAS


def test_cfr_b_exemplo_do_enunciado(exemplo_enunciado):
    resultado = cfr.cfr_entrega(exemplo_enunciado, FIM)
    assert resultado["releases_avaliadas_cfr_b"] == 4
    assert resultado["releases_falha_cfr_b"] == 1
    assert resultado["cfr_b"] == 0.25
    assert resultado["releases_corretivas"] == 1
    assert resultado["releases_censuradas_cfr_b"] == 0


def test_cfr_b_ordem_de_entrada_nao_importa(exemplo_enunciado):
    resultado = cfr.cfr_entrega(list(reversed(exemplo_enunciado)), FIM)
    assert resultado["cfr_b"] == 0.25


def test_cfr_b_correcao_depois_de_7_dias_nao_conta():
    releases = [
        _release("v1.0.0", "2026-05-01T00:00:00Z"),
        _release("v1.0.1", "2026-05-08T00:00:01Z", ["fix: x"]),
    ]
    assert cfr.cfr_entrega(releases, FIM)["releases_falha_cfr_b"] == 0


def test_cfr_b_correcao_com_exatos_7_dias_conta():
    releases = [
        _release("v1.0.0", "2026-05-01T00:00:00Z"),
        _release("v1.0.1", "2026-05-08T00:00:00Z", ["fix: x"]),
    ]
    assert cfr.cfr_entrega(releases, FIM)["releases_falha_cfr_b"] == 1


def test_cfr_b_releases_do_fim_da_janela_sao_censuradas():
    releases = [
        _release("v1.0.0", "2026-09-25T23:59:59Z"),
        _release("v1.0.1", "2026-09-26T00:00:00Z", ["fix: x"]),
        _release("v1.0.2", "2026-10-02T10:00:00Z", ["fix: y"]),
    ]
    resultado = cfr.cfr_entrega(releases, FIM)
    # v1.0.0 ainda tem os 7 dias dentro da janela; as outras duas nao
    assert resultado["releases_avaliadas_cfr_b"] == 1
    assert resultado["releases_censuradas_cfr_b"] == 2
    assert resultado["releases_falha_cfr_b"] == 1
    assert resultado["cfr_b"] == 1.0


def test_cfr_b_so_olha_a_mesma_linha_do_monorepo():
    releases = [
        _release("vite@7.0.0", "2026-03-01T00:00:00Z", ["feat: x"]),
        _release("create-vite@8.0.1", "2026-03-02T00:00:00Z", ["fix: template"]),
        _release("vite@7.1.0", "2026-03-20T00:00:00Z", ["feat: y"]),
    ]
    resultado = cfr.cfr_entrega(releases, FIM)
    assert resultado["releases_falha_cfr_b"] == 0
    assert resultado["releases_avaliadas_cfr_b"] == 3


def test_cfr_b_so_olha_a_release_seguinte():
    # a correcao do dia 5 corrige a v1.1.0, nao a v1.0.0
    releases = [
        _release("v1.0.0", "2026-03-01T00:00:00Z"),
        _release("v1.1.0", "2026-03-03T00:00:00Z", ["feat: x"]),
        _release("v1.1.1", "2026-03-05T00:00:00Z", ["fix: x"]),
    ]
    resultado = cfr.cfr_entrega(releases, FIM)
    assert resultado["releases_falha_cfr_b"] == 1
    assert resultado["cfr_b"] == pytest.approx(1 / 3)


def test_cfr_b_com_outra_versao_da_heuristica():
    releases = [
        _release("v1.0.0", "2026-03-01T00:00:00Z"),
        _release("v1.0.1", "2026-03-02T00:00:00Z", ["chore: release"]),
    ]
    assert cfr.cfr_entrega(releases, FIM)["releases_falha_cfr_b"] == 0
    assert cfr.cfr_entrega(releases, FIM, heuristica="v1_patch")["releases_falha_cfr_b"] == 1


def test_cfr_b_sem_releases_avaliaveis():
    assert cfr.cfr_entrega([], FIM)["cfr_b"] is None
    so_no_fim = [_release("v1.0.0", "2026-10-01T00:00:00Z")]
    resultado = cfr.cfr_entrega(so_no_fim, FIM)
    assert resultado["cfr_b"] is None
    assert resultado["releases_censuradas_cfr_b"] == 1


def test_cfr_b_release_sem_mensagens():
    releases = [
        {"tag_name": "v1.0.0", "published_at": "2026-03-01T00:00:00Z"},
        {"tag_name": "v1.0.1", "published_at": "2026-03-02T00:00:00Z"},
    ]
    assert cfr.cfr_entrega(releases, FIM)["releases_falha_cfr_b"] == 0
