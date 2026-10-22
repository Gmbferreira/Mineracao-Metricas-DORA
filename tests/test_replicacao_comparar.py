import pandas as pd
import pytest

from replicacao_cruzada import comparar


def test_diferenca_relativa():
    assert comparar.diferenca_relativa(10.0, 11.0) == pytest.approx(0.1)
    assert comparar.diferenca_relativa(10.0, 9.0) == pytest.approx(-0.1)
    assert comparar.diferenca_relativa(0.0, 0.0) == 0.0
    assert comparar.diferenca_relativa(0.0, 5.0) is None
    assert comparar.diferenca_relativa(None, 5.0) is None


def test_classe_geral_pela_regra_da_disciplina():
    linha = {"classe_deployment_frequency": "Elite", "classe_lead_time_a": "High",
             "classe_cfr_a": "High", "classe_tempo_recuperacao": "Low"}
    assert comparar.classe_geral(linha) == "High"  # notas 4, 3, 3, 1
    linha["classe_tempo_recuperacao"] = None
    assert comparar.classe_geral(linha) == "High"  # notas 4, 3, 3


def _csv(valores_df, classes_df):
    linhas = []
    for i, (df, classe) in enumerate(zip(valores_df, classes_df)):
        linha = {"full_name": f"o/r{i}"}
        for metrica in comparar.METRICAS:
            linha[metrica] = df if metrica == "deployment_frequency" else 1.0
            linha[f"classe_{metrica}"] = classe if metrica == "deployment_frequency" else "High"
        linhas.append(linha)
    return pd.DataFrame(linhas)


def test_comparacao_entre_original_e_replicado(tmp_path):
    original = _csv([1.0, 2.0, 0.0], ["High", "High", "Low"])
    replicado = _csv([1.0, 2.2, 0.0], ["High", "High", "Medium"])
    original.to_csv(tmp_path / "o.csv", index=False)
    replicado.to_csv(tmp_path / "r.csv", index=False)
    comparar.main(["--original", str(tmp_path / "o.csv"), "--replicado", str(tmp_path / "r.csv"),
                   "--saida", str(tmp_path / "saida")])
    resumo = pd.read_csv(tmp_path / "saida" / "comparacao_resumo.csv").set_index("metrica")
    df = resumo.loc["deployment_frequency"]
    assert df["pares"] == 3
    assert df["dif_rel_max"] == pytest.approx(0.1)
    assert df["ate_1pct"] == pytest.approx(2 / 3)
    assert df["mesma_classe"] == pytest.approx(2 / 3)
    assert resumo.loc["lead_time_a", "mesma_classe"] == 1.0
    assert (tmp_path / "saida" / "comparacao_por_repositorio.csv").exists()
    assert (tmp_path / "saida" / "comparacao.md").exists()
