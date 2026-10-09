import datetime as dt

from pipeline import runs as coleta
from tests.falsos import ClienteFalso, RespostaFalsa

UTC = dt.timezone.utc
CAMINHO = "/repos/o/r/actions/runs"


def _run(id_, branch="main", event="push", conclusion="success"):
    return {
        "id": id_,
        "name": "CI",
        "workflow_id": 7,
        "event": event,
        "head_branch": branch,
        "status": "completed",
        "conclusion": conclusion,
        "created_at": f"2026-03-10T10:{id_ % 60:02d}:00Z",
        "run_started_at": f"2026-03-10T10:{id_ % 60:02d}:00Z",
        "updated_at": f"2026-03-10T10:{id_ % 60:02d}:30Z",
        "run_attempt": 1,
        "repository": {"pesado": "x" * 100},
        "head_commit": {"message": "x"},
    }


def test_reduzir_runs_tira_campos_pesados():
    reduzido = coleta.reduzir_runs({"total_count": 1, "workflow_runs": [_run(1)]})
    assert reduzido["total_count"] == 1
    assert "repository" not in reduzido["workflow_runs"][0]
    assert reduzido["workflow_runs"][0]["workflow_id"] == 7
    assert coleta.reduzir_runs("x") == "x"


def test_intervalos_mensais_cobrem_a_janela_sem_sobrepor():
    intervalos = coleta.intervalos_mensais(dt.date(2025, 10, 2), dt.date(2026, 10, 2))
    assert len(intervalos) == 13
    assert intervalos[0] == (
        dt.datetime(2025, 10, 2, tzinfo=UTC),
        dt.datetime(2025, 10, 31, 23, 59, 59, tzinfo=UTC),
    )
    assert intervalos[2][0] == dt.datetime(2025, 12, 1, tzinfo=UTC)
    assert intervalos[3][0] == dt.datetime(2026, 1, 1, tzinfo=UTC)
    assert intervalos[-1] == (
        dt.datetime(2026, 10, 1, tzinfo=UTC),
        dt.datetime(2026, 10, 2, 23, 59, 59, tzinfo=UTC),
    )
    for (_, fim), (proximo, _) in zip(intervalos, intervalos[1:]):
        assert proximo - fim == dt.timedelta(seconds=1)


def test_formatar_intervalo():
    a = dt.datetime(2026, 3, 1, tzinfo=UTC)
    b = dt.datetime(2026, 3, 31, 23, 59, 59, tzinfo=UTC)
    assert coleta.formatar_intervalo(a, b) == "2026-03-01T00:00:00Z..2026-03-31T23:59:59Z"


def test_dividir_intervalo_ao_meio_e_parar_em_um_minuto():
    a = dt.datetime(2026, 3, 1, tzinfo=UTC)
    b = dt.datetime(2026, 3, 2, 23, 59, 59, tzinfo=UTC)
    (a1, b1), (a2, b2) = coleta.dividir_intervalo(a, b)
    assert a1 == a and b2 == b
    assert a2 - b1 == dt.timedelta(seconds=1)
    assert coleta.dividir_intervalo(a, a + dt.timedelta(seconds=30)) is None


def test_buscar_intervalo_pagina_ate_o_total():
    paginas = {
        1: RespostaFalsa(200, {"total_count": 5, "workflow_runs": [_run(1), _run(2)]}),
        2: RespostaFalsa(200, {"total_count": 5, "workflow_runs": [_run(3), _run(4)]}),
        3: RespostaFalsa(200, {"total_count": 5, "workflow_runs": [_run(5)]}),
    }
    cliente = ClienteFalso({(CAMINHO, p): r for p, r in paginas.items()})
    a = dt.datetime(2026, 3, 1, tzinfo=UTC)
    resultado = coleta.buscar_intervalo(cliente, "o/r", "main", a, a, per_page=2)
    assert [run["id"] for run in resultado["runs"]] == [1, 2, 3, 4, 5]
    assert resultado["no_teto"] == 0
    parametros = cliente.chamadas[0][1]
    assert parametros["event"] == "push"
    assert parametros["branch"] == "main"
    assert parametros["created"] == "2026-03-01T00:00:00Z..2026-03-01T00:00:00Z"


def test_buscar_intervalo_divide_quando_passa_do_teto():
    def responder(params):
        if params["created"].startswith("2026-03-01T00:00:00Z..2026-03-31"):
            return RespostaFalsa(200, {"total_count": 2500, "workflow_runs": [_run(1)]})
        inicio = params["created"][:10]
        id_ = 10 if inicio == "2026-03-01" else 20
        return RespostaFalsa(200, {"total_count": 1, "workflow_runs": [_run(id_)]})

    cliente = ClienteFalso({CAMINHO: responder})
    a = dt.datetime(2026, 3, 1, tzinfo=UTC)
    b = dt.datetime(2026, 3, 31, 23, 59, 59, tzinfo=UTC)
    resultado = coleta.buscar_intervalo(cliente, "o/r", "main", a, b, per_page=100, teto=1000)
    assert sorted(run["id"] for run in resultado["runs"]) == [10, 20]
    assert resultado["intervalos"] == 2
    assert resultado["no_teto"] == 0


def test_buscar_intervalo_minimo_ainda_no_teto_e_registrado():
    resposta = RespostaFalsa(200, {"total_count": 3, "workflow_runs": [_run(1)]})
    cliente = ClienteFalso({CAMINHO: resposta})
    a = dt.datetime(2026, 3, 1, tzinfo=UTC)
    resultado = coleta.buscar_intervalo(cliente, "o/r", "main", a, a, per_page=1, teto=2)
    assert resultado["no_teto"] == 1
    assert len(cliente.chamadas) == 2


def test_buscar_intervalo_sem_acesso():
    cliente = ClienteFalso({CAMINHO: RespostaFalsa(403, {})})
    a = dt.datetime(2026, 3, 1, tzinfo=UTC)
    resultado = coleta.buscar_intervalo(cliente, "o/r", "main", a, a)
    assert resultado == {"runs": [], "intervalos": 1, "no_teto": 0, "acesso": False}


def test_buscar_intervalo_pagina_seguinte_falha():
    cliente = ClienteFalso({
        (CAMINHO, 1): RespostaFalsa(200, {"total_count": 4, "workflow_runs": [_run(1), _run(2)]}),
        (CAMINHO, 2): RespostaFalsa(404, {}),
    })
    a = dt.datetime(2026, 3, 1, tzinfo=UTC)
    resultado = coleta.buscar_intervalo(cliente, "o/r", "main", a, a, per_page=2)
    assert len(resultado["runs"]) == 2


def test_coletar_runs_filtra_push_no_default_branch_e_remove_repetidos():
    resposta = RespostaFalsa(200, {
        "total_count": 4,
        "workflow_runs": [
            _run(2),
            _run(1),
            _run(3, branch="dev"),
            _run(4, event="schedule"),
        ],
    })
    cliente = ClienteFalso({CAMINHO: resposta})
    resultado = coleta.coletar_runs(cliente, "o/r", "main", dt.date(2026, 1, 1), dt.date(2026, 2, 15))
    assert [run["id"] for run in resultado["runs"]] == [1, 2]
    assert resultado["intervalos"] == 2
    assert resultado["acesso"]


def test_coletar_runs_sem_default_branch():
    resultado = coleta.coletar_runs(ClienteFalso({}), "o/r", None, dt.date(2026, 1, 1), dt.date(2026, 1, 2))
    assert resultado["runs"] == []
    assert not resultado["acesso"]
