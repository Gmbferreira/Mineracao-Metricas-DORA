import datetime as dt

import pytest

from metricas import comum, frequencia, lead_time

DIA = 24.0


@pytest.fixture
def release_v11():
    # exemplo da secao 5 (RQ 02): v1.1 em 15/03 com commits de 02/03, 10/03 e 14/03
    return {
        "published_at": "2026-03-15T00:00:00Z",
        "status": "ok",
        "commits": [
            "2026-03-02T00:00:00Z",
            "2026-03-10T00:00:00Z",
            "2026-03-14T00:00:00Z",
        ],
    }


@pytest.fixture
def release_v12():
    return {
        "published_at": "2026-03-20T12:00:00Z",
        "status": "ok",
        "commits": ["2026-03-20T00:00:00Z"],
    }


def test_variante_a_usa_commit_mais_antigo(release_v11):
    horas = lead_time.lead_time_por_release(
        release_v11["published_at"], release_v11["commits"]
    )
    assert horas == 13 * DIA


def test_variante_b_um_valor_por_commit(release_v11):
    valores, negativos = lead_time.lead_times_por_commit(
        release_v11["published_at"], release_v11["commits"]
    )
    assert sorted(valores) == [1 * DIA, 5 * DIA, 13 * DIA]
    assert negativos == 0


def test_repositorio_agrega_pela_mediana(release_v11, release_v12):
    resultado = lead_time.lead_time_repositorio([release_v11, release_v12])
    # (a): mediana de 13 dias e 12 horas
    assert resultado["lead_time_a_horas"] == (13 * DIA + 12) / 2
    # (b): mediana de [13, 5, 1 dias, 12 horas] = (1 dia + 5 dias) / 2
    assert resultado["lead_time_b_horas"] == 3 * DIA
    assert resultado["releases_avaliadas"] == 2
    assert resultado["commits_avaliados"] == 4


def test_commit_antigo_esquecido_afeta_mais_a_variante_a():
    releases = [
        {
            "published_at": "2026-06-01T00:00:00Z",
            "status": "ok",
            "commits": ["2025-06-01T00:00:00Z"] + ["2026-05-31T00:00:00Z"] * 9,
        }
    ]
    resultado = lead_time.lead_time_repositorio(releases)
    assert resultado["lead_time_a_horas"] == 365 * DIA
    assert resultado["lead_time_b_horas"] == 1 * DIA


def test_release_sem_commits_novos_fica_fora():
    releases = [{"published_at": "2026-03-15T00:00:00Z", "status": "ok", "commits": []}]
    resultado = lead_time.lead_time_repositorio(releases)
    assert resultado["lead_time_a_horas"] is None
    assert resultado["lead_time_b_horas"] is None
    assert resultado["releases_sem_commits"] == 1
    assert resultado["releases_avaliadas"] == 0


def test_primeira_release_e_compare_404_sao_ignoradas(release_v11):
    releases = [
        {"published_at": "2026-01-01T00:00:00Z", "status": "sem_anterior", "commits": []},
        {"published_at": "2026-02-01T00:00:00Z", "status": "404", "commits": []},
        {"published_at": "2026-02-02T00:00:00Z", "status": "erro", "commits": []},
        release_v11,
    ]
    resultado = lead_time.lead_time_repositorio(releases)
    assert resultado["releases_sem_anterior"] == 1
    assert resultado["releases_compare_falho"] == 2
    assert resultado["releases_avaliadas"] == 1
    assert resultado["lead_time_a_horas"] == 13 * DIA


def test_repositorio_com_uma_unica_release():
    releases = [{"published_at": "2026-01-01T00:00:00Z", "status": "sem_anterior"}]
    resultado = lead_time.lead_time_repositorio(releases)
    assert resultado["lead_time_a_horas"] is None
    assert resultado["releases_sem_anterior"] == 1


def test_commit_com_data_depois_da_release_e_descartado():
    releases = [
        {
            "published_at": "2026-03-15T00:00:00Z",
            "status": "ok",
            "commits": ["2026-03-16T00:00:00Z", "2026-03-14T00:00:00Z", None],
        }
    ]
    resultado = lead_time.lead_time_repositorio(releases)
    assert resultado["commits_data_invalida"] == 1
    assert resultado["commits_avaliados"] == 1
    assert resultado["lead_time_a_horas"] == 1 * DIA


def test_release_so_com_commits_invalidos_nao_tem_lead_time():
    assert lead_time.lead_time_por_release(
        "2026-03-15T00:00:00Z", ["2026-03-16T00:00:00Z"]
    ) is None


def test_lista_vazia():
    resultado = lead_time.lead_time_repositorio([])
    assert resultado["lead_time_a_horas"] is None
    assert resultado["releases_avaliadas"] == 0


def test_para_datetime_aceita_formatos():
    assert comum.para_datetime(None) is None
    assert comum.para_datetime("") is None
    sem_fuso = comum.para_datetime("2026-03-15T10:00:00")
    assert sem_fuso.tzinfo is not None
    pronto = dt.datetime(2026, 3, 15, tzinfo=dt.timezone.utc)
    assert comum.para_datetime(pronto) == pronto
    assert comum.horas_entre("2026-03-15T10:00:00Z", "2026-03-15T11:30:00Z") == 1.5


def test_mediana_ignora_none():
    assert comum.mediana([]) is None
    assert comum.mediana([None, 3, 1]) == 2.0


def test_deployment_frequency_por_semana():
    inicio, fim = dt.date(2025, 10, 2), dt.date(2026, 10, 2)
    assert frequencia.semanas_da_janela(inicio, fim) == pytest.approx(52.14, 0.001)
    assert frequencia.deployment_frequency(365, inicio, fim) == pytest.approx(7.0)
    assert frequencia.deployment_frequency(3, inicio, inicio) is None


def test_releases_na_janela_descarta_draft_e_pre():
    inicio, fim = dt.date(2025, 10, 2), dt.date(2026, 10, 2)
    releases = [
        {"draft": False, "prerelease": False, "published_at": "2025-10-02T00:00:00Z"},
        {"draft": False, "prerelease": True, "published_at": "2026-01-01T00:00:00Z"},
        {"draft": True, "prerelease": False, "published_at": "2026-01-01T00:00:00Z"},
        {"draft": False, "prerelease": False, "published_at": None},
        {"draft": False, "prerelease": False, "published_at": "2026-10-03T00:00:00Z"},
    ]
    assert frequencia.releases_na_janela(releases, inicio, fim) == 1
    assert frequencia.releases_na_janela(releases, inicio, fim, incluir_pre=True) == 2
