import os

import pandas as pd
import pytest

from analises import rq07_sensibilidade as rq07

CAMINHO_VARIANTES = os.path.join(os.path.dirname(__file__), os.pardir, "data", "variantes.csv")


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
    assert dist.loc["C1", "moda"] == "High"


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


def test_classes_combinacao_devolve_as_cinco_classes(valores):
    primeira, segunda = valores.iloc[0], valores.iloc[1]
    classes = rq07.classes_combinacao(primeira, "release", "lead_time_a", "cfr_a")
    assert classes == {"frequencia": "Medium", "lead_time": "Elite", "cfr": "Elite",
                       "recuperacao": "Elite", "geral": "Elite"}
    assert rq07.classe_geral(primeira, "release", "lead_time_a", "cfr_a") == classes["geral"]
    sem_cfr = rq07.classes_combinacao(segunda, "release", "lead_time_a", "cfr_b")
    assert sem_cfr["cfr"] is None
    assert sem_cfr["frequencia"] == "Low"
    assert sem_cfr["geral"] == "Low"


def test_classes_combinacao_sem_dado_da_unidade(valores):
    classes = rq07.classes_combinacao(valores.iloc[1], "tag", "lead_time_a", "cfr_a")
    assert set(classes) == set(rq07.METRICAS_ORDEM)
    assert set(classes.values()) == {None}


def test_distribuicao_metricas(variantes):
    tabela = rq07.distribuicao_metricas(variantes)
    assert len(tabela) == len(rq07.METRICAS_ORDEM) * len(rq07.COMBINACOES)
    geral = tabela[tabela.metrica == "geral"].set_index("combinacao")
    dist = rq07.distribuicao(variantes).set_index("combinacao")
    for combinacao in ("C1", "C2", "C3"):
        assert geral.loc[combinacao, "n"] == dist.loc[combinacao, "n"]
        assert geral.loc[combinacao, "Elite"] == pytest.approx(dist.loc[combinacao, "Elite"])
        assert geral.loc[combinacao, "moda"] == dist.loc[combinacao, "moda"]
    recuperacao = tabela[tabela.metrica == "recuperacao"].set_index("combinacao")
    assert recuperacao.loc["C1", "n"] == 5
    assert recuperacao.loc["C2", "n"] == 4


def test_distribuicao_metricas_ignora_coluna_ausente(variantes):
    sem_c3 = variantes.drop(columns=[f"classe_{metrica}_c3" for metrica in rq07.METRICAS_ORDEM])
    tabela = rq07.distribuicao_metricas(sem_c3)
    assert "C3" not in set(tabela["combinacao"])
    assert len(tabela) == len(rq07.METRICAS_ORDEM) * 2


@pytest.fixture
def valores_metricas():
    """Repositorios com as classes por metrica da C1, para medir a migracao."""
    nan = float("nan")
    return pd.DataFrame([
        {"full_name": "a/a", "unidades_release": 10, "deployment_frequency_release": 0.5,
         "lead_time_a_release": 10.0, "lead_time_b_release": 200.0, "cfr_b_release": 0.5,
         "unidades_release_pre": 12, "deployment_frequency_release_pre": 0.5,
         "lead_time_a_release_pre": 10.0, "cfr_b_release_pre": 0.2,
         "unidades_tag": 40, "deployment_frequency_tag": 8.0, "lead_time_a_tag": 10.0,
         "cfr_a": 0.1, "recuperacao_horas": 0.5,
         "classe_frequencia_c1": "Medium", "classe_lead_time_c1": "Elite",
         "classe_cfr_c1": "Elite", "classe_recuperacao_c1": "Elite",
         "classe_geral_c1": "Elite"},
        {"full_name": "b/b", "unidades_release": 5, "deployment_frequency_release": 0.1,
         "lead_time_a_release": 800.0, "lead_time_b_release": 800.0, "cfr_b_release": nan,
         "unidades_release_pre": nan, "deployment_frequency_release_pre": nan,
         "lead_time_a_release_pre": nan, "cfr_b_release_pre": nan,
         "unidades_tag": nan, "deployment_frequency_tag": nan, "lead_time_a_tag": nan,
         "cfr_a": 0.5, "recuperacao_horas": nan,
         "classe_frequencia_c1": "Low", "classe_lead_time_c1": "Low",
         "classe_cfr_c1": "Low", "classe_recuperacao_c1": None,
         "classe_geral_c1": "Low"},
    ])


