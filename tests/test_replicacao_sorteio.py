import json

import pandas as pd

from replicacao_cruzada import sorteio


def _dataset(n=40):
    return pd.DataFrame({
        "id": range(1, n + 1),
        "full_name": [f"o/r{i:02d}" for i in range(n)],
        "estrelas": range(1000, 1000 + n),
        "linguagem": ["Python" if i % 2 else None for i in range(n)],
    })


def test_sorteio_reproduzivel_e_formato_dos_candidatos():
    primeira = sorteio.sortear(_dataset(), 30, 42)
    segunda = sorteio.sortear(_dataset().sample(frac=1, random_state=7), 30, 42)
    assert len(primeira) == 30
    assert primeira["full_name"].tolist() == segunda["full_name"].tolist()
    lista = sorteio.candidatos(primeira)
    assert lista["total_candidatos"] == 30
    assert set(lista["candidatos"][0]) == {"id", "full_name", "html_url", "estrelas", "linguagem"}
    assert lista["candidatos"][0]["html_url"] == f"https://github.com/{lista['candidatos'][0]['full_name']}"
    assert any(c["linguagem"] is None for c in lista["candidatos"])


def test_sorteio_main(tmp_path):
    origem = tmp_path / "dataset.csv"
    _dataset().to_csv(origem, index=False)
    sorteio.main(["--dataset", str(origem), "--saida", str(tmp_path / "saida"), "--n", "5"])
    assert len(pd.read_csv(tmp_path / "saida" / "amostra_5.csv")) == 5
    with open(tmp_path / "saida" / "candidatos_5.json", encoding="utf-8") as f:
        assert len(json.load(f)["candidatos"]) == 5
