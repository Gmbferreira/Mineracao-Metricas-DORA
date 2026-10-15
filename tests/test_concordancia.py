import pandas as pd
import pytest
from openpyxl import Workbook

from validacao import concordancia


def _caso(pares):
    """Dois avaliadores com os mesmos ids; `pares` = [(rotulo_a, rotulo_b), ...]."""
    return {
        "a": {"corretiva": pd.Series([p[0] for p in pares], dtype=object)},
        "b": {"corretiva": pd.Series([p[1] for p in pares], dtype=object)},
    }


def test_interpretacao_seguindo_landis_e_koch():
    assert concordancia.interpretar(-0.3) == "pobre"
    assert concordancia.interpretar(0.10) == "leve"
    assert concordancia.interpretar(0.21) == "razoavel"
    assert concordancia.interpretar(0.50) == "moderada"
    assert concordancia.interpretar(0.79) == "substancial"
    assert concordancia.interpretar(0.81) == "quase perfeita"
    assert concordancia.interpretar(1.0) == "quase perfeita"


def test_acordo_total_da_kappa_um():
    r = concordancia.calcular(_caso([("sim", "sim")] * 10 + [("nao", "nao")] * 10),
                              "corretiva")
    assert r["kappa"] == pytest.approx(1.0)
    assert r["concordancia_bruta"] == 1.0
    assert len(r["divergencias"]) == 0
    assert r["interpretacao"] == "quase perfeita"


def test_kappa_reproduz_o_calculo_manual():
    # 4 itens: 3 unanimes e 1 divergente -> p_o = 0,75, p_e = 0,53125,
    # kappa = (0,75 - 0,53125) / (1 - 0,53125) = 0,4667 (moderada)
    r = concordancia.calcular(_caso([("sim", "sim"), ("sim", "sim"),
                                     ("nao", "nao"), ("sim", "nao")]), "corretiva")
    assert r["kappa"] == pytest.approx(0.4667, abs=1e-4)
    assert r["concordancia_bruta"] == pytest.approx(0.75)
    assert r["interpretacao"] == "moderada"
    div = r["divergencias"]
    assert list(div["id"]) == [3]
    assert div.iloc[0]["a"] == "sim" and div.iloc[0]["b"] == "nao"


def test_quatro_categorias_usando_aggregate_raters():
    categorias = ["outro", "outro", "aplicacao/servico", "biblioteca/framework"]
    dados = {"a": {"tipo_projeto": pd.Series(categorias, dtype=object)},
             "b": {"tipo_projeto": pd.Series(categorias, dtype=object)}}
    r = concordancia.calcular(dados, "tipo_projeto")
    assert r["itens"] == 4
    assert r["avaliadores"] == 2
    assert r["kappa"] == 1.0


def test_categorias_com_maiuscula_sao_aceitas():
    # "ferramenta CLI" tem maiuscula na lista do sorteio; a comparacao e case-insensitive
    tipos = ["ferramenta CLI"] + ["outro"] * 59
    completos = {"tipo_projeto": pd.Series(tipos, dtype=object),
                 "entregas_reais": pd.Series(["sim"] * 60, dtype=object),
                 "corretiva": pd.Series(["nao"] * 300, dtype=object)}
    assert concordancia.conferir(completos) == []
    dados = {"a": {"tipo_projeto": pd.Series(["ferramenta CLI", "outro"], dtype=object)},
             "b": {"tipo_projeto": pd.Series(["ferramenta cli", "outro"], dtype=object)}}
    r = concordancia.calcular(dados, "tipo_projeto")
    assert r["kappa"] == 1.0


def test_ids_divergentes_entre_planilhas():
    dados = {"a": {"corretiva": pd.Series(["sim", "nao"], index=[1, 2], dtype=object)},
             "b": {"corretiva": pd.Series(["sim", "nao"], index=[1, 3], dtype=object)}}
    with pytest.raises(SystemExit, match="ids divergentes"):
        concordancia.calcular(dados, "corretiva")


def test_conferir_acusa_planilha_incompleta():
    rotulos = {"corretiva": pd.Series(["sim"] * 300, dtype=object),
               "tipo_projeto": pd.Series(["outro"] * 59 + [None], dtype=object),
               "entregas_reais": pd.Series(["sim"] * 60, dtype=object)}
    erros = concordancia.conferir(rotulos, "rotulos_x.xlsx")
    assert any("tipo_projeto: 59/60" in e for e in erros)


def test_conferir_acusa_valor_fora_da_lista():
    rotulos = {"corretiva": pd.Series(["talvez"] + ["sim"] * 299, dtype=object),
               "tipo_projeto": pd.Series(["outro"] * 60, dtype=object),
               "entregas_reais": pd.Series(["sim"] * 60, dtype=object)}
    erros = concordancia.conferir(rotulos, "rotulos_x.xlsx")
    assert any("valores fora da lista" in e for e in erros)


def test_conferir_planilha_pronta_nao_reclama():
    rotulos = {"corretiva": pd.Series(["sim"] * 300, dtype=object),
               "tipo_projeto": pd.Series(["outro"] + [None] * 59, dtype=object),
               "entregas_reais": pd.Series(["sim"] + [None] * 59, dtype=object)}
    erros = [e for e in concordancia.conferir(rotulos) if "corretiva" in e]
    assert erros == []


def _planilha_minima(caminho):
    livro = Workbook()
    repos = livro.active
    repos.title = "repositorios"
    repos.append(["id_repo", "repositorio", "link", "tipo_projeto",
                  "entregas_reais", "observacao"])
    repos.append([1, "o/r", "https://example.com", "outro", "sim", None])
    repos.append([2, "o/r2", "https://example.com", None, None, None])
    rels = livro.create_sheet("releases")
    rels.append(["id_release", "id_repo", "repositorio", "tag", "publicada_em",
                 "link_release", "link_commits", "corretiva", "observacao"])
    rels.append([1, 1, "o/r", "v1", "2025-01-01", "u", "u", "nao", None])
    livro.save(caminho)


def test_ler_planilha(tmp_path):
    caminho = tmp_path / "rotulos_teste.xlsx"
    _planilha_minima(caminho)
    rotulos = concordancia.ler_planilha(str(caminho))
    assert list(rotulos["tipo_projeto"].index) == [1, 2]
    assert rotulos["tipo_projeto"][1] == "outro"
    assert rotulos["tipo_projeto"][2] is None
    assert rotulos["corretiva"][1] == "nao"


def test_main_aborta_quando_planilha_falta(tmp_path):
    with pytest.raises(SystemExit, match="ausentes"):
        concordancia.main(diretorio=str(tmp_path), argv=[])


def test_main_aborta_com_rotulagem_incompleta(tmp_path):
    for nome in ("gabriel", "guilherme"):
        _planilha_minima(tmp_path / f"rotulos_{nome}.xlsx")
    with pytest.raises(SystemExit, match="incompleta"):
        concordancia.main(diretorio=str(tmp_path), argv=[])
