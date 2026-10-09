import csv
import datetime as dt
import json

from pipeline import coleta, consolidacao
from tests.falsos import ClienteFalso, RespostaFalsa


class Cfg:
    janela_inicio = dt.date(2025, 10, 2)
    janela_fim = dt.date(2026, 10, 2)


def _release(tag, data):
    return {"tag_name": tag, "draft": False, "prerelease": False,
            "created_at": data, "published_at": data,
            "html_url": f"https://github.com/o/r/releases/tag/{tag}"}


def _run(id_, hora, conclusion):
    data = f"2026-03-10T{hora}:00Z"
    return {"id": id_, "workflow_id": 1, "name": "CI", "event": "push",
            "head_branch": "main", "conclusion": conclusion, "created_at": data,
            "run_started_at": data, "updated_at": data}


class _ComTotal:
    """Expoe `chamadas` como contador, igual ao ClienteGitHub."""

    def __init__(self, cliente):
        self._cliente = cliente

    @property
    def chamadas(self):
        return len(self._cliente.chamadas)

    def get(self, *args, **kwargs):
        return self._cliente.get(*args, **kwargs)


def _cliente():
    runs = [_run(1, "09:00", "success"), _run(2, "10:00", "failure"),
            _run(3, "12:00", "success")]

    def responder_runs(params):
        if params["created"].startswith("2026-03-01"):
            return RespostaFalsa(200, {"total_count": 3, "workflow_runs": runs})
        return RespostaFalsa(200, {"total_count": 0, "workflow_runs": []})

    return ClienteFalso({
        "/repos/o/r/releases": RespostaFalsa(200, [
            _release("v2", "2026-03-15T00:00:00Z"),
            _release("v1", "2026-03-01T00:00:00Z"),
            _release("v0", "2025-01-01T00:00:00Z"),
        ]),
        "/repos/o/r/compare/v0...v1": RespostaFalsa(404, {}),
        "/repos/o/r/compare/v1...v2": RespostaFalsa(200, {
            "total_commits": 2,
            "commits": [
                {"sha": "a", "commit": {"author": {"date": "2026-03-02T00:00:00Z"},
                                        "message": "feat: x"}},
                {"sha": "b", "commit": {"author": {"date": "2026-03-14T00:00:00Z"},
                                        "message": "fix: y"}},
            ],
        }),
        "/repos/o/r/actions/runs": responder_runs,
    })


def test_coletar_amostra_salva_e_retoma(tmp_path, capsys):
    cliente = _cliente()
    cliente_com_total = _ComTotal(cliente)
    amostra = [{"full_name": "o/r", "default_branch": "main"}]
    coletados, erros = coleta.coletar_amostra(cliente_com_total, Cfg(), amostra, str(tmp_path))
    assert erros == []
    assert len(coletados[0]["runs"]) == 3
    chamadas = len(cliente.chamadas)
    assert chamadas > 0

    de_novo, _ = coleta.coletar_amostra(cliente_com_total, Cfg(), amostra, str(tmp_path))
    assert len(cliente.chamadas) == chamadas
    assert de_novo[0]["full_name"] == "o/r"
    assert "ja coletado" in capsys.readouterr().out


def test_coleta_de_outra_janela_e_refeita(tmp_path):
    coleta.salvar(str(tmp_path), "o/r", {"janela": {"inicio": "2020-01-01", "fim": "2021-01-01"}})
    assert coleta.carregar(str(tmp_path), "o/r", Cfg()) is None
    assert coleta.carregar(str(tmp_path), "x/y", Cfg()) is None


def test_erro_num_repositorio_nao_para_os_outros(tmp_path):
    cliente = _ComTotal(ClienteFalso({"/repos/o/r/releases": RuntimeError("HTTP 500")}))
    amostra = [{"full_name": "o/r", "default_branch": "main"}]
    coletados, erros = coleta.coletar_amostra(cliente, Cfg(), amostra, str(tmp_path))
    assert coletados == []
    assert erros[0]["full_name"] == "o/r"


def test_consolidar_gera_csvs(tmp_path):
    cliente = _ComTotal(_cliente())
    amostra = [{"full_name": "o/r", "default_branch": "main"}]
    coletados, _ = coleta.coletar_amostra(cliente, Cfg(), amostra, str(tmp_path / "coleta"))
    arq_metricas = tmp_path / "metricas.csv"
    arq_releases = tmp_path / "releases.csv"
    consolidacao.consolidar(coletados, Cfg.janela_inicio, Cfg.janela_fim,
                            str(arq_metricas), str(arq_releases))

    with open(arq_metricas, encoding="utf-8") as f:
        linha = next(csv.DictReader(f))
    assert linha["releases_janela"] == "2"
    assert float(linha["lead_time_a_horas"]) == 13 * 24
    assert linha["releases_compare_falho"] == "1"
    assert float(linha["cfr_a"]) == round(1 / 3, 4)
    assert float(linha["recuperacao_horas"]) == 2.0
    assert linha["classe_cfr"] == "Medium"

    with open(arq_releases, encoding="utf-8") as f:
        releases = list(csv.DictReader(f))
    assert [r["status_compare"] for r in releases] == ["404", "ok"]
    assert releases[1]["lead_time_horas"] == "312.0"
    assert releases[0]["lead_time_horas"] == ""


def test_ler_amostra(tmp_path):
    caminho = tmp_path / "amostra.csv"
    caminho.write_text("full_name,default_branch\no/r,main\n", encoding="utf-8")
    assert coleta.ler_amostra(str(caminho)) == [{"full_name": "o/r", "default_branch": "main"}]


def test_arquivo_repo_nao_cria_subpasta(tmp_path):
    caminho = coleta.arquivo_repo(str(tmp_path), "dono/repo")
    assert caminho.endswith("dono__repo.json")
    coleta.salvar(str(tmp_path), "dono/repo", {"x": 1})
    with open(caminho, encoding="utf-8") as f:
        assert json.load(f) == {"x": 1}



def test_erro_ao_gravar_nao_para_os_outros(tmp_path, monkeypatch):
    def falhar(*_):
        raise PermissionError("WinError 32")

    monkeypatch.setattr(coleta, "salvar", falhar)
    amostra = [{"full_name": "o/r", "default_branch": "main"}]
    coletados, erros = coleta.coletar_amostra(_ComTotal(_cliente()), Cfg(), amostra, str(tmp_path))
    assert coletados == []
    assert "WinError 32" in erros[0]["erro"]


def test_coleta_paralela_da_o_mesmo_resultado_da_sequencial(tmp_path):
    amostra = [{"full_name": "o/r", "default_branch": "main"}]
    sequencial, _ = coleta.coletar_amostra(
        _ComTotal(_cliente()), Cfg(), amostra, str(tmp_path / "seq"), paralelo=1
    )
    paralela, erros = coleta.coletar_amostra(
        _ComTotal(_cliente()), Cfg(), amostra, str(tmp_path / "par"), paralelo=4
    )
    assert erros == []
    assert paralela[0]["runs"] == sequencial[0]["runs"]
    assert paralela[0]["avaliadas"] == sequencial[0]["avaliadas"]
