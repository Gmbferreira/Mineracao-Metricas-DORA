import pandas as pd
import pytest

from validacao import consenso


def _series(categorias):
    return pd.Series(categorias, dtype=object)


def test_montar_usa_acordo_e_desempate():
    rotulos = {
        "a": {"corretiva": _series(["sim", "sim", "nao"])},
        "b": {"corretiva": _series(["sim", "nao", "nao"])},
    }
    decisoes = pd.DataFrame([{"dimensao": "corretiva", "id": 1, "consenso": "sim",
                              "motivo": "notes listam 3 correcoes"}])
    # precisa das outras dimensoes preenchidas para o protocolo
    rotulos["a"]["tipo_projeto"] = rotulos["b"]["tipo_projeto"] = _series(["outro"] * 60)
    rotulos["a"]["entregas_reais"] = rotulos["b"]["entregas_reais"] = _series(["sim"] * 60)
    with pytest.raises(SystemExit, match="sem decisao de desempate"):
        consenso.montar(rotulos)
    resultado = consenso.montar(rotulos, decisoes)
    assert resultado["corretiva"][0] == "sim"
    assert resultado["corretiva"][2] == "nao"
    assert resultado["corretiva"][1] == "sim"


def test_montar_acusa_decisao_fora_de_divergencia():
    rotulos = {
        "a": {"corretiva": _series(["sim", "nao"])},
        "b": {"corretiva": _series(["sim", "nao"])},
    }
    rotulos["a"]["tipo_projeto"] = rotulos["b"]["tipo_projeto"] = _series(["outro"] * 60)
    rotulos["a"]["entregas_reais"] = rotulos["b"]["entregas_reais"] = _series(["sim"] * 60)
    decisoes = pd.DataFrame([{"dimensao": "corretiva", "id": 0, "consenso": "nao",
                              "motivo": "x"}])
    with pytest.raises(SystemExit, match="sem divergencia"):
        consenso.montar(rotulos, decisoes)


def test_gerar_junta_com_as_planilhas_de_origem():
    rotulos = {"a": {}, "b": {}}
    for dimensao, valores in (("tipo_projeto", ["outro"] * 2),
                              ("entregas_reais", ["sim"] * 2),
                              ("corretiva", ["sim", "nao"])):
        rotulos["a"][dimensao] = _series(valores)
        rotulos["b"][dimensao] = _series(valores)
    amostra = pd.DataFrame([{"id_repo": 0, "full_name": "o/r", "html_url": "u"},
                            {"id_repo": 1, "full_name": "o/r2", "html_url": "u"}])
    releases = pd.DataFrame([{"id_release": 0, "id_repo": 0, "full_name": "o/r",
                              "tag_name": "v1", "link_release": "u"},
                             {"id_release": 1, "id_repo": 1, "full_name": "o/r2",
                              "tag_name": "v2", "link_release": "u"}])
    repos, tabela = consenso.gerar(rotulos, None, amostra, releases)
    assert list(repos.columns) == ["id_repo", "full_name", "tipo_projeto", "entregas_reais"]
    assert list(tabela.columns) == ["id_release", "full_name", "tag_name", "corretiva"]
    assert tabela.loc[0, "corretiva"] == "sim"
    assert repos.loc[1, "full_name"] == "o/r2"


def test_carregar_decisoes_ausente_devolve_tabela_vazia(tmp_path):
    decisoes = consenso.carregar_decisoes(str(tmp_path / "nao_existe.csv"))
    assert list(decisoes.columns) == consenso.CABECALHO_DECISOES
    assert decisoes.empty


def test_carregar_decisoes_acusa_coluna_ausente(tmp_path):
    caminho = tmp_path / "decisoes.csv"
    caminho.write_text("dimensao,id,consenso\ncorretiva,1,sim\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="colunas ausentes"):
        consenso.carregar_decisoes(str(caminho))


def _planilha(caminho, diverge=False):
    from openpyxl import Workbook
    livro = Workbook()
    repos = livro.active
    repos.title = "repositorios"
    repos.append(["id_repo", "repositorio", "link", "tipo_projeto",
                  "entregas_reais", "observacao"])
    for i in range(60):
        repos.append([i, f"o/r{i}", "u", "outro", "sim", None])
    rels = livro.create_sheet("releases")
    rels.append(["id_release", "id_repo", "repositorio", "tag", "publicada_em",
                 "link_release", "link_commits", "corretiva", "observacao"])
    for i in range(300):
        rels.append([i, 0, "o/r0", f"v{i}", "2025-01-01", "u", "u",
                     "nao" if (diverge and i == 0) else "sim", None])
    livro.save(caminho)


def test_main_gera_os_dois_csvs(tmp_path):
    _planilha(tmp_path / "rotulos_gabriel.xlsx")
    _planilha(tmp_path / "rotulos_guilherme.xlsx")
    amostra = pd.DataFrame([{"id_repo": i, "full_name": f"o/r{i}", "html_url": "u"}
                            for i in range(60)])
    releases = pd.DataFrame([{"id_release": i, "id_repo": 0, "full_name": "o/r0",
                              "tag_name": f"v{i}", "link_release": "u"}
                             for i in range(300)])
    amostra.to_csv(tmp_path / "amostra_ouro.csv", index=False)
    releases.to_csv(tmp_path / "releases_ouro.csv", index=False)

    consenso.main(diretorio=str(tmp_path), argv=[])
    repos = pd.read_csv(tmp_path / "consenso_repositorios.csv")
    tabela = pd.read_csv(tmp_path / "consenso_releases.csv")
    assert len(repos) == 60 and len(tabela) == 300
    assert list(repos.columns) == ["id_repo", "full_name", "tipo_projeto", "entregas_reais"]
    assert list(tabela.columns) == ["id_release", "full_name", "tag_name", "corretiva"]
    assert (tabela["corretiva"] == "sim").sum() == 300


def test_main_exige_decisao_para_divergencia(tmp_path):
    _planilha(tmp_path / "rotulos_gabriel.xlsx", diverge=True)
    _planilha(tmp_path / "rotulos_guilherme.xlsx")
    amostra = pd.DataFrame([{"id_repo": i, "full_name": f"o/r{i}", "html_url": "u"}
                            for i in range(60)])
    releases = pd.DataFrame([{"id_release": i, "id_repo": 0, "full_name": "o/r0",
                              "tag_name": f"v{i}", "link_release": "u"}
                             for i in range(300)])
    amostra.to_csv(tmp_path / "amostra_ouro.csv", index=False)
    releases.to_csv(tmp_path / "releases_ouro.csv", index=False)

    with pytest.raises(SystemExit, match="sem decisao de desempate"):
        consenso.main(diretorio=str(tmp_path), argv=[])
    (tmp_path / "decisoes_desempate.csv").write_text(
        "dimensao,id,consenso,motivo\ncorretiva,0,sim,notes listam correcoes\n",
        encoding="utf-8")
    consenso.main(diretorio=str(tmp_path), argv=[])
    tabela = pd.read_csv(tmp_path / "consenso_releases.csv")
    assert tabela.loc[0, "corretiva"] == "sim"
