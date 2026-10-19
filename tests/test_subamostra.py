import pandas as pd

from pipeline import subamostra


def test_subamostra_reproduzivel(tmp_path):
    amostra = pd.DataFrame({"full_name": [f"o/r{i:02d}" for i in range(50)], "stars": range(50)})
    primeira = subamostra.sortear(amostra, 30, 42)
    segunda = subamostra.sortear(amostra.sample(frac=1, random_state=1), 30, 42)
    assert len(primeira) == 30
    assert primeira["full_name"].tolist() == segunda["full_name"].tolist()
    assert primeira["full_name"].tolist() == sorted(primeira["full_name"])
    assert len(subamostra.sortear(amostra, 80, 42)) == 50


def test_subamostra_com_limite_de_runs(tmp_path):
    origem = tmp_path / "amostra.csv"
    dataset = tmp_path / "dataset.csv"
    pd.DataFrame({"full_name": ["o/leve", "o/pesado", "o/medio"]}).to_csv(origem, index=False)
    pd.DataFrame({"full_name": ["o/leve", "o/pesado", "o/medio"],
                  "runs_total": [100, 400000, 5000]}).to_csv(dataset, index=False)
    saida = tmp_path / "sub.csv"
    subamostra.main(["--n", "5", "--amostra", str(origem), "--dataset", str(dataset),
                     "--max-runs", "20000", "--saida", str(saida)])
    assert sorted(pd.read_csv(saida)["full_name"]) == ["o/leve", "o/medio"]


def test_subamostra_main(tmp_path, capsys):
    origem = tmp_path / "amostra.csv"
    pd.DataFrame({"full_name": [f"o/r{i}" for i in range(10)]}).to_csv(origem, index=False)
    saida = tmp_path / "replicacao" / "amostra_3.csv"
    subamostra.main(["--n", "3", "--amostra", str(origem), "--saida", str(saida)])
    assert len(pd.read_csv(saida)) == 3
    assert "3 repositorios sorteados" in capsys.readouterr().out
