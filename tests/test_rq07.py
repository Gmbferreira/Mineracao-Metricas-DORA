import pandas as pd
import pytest

from analises import rq07_sensibilidade as rq07


@pytest.fixture
def variantes():
    linhas = []
    classes = [("Elite", "High", "Elite"), ("High", "High", "High"), ("Medium", "Low", "High"),
               ("Low", "Low", "Low"), ("High", None, None)]
    for i, (c1, c2, c3) in enumerate(classes):
        linha = {"full_name": f"r{i}", "unidades_release": 10 + i, "deployment_frequency_release": 0.2,
                 "lead_time_a_release": 10.0, "lead_time_b_release": 5.0,
                 "unidades_tag": 20 + i, "deployment_frequency_tag": 0.4,
                 "lead_time_a_tag": 8.0, "lead_time_b_tag": 4.0}
        for metrica in ("geral", "frequencia", "lead_time", "cfr", "recuperacao"):
            linha[f"classe_{metrica}_c1"] = c1
            linha[f"classe_{metrica}_c2"] = c2
            linha[f"classe_{metrica}_c3"] = c3
        linhas.append(linha)
    return pd.DataFrame(linhas)


def test_distribuicao_das_classes(variantes):
    dist = rq07.distribuicao(variantes).set_index("combinacao")
    assert dist.loc["C1", "n"] == 5
    assert dist.loc["C2", "n"] == 4
    assert dist.loc["C1", "High"] == pytest.approx(0.4)
    assert dist.loc["C3", "Elite"] == pytest.approx(0.25)


def test_comparar_par(variantes):
    resultado = rq07.comparar_par(variantes, "c1", "c2")
    assert resultado["n"] == 4
    assert resultado["mudou_de_classe"] == pytest.approx(0.5)
    assert resultado["desceu"] == pytest.approx(0.5)
    assert resultado["subiu"] == 0.0
    esperado = __import__("sklearn.metrics", fromlist=["x"]).cohen_kappa_score(
        [4, 3, 2, 1], [3, 3, 1, 1], weights="linear", labels=[1, 2, 3, 4])
    assert resultado["kappa_linear"] == pytest.approx(esperado)


def test_comparar_par_sem_dados_e_concordancia_total(variantes):
    vazio = variantes.assign(classe_geral_c2=None)
    assert rq07.comparar_par(vazio, "c1", "c2")["kappa_linear"] is None
    igual = variantes.assign(classe_geral_c2=variantes["classe_geral_c1"])
    assert rq07.comparar_par(igual, "c1", "c2")["kappa_linear"] == pytest.approx(1.0)


def test_transicoes_e_unidades(variantes):
    matriz = rq07.transicoes(variantes, "c1", "c3")
    assert list(matriz.index) == list(rq07.CLASSES)
    assert matriz.loc["Medium", "High"] == 1
    assert int(matriz.values.sum()) == 4
    tabela = rq07.unidades(variantes)
    assert set(tabela["unidade"]) == {"release", "tag"}
    tag = tabela[(tabela.unidade == "tag") & (tabela.metrica == "unidades")].iloc[0]
    assert tag["mediana"] == 22.0


@pytest.fixture
def valores():
    nan = float("nan")
    return pd.DataFrame([
        # C1: frequencia Medium, lead time Elite, CFR Elite, recuperacao Elite -> Elite
        {"full_name": "a/a", "unidades_release": 10, "deployment_frequency_release": 0.5,
         "lead_time_a_release": 10.0, "lead_time_b_release": 200.0, "cfr_b_release": 0.5,
         "unidades_release_pre": 12, "deployment_frequency_release_pre": 0.5,
         "lead_time_a_release_pre": 10.0, "cfr_b_release_pre": 0.2,
         "unidades_tag": 40, "deployment_frequency_tag": 8.0, "lead_time_a_tag": 10.0,
         "cfr_a": 0.1, "recuperacao_horas": 0.5, "classe_geral_c1": "Elite"},
        # sem variantes, sem CFR (b) e sem recuperacao: tudo Low
        {"full_name": "b/b", "unidades_release": 5, "deployment_frequency_release": 0.1,
         "lead_time_a_release": 800.0, "lead_time_b_release": 800.0, "cfr_b_release": nan,
         "unidades_release_pre": nan, "deployment_frequency_release_pre": nan,
         "lead_time_a_release_pre": nan, "cfr_b_release_pre": nan,
         "unidades_tag": nan, "deployment_frequency_tag": nan, "lead_time_a_tag": nan,
         "cfr_a": 0.5, "recuperacao_horas": nan, "classe_geral_c1": "Low"},
    ])


def test_classe_geral_em_qualquer_combinacao(valores):
    primeira, segunda = valores.iloc[0], valores.iloc[1]
    assert rq07.classe_geral(primeira, "release", "lead_time_a", "cfr_a") == "Elite"
    assert rq07.classe_geral(primeira, "release", "lead_time_b", "cfr_a") == "High"  # notas 2, 2, 4, 4
    assert rq07.classe_geral(primeira, "release", "lead_time_a", "cfr_b") == "High"  # notas 1, 2, 4, 4
    assert rq07.classe_geral(segunda, "release", "lead_time_a", "cfr_b") == "Low"
    assert rq07.classe_geral(segunda, "tag", "lead_time_a", "cfr_a") is None


def test_fatores_isolados(valores):
    tabela = rq07.fatores_isolados(valores).set_index("fator")
    assert list(tabela.index) == [nome for nome, *_ in rq07.FATORES]
    assert tabela.loc["unidade: tag", "n"] == 1
    assert tabela.loc["unidade: tag", "mudou_de_classe"] == 0.0
    assert tabela.loc["lead time (b)", "n"] == 2
    assert tabela.loc["lead time (b)", "desceu"] == pytest.approx(0.5)
    assert tabela.loc["CFR (b)", "mudou_de_classe"] == pytest.approx(0.5)


def test_rq07_main_grava_resultados(variantes, tmp_path, capsys):
    arquivo = tmp_path / "variantes.csv"
    variantes.to_csv(arquivo, index=False)
    rq07.main(["--variantes", str(arquivo), "--saida", str(tmp_path / "saida")])
    for nome in ("rq07_distribuicao.csv", "rq07_pares.csv", "rq07_unidades.csv", "rq07_fatores.csv",
                 "rq07_transicoes_c1_c2.csv", "rq07_transicoes.png", "rq07.md"):
        assert (tmp_path / "saida" / nome).exists()
    assert "Sensibilidade" in capsys.readouterr().out
