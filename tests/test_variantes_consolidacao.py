import csv
import datetime as dt

from pipeline import consolidacao

INICIO = dt.date(2025, 10, 2)
FIM = dt.date(2026, 10, 2)


def _avaliada(tag, data, anterior, datas_commits, status="ok"):
    return {"tag_name": tag, "published_at": data, "tag_anterior": anterior, "status": status,
            "commits": [{"data_autor": d, "mensagem": "fix: x"} for d in datas_commits]}


def _dados(com_variantes=True):
    dados = {
        "full_name": "o/r",
        "releases": [
            {"tag_name": "v1.0.0", "draft": False, "prerelease": False, "published_at": "2026-01-01T00:00:00Z"},
            {"tag_name": "v1.0.1", "draft": False, "prerelease": False, "published_at": "2026-01-03T00:00:00Z"},
        ],
        "avaliadas": [
            _avaliada("v1.0.0", "2026-01-01T00:00:00Z", None, [], status="sem_anterior"),
            _avaliada("v1.0.1", "2026-01-03T00:00:00Z", "v1.0.0", ["2026-01-02T00:00:00Z"]),
        ],
        "notas": {"v1.0.1": "Bug fixes", "v1.1.0-rc.1": "New features"},
        "runs": [
            {"id": 1, "workflow_id": 1, "conclusion": "success", "created_at": "2026-01-01T00:00:00Z",
             "run_started_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"},
            {"id": 2, "workflow_id": 1, "conclusion": "failure", "created_at": "2026-01-02T00:00:00Z",
             "run_started_at": "2026-01-02T00:00:00Z", "updated_at": "2026-01-02T00:00:00Z"},
            {"id": 3, "workflow_id": 1, "conclusion": "success", "created_at": "2026-01-02T00:00:00Z",
             "run_started_at": "2026-01-02T00:30:00Z", "updated_at": "2026-01-02T00:30:00Z"},
        ],
    }
    if com_variantes:
        dados["variantes"] = {
            "release_pre": {"avaliadas": dados["avaliadas"] + [
                _avaliada("v1.1.0-rc.1", "2026-01-10T00:00:00Z", "v1.0.1", ["2026-01-09T00:00:00Z"])]},
            "tag": {"tags": [], "avaliadas": [
                _avaliada("t1", "2026-01-01T00:00:00Z", None, [], status="sem_anterior"),
                _avaliada("t2", "2026-01-02T00:00:00Z", "t1", ["2026-01-01T12:00:00Z"]),
                _avaliada("t3", "2026-01-05T00:00:00Z", "t2", ["2026-01-04T00:00:00Z", "2026-01-01T00:00:00Z"]),
            ]},
        }
    return dados


def test_metricas_por_unidade_de_deploy():
    linha = consolidacao.metricas_variantes(_dados(), INICIO, FIM)
    assert linha["unidades_release"] == 2
    assert linha["unidades_release_pre"] == 3
    assert linha["unidades_tag"] == 3
    assert linha["lead_time_a_release"] == 24.0
    assert linha["lead_time_b_tag"] == 24.0
    assert linha["lead_time_a_tag"] == (12.0 + 96.0) / 2
    # v1.0.0 falhou: a v1.0.1 saiu 2 dias depois, e patch com notas de correcao
    assert linha["cfr_b_release"] == 0.5
    assert linha["cfr_a"] == round(1 / 3, 4)
    assert linha["recuperacao_horas"] == 0.5


def test_classificacao_das_tres_combinacoes():
    linha = consolidacao.metricas_variantes(_dados(), INICIO, FIM)
    assert linha["classe_lead_time_c1"] == "High"   # (a) da release: 24 horas
    assert linha["classe_lead_time_c3"] == "High"   # (b) da tag: 24 horas
    assert linha["classe_cfr_c1"] == linha["classe_cfr_c3"] == "Medium"  # cfr (a) de 1/3
    assert linha["classe_recuperacao_c2"] == "Elite"
    for combinacao in ("c1", "c2", "c3"):
        assert linha[f"classe_geral_{combinacao}"] in {"Elite", "High", "Medium", "Low"}


def test_commits_das_variantes_sem_mensagem():
    dados = _dados()
    for item in dados["variantes"]["release_pre"]["avaliadas"]:
        item["commits"] = [{"sha": "s", "data_autor": c["data_autor"]} for c in item["commits"]]
    linha = consolidacao.metricas_variantes(dados, INICIO, FIM)
    assert linha["cfr_b_release_pre"] != ""
    assert linha["lead_time_b_release_pre"] == 24.0


def test_sem_variantes_so_preenche_a_referencia():
    linha = consolidacao.metricas_variantes(_dados(com_variantes=False), INICIO, FIM)
    assert "classe_geral_c1" in linha
    assert "classe_geral_c2" not in linha
    assert "unidades_tag" not in linha


def test_consolidar_grava_o_csv_de_variantes(tmp_path):
    arquivo = tmp_path / "variantes.csv"
    consolidacao.consolidar([_dados()], INICIO, FIM, str(tmp_path / "d.csv"), str(tmp_path / "r.csv"),
                            arq_variantes=str(arquivo))
    with open(arquivo, encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        assert leitor.fieldnames == consolidacao.CAMPOS_VARIANTES
        linha = next(leitor)
    with open(tmp_path / "d.csv", encoding="utf-8") as f:
        principal = next(csv.DictReader(f))
    assert linha["classe_geral_c1"] == principal["classe_geral"]