def test_fatores_metricas_isola_a_metrica_trocada(valores_metricas):
    tabela = rq07.fatores_metricas(valores_metricas).set_index(["fator", "metrica"])
    assert tabela.loc[("CFR (b)", "cfr"), "n"] == 1
    assert tabela.loc[("CFR (b)", "cfr"), "mudou_de_classe"] == 1.0
    assert tabela.loc[("CFR (b)", "cfr"), "desceu"] == 1.0
    assert tabela.loc[("CFR (b)", "cfr"), "subiu"] == 0.0
    assert tabela.loc[("CFR (b)", "frequencia"), "mudou_de_classe"] == 0.0
    assert tabela.loc[("CFR (b)", "lead_time"), "mudou_de_classe"] == 0.0
    assert tabela.loc[("CFR (b)", "recuperacao"), "mudou_de_classe"] == 0.0
    assert tabela.loc[("CFR (b)", "geral"), "mudou_de_classe"] == pytest.approx(0.5)
    assert tabela.loc[("CFR (b)", "geral"), "desceu"] == pytest.approx(0.5)


def test_fatores_metricas_troca_de_unidade_sobe_na_frequencia(valores_metricas):
    tabela = rq07.fatores_metricas(valores_metricas).set_index(["fator", "metrica"])
    assert tabela.loc[("unidade: tag", "frequencia"), "n"] == 1
    assert tabela.loc[("unidade: tag", "frequencia"), "subiu"] == 1.0
    assert tabela.loc[("unidade: tag", "frequencia"), "desceu"] == 0.0
    assert tabela.loc[("unidade: tag", "cfr"), "mudou_de_classe"] == 0.0
    assert tabela.loc[("unidade: tag", "geral"), "mudou_de_classe"] == 0.0


def test_fatores_metricas_troca_do_lead_time_sobe_e_desce(valores_metricas):
    tabela = rq07.fatores_metricas(valores_metricas).set_index(["fator", "metrica"])
    lead = tabela.loc[("lead time (b)", "lead_time")]
    assert lead["n"] == 2
    assert lead["mudou_de_classe"] == pytest.approx(0.5)
    assert lead["desceu"] == pytest.approx(0.5)
    assert lead["subiu"] == 0.0
    assert tabela.loc[("lead time (b)", "frequencia"), "mudou_de_classe"] == 0.0


@pytest.mark.skipif(not os.path.exists(CAMINHO_VARIANTES), reason="sem data/variantes.csv")
def test_classes_da_c1_recalculadas_batem_com_o_csv():
    variantes = pd.read_csv(CAMINHO_VARIANTES)
    for metrica in rq07.METRICAS_ORDEM:
        recalculadas = [rq07.classes_combinacao(linha, "release", "lead_time_a", "cfr_a")[metrica]
                        or "" for _, linha in variantes.iterrows()]
        esperadas = [valor or "" for valor in variantes[f"classe_{metrica}_c1"].fillna("")]
        assert recalculadas == esperadas


@pytest.mark.skipif(not os.path.exists(CAMINHO_VARIANTES), reason="sem data/variantes.csv")
def test_migracao_por_metrica_no_dado_real():
    variantes = pd.read_csv(CAMINHO_VARIANTES)
    tabela = rq07.fatores_metricas(variantes).set_index(["fator", "metrica"])
    assert tabela.loc[("CFR (b)", "cfr"), "desceu"] == pytest.approx(0.575, abs=1e-3)
    assert tabela.loc[("CFR (b)", "cfr"), "subiu"] == pytest.approx(0.080, abs=1e-3)
    assert tabela.loc[("lead time (b)", "lead_time"), "mudou_de_classe"] == pytest.approx(0.407, abs=1e-3)
    assert tabela.loc[("unidade: tag", "frequencia"), "subiu"] == pytest.approx(0.250, abs=1e-3)
    assert tabela.loc[("unidade: release + pre-release", "cfr"), "mudou_de_classe"] == 0.0


def test_rq07_main_grava_resultados(variantes, tmp_path, capsys):
    arquivo = tmp_path / "variantes.csv"
    variantes.to_csv(arquivo, index=False)
    rq07.main(["--variantes", str(arquivo), "--saida", str(tmp_path / "saida")])
    for nome in ("rq07_distribuicao.csv", "rq07_pares.csv", "rq07_unidades.csv", "rq07_fatores.csv",
                 "rq07_classes_metricas.csv", "rq07_fatores_metricas.csv",
                 "rq07_transicoes_c1_c2.csv", "rq07_transicoes.png", "rq07_classes_e_unidades.png",
                 "rq07_migracao_metricas.png", "rq07.md"):
        assert (tmp_path / "saida" / nome).exists()
    saida = capsys.readouterr().out
    assert "Sensibilidade" in saida
    assert "Classes por métrica" in saida
    assert "Um fator de cada vez, por métrica" in saida
