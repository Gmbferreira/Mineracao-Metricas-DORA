import pytest

from metricas import cfr, recuperacao


def _run(id_, hora, conclusion, workflow=1, fim=None):
    inicio = f"2026-03-10T{hora}:00Z"
    return {
        "id": id_,
        "workflow_id": workflow,
        "conclusion": conclusion,
        "created_at": inicio,
        "run_started_at": inicio,
        "updated_at": f"2026-03-10T{fim}:00Z" if fim else inicio,
    }


@pytest.fixture
def exemplo_enunciado():
    # secao 5 (RQ 04): workflow CI na main
    return [
        _run(1, "09:00", "success", fim="09:05"),
        _run(2, "10:00", "failure", fim="10:10"),
        _run(3, "10:30", "failure", fim="10:40"),
        _run(4, "11:15", "success", fim="11:20"),
    ]


def test_classificar_conclusoes():
    assert cfr.classificar("success") == "sucesso"
    for falha in ("failure", "timed_out", "startup_failure"):
        assert cfr.classificar(falha) == "falha"
    for ignorado in ("cancelled", "skipped", "neutral", "action_required", "stale", None, ""):
        assert cfr.classificar(ignorado) is None


def test_cfr_ignora_cancelados_e_em_andamento():
    runs = [
        {"conclusion": "success"},
        {"conclusion": "success"},
        {"conclusion": "success"},
        {"conclusion": "failure"},
        {"conclusion": "cancelled"},
        {"conclusion": "skipped"},
        {"conclusion": None},
    ]
    resultado = cfr.cfr_ci(runs)
    assert resultado["cfr_a"] == 0.25
    assert resultado["runs_falha"] == 1
    assert resultado["runs_sucesso"] == 3
    assert resultado["runs_ignorados"] == 3


def test_cfr_sem_falhas_e_zero():
    assert cfr.cfr_ci([{"conclusion": "success"}])["cfr_a"] == 0.0


def test_cfr_sem_runs_validos_e_indefinido():
    assert cfr.cfr_ci([{"conclusion": "cancelled"}])["cfr_a"] is None
    assert cfr.cfr_ci([])["cfr_a"] is None


def test_episodio_do_enunciado_dura_1h20(exemplo_enunciado):
    episodios, sem_inicio = recuperacao.episodios_de_falha(exemplo_enunciado)
    assert len(episodios) == 1
    assert episodios[0]["horas"] == pytest.approx(80 / 60)
    assert not episodios[0]["censurado"]
    assert sem_inicio == 0


def test_ordena_por_data_antes_de_medir(exemplo_enunciado):
    episodios, _ = recuperacao.episodios_de_falha(list(reversed(exemplo_enunciado)))
    assert episodios[0]["horas"] == pytest.approx(80 / 60)


def test_falha_nunca_recuperada_e_censurada():
    runs = [_run(1, "09:00", "success"), _run(2, "10:00", "failure"), _run(3, "11:00", "failure")]
    episodios, _ = recuperacao.episodios_de_falha(runs)
    assert episodios == [
        {"inicio": "2026-03-10T10:00:00Z", "fim": None, "horas": None, "censurado": True}
    ]


def test_cancelado_no_meio_nao_encerra_o_episodio():
    runs = [
        _run(1, "09:00", "success"),
        _run(2, "10:00", "failure"),
        _run(3, "10:30", "cancelled"),
        _run(4, "11:00", "success", fim="11:00"),
    ]
    episodios, _ = recuperacao.episodios_de_falha(runs)
    assert episodios[0]["horas"] == 1.0


def test_falhas_antes_do_primeiro_sucesso_nao_abrem_episodio():
    runs = [_run(1, "08:00", "failure"), _run(2, "09:00", "failure"), _run(3, "10:00", "success")]
    episodios, sem_inicio = recuperacao.episodios_de_falha(runs)
    assert episodios == []
    assert sem_inicio == 2


def test_sem_falhas_nao_tem_episodio():
    runs = [_run(1, "09:00", "success"), _run(2, "10:00", "success")]
    episodios, _ = recuperacao.episodios_de_falha(runs)
    assert episodios == []


def test_repositorio_mede_dentro_de_cada_workflow():
    # a falha do workflow 1 nao e encerrada pelo sucesso do workflow 2
    runs = [
        _run(1, "09:00", "success", workflow=1),
        _run(2, "10:00", "failure", workflow=1),
        _run(3, "10:30", "success", workflow=2),
        _run(4, "12:00", "success", workflow=1),
        _run(5, "13:00", "success", workflow=2),
        _run(6, "14:00", "failure", workflow=2),
        _run(7, "14:30", "success", workflow=2),
        _run(8, "15:00", "failure", workflow=1),
    ]
    resultado = recuperacao.tempo_recuperacao_repositorio(runs)
    assert resultado["episodios"] == 3
    assert resultado["episodios_censurados"] == 1
    assert resultado["proporcao_censurados"] == pytest.approx(1 / 3)
    assert resultado["recuperacao_horas"] == pytest.approx((2.0 + 0.5) / 2)


def test_repositorio_sem_falhas():
    resultado = recuperacao.tempo_recuperacao_repositorio(
        [_run(1, "09:00", "success"), _run(2, "10:00", "cancelled")]
    )
    assert resultado["recuperacao_horas"] is None
    assert resultado["episodios"] == 0
    assert resultado["proporcao_censurados"] is None


def test_repositorio_so_com_episodios_censurados():
    resultado = recuperacao.tempo_recuperacao_repositorio(
        [_run(1, "09:00", "success"), _run(2, "10:00", "timed_out")]
    )
    assert resultado["recuperacao_horas"] is None
    assert resultado["proporcao_censurados"] == 1.0


def test_agrupa_pelo_nome_sem_workflow_id():
    runs = [{"name": "CI", "conclusion": "success"}, {"name": "Lint", "conclusion": "success"}]
    grupos = recuperacao.agrupar_por_workflow(runs)
    assert set(grupos) == {"CI", "Lint"}
