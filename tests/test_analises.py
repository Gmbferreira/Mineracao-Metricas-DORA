import pandas as pd
import pytest

from analises import comum, rq08_rework as rq08


def test_resumo_media_mediana_e_iqr():
    resultado = comum.resumo(pd.Series([1.0, 2.0, 3.0, 4.0, None]))
    assert resultado == {"n": 4, "media": 2.5, "mediana": 2.5, "moda": None,
                         "q1": 1.75, "q3": 3.25, "iqr": 1.5}
    assert comum.resumo(pd.Series([], dtype=float))["mediana"] is None


def test_moda():
    # cauda longa: a media sai de perto da mediana, e a moda fica no valor que mais se repete
    resultado = comum.resumo(pd.Series([0.0, 0.0, 0.0, 1.0, 2.0, 30.0]))
    assert resultado["moda"] == 0.0
    assert resultado["mediana"] == 0.5
    assert resultado["media"] == pytest.approx(5.5)
    assert comum.moda(pd.Series([3, 3, 1, 1, 2])) == 1  # empate: fica o menor
    assert comum.moda(pd.Series(["High", "Medium", "High", None])) == "High"
    assert comum.moda(pd.Series([1.5, 2.5])) is None


def test_tabela_markdown():
    texto = comum.tabela_markdown(pd.DataFrame({"a": ["x"], "b": [0.12345]}), casas=2)
    assert texto == "| a | b |\n|---|---|\n| x | 0.12 |\n"


@pytest.fixture
def dataset():
    return pd.DataFrame({
        "full_name": ["a/a", "b/b", "c/c", "d/d"],
        "releases_janela": [10, 4, 5, 8],
        "releases_corretivas": [5, 1, 0, 8],
        "cfr_b": [0.2, 0.25, None, 0.5],
    })


def test_rework_rate(dataset):
    tabela = rq08.rework_rate(dataset)
    assert tabela["rework_rate"].tolist() == [0.5, 0.25, 0.0, 1.0]


def test_comparacao_com_cfr_b(dataset):
    resultado = rq08.comparar(rq08.rework_rate(dataset))
    assert resultado["n"] == 3
    assert resultado["spearman_rho"] == pytest.approx(0.5)
    assert resultado["mediana_da_diferenca"] == pytest.approx(0.3)
    assert resultado["proporcao_rework_maior"] == pytest.approx(2 / 3)
    assert resultado["proporcao_rework_igual"] == pytest.approx(1 / 3)


def test_rq08_main_grava_resultados(dataset, tmp_path, capsys):
    arquivo = tmp_path / "dataset.csv"
    dataset.to_csv(arquivo, index=False)
    rq08.main(["--dataset", str(arquivo), "--saida", str(tmp_path / "saida")])
    for nome in ("rq08_rework_por_repositorio.csv", "rq08_resumo.csv", "rq08_comparacao.csv",
                 "rq08_rework_x_cfr_b.png", "rq08_distribuicao.png", "rq08.md"):
        assert (tmp_path / "saida" / nome).exists()
    resumos = pd.read_csv(tmp_path / "saida" / "rq08_resumo.csv").set_index("metrica")
    assert resumos.loc["rework_rate - cfr_b", "n"] == 3
    assert resumos.loc["rework_rate - cfr_b", "mediana"] == pytest.approx(0.3)
    assert "Rework rate" in capsys.readouterr().out
