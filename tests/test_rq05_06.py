import math

import numpy as np
import pandas as pd
import pytest

from analises import rq05_06_relacoes as rq


def _linhas():
    """Vinte repositorios com metricas conhecidas.

    A frequencia cresce com o quartil de idade (1,5 / 3 / 4,5 / 6 releases por
    semana) e o lead time cai com ele, o que da um Kruskal-Wallis
    significativo e uma correlacao de Spearman negativa. Um repositorio fica
    sem CFR (b) e um sem tempo de recuperacao.
    """
    linhas = []
    for i in range(20):
        quartil = i % 4 + 1
        linhas.append({
            "full_name": f"org{i:02d}/repo{i:02d}",
            "deployment_frequency_semana": quartil * 1.5,
            "lead_time_a_horas": (5 - quartil) * 100 + i,
            "lead_time_b_horas": (5 - quartil) * 120 + i,
            "cfr_a": quartil / 10,
            "cfr_b": None if i == 3 else quartil / 5,
            "recuperacao_horas": None if i == 7 else quartil * 2.0,
            "linguagem": "Python" if i < 16 else "Ruby",
            "quartil_estrelas": quartil,
            "quartil_contribuidores": quartil,
            "quartil_idade": quartil,
            "stars": 1000 * quartil,
            "idade_anos": quartil * 2.0,
            "contributors": 100 * quartil,
        })
    return linhas


@pytest.fixture
def dataset():
    return pd.DataFrame(_linhas())


@pytest.fixture
def consenso():
    """Rotulo de tipo de projeto da amostra-ouro, para os mesmos repositorios."""
    return pd.DataFrame({
        "full_name": [f"org{i:02d}/repo{i:02d}" for i in range(20)],
        "tipo_projeto": ["biblioteca/framework" if i % 2 else "aplicacao/servico"
                         for i in range(20)],
        "entregas_reais": ["sim"] * 20,
    })


def test_correlacoes_rho_perfeito():
    dados = pd.DataFrame({
        "deployment_frequency_semana": [1, 2, 3, 4, 5],
        "cfr_a": [2, 4, 6, 8, 10],
        "cfr_b": [10, 8, 6, 4, 2],
        "lead_time_a_horas": [5, 4, 3, 2, 1],
        "lead_time_b_horas": [1, 2, 3, 4, 5],
        "recuperacao_horas": [1, 2, 3, 4, 5],
    })
    tabela = rq.correlacoes(dados).set_index("metrica_y")
    assert tabela.loc["cfr_a", "rho"] == pytest.approx(1.0)
    assert tabela.loc["cfr_b", "rho"] == pytest.approx(-1.0)
    assert tabela.loc["lead_time_a", "rho"] == pytest.approx(-1.0)
    assert tabela.loc["cfr_a", "n"] == 5
    assert tabela.loc["cfr_a", "p"] < 0.05
    assert tabela.loc["cfr_a", "forca"] == "forte"


def test_correlacoes_ignora_valor_ausente():
    dados = pd.DataFrame({
        "deployment_frequency_semana": [1, 2, 3, 4],
        "cfr_a": [1, 2, 3, 4],
        "cfr_b": [1, None, 3, 4],
        "lead_time_a_horas": [1, 2, 3, 4],
        "lead_time_b_horas": [1, 2, 3, 4],
        "recuperacao_horas": [1, 2, 3, 4],
    })
    tabela = rq.correlacoes(dados).set_index("metrica_y")
    assert tabela.loc["cfr_b", "n"] == 3
    assert tabela.loc["cfr_a", "n"] == 4


def test_correcao_de_holm_aumenta_o_p(dataset):
    tabela = rq.correlacoes(dataset)
    assert (tabela["p_holm"] >= tabela["p"]).all()


def test_holm_ordena_os_p_valores():
    """Exemplo calculado a mao: Holm sobre 0,01 / 0,02 / 0,03 da 0,03 / 0,04 / 0,04."""
    tabela = pd.DataFrame({"familia": ["x", "x", "x"], "p": [0.01, 0.02, 0.03]})
    corrigida = rq.corrigir_holm(tabela)
    assert list(corrigida["p_holm"]) == pytest.approx([0.03, 0.04, 0.04])


def test_holm_corrige_so_dentro_da_familia():
    tabela = pd.DataFrame({
        "familia": ["x", "x", "y"],
        "p": [0.01, 0.02, 0.03],
    })
    corrigida = rq.corrigir_holm(tabela)
    assert corrigida.loc[0, "p_holm"] == pytest.approx(0.02)
    assert corrigida.loc[1, "p_holm"] == pytest.approx(0.02)
    assert corrigida.loc[2, "p_holm"] == pytest.approx(0.03)


def test_matriz_spearman():
    dados = pd.DataFrame({
        "deployment_frequency_semana": [1, 2, 3, 4, 5],
        "cfr_a": [2, 4, 6, 8, 10],
        "cfr_b": [10, 8, 6, 4, 2],
        "lead_time_a_horas": [5, 4, 3, 2, 1],
        "lead_time_b_horas": [1, 2, 3, 4, 5],
        "recuperacao_horas": [1, 2, 3, 4, 5],
    })
    matriz = rq.matriz_spearman(dados)
    assert matriz.shape == (6, 6)
    assert np.allclose(np.diag(matriz.values), 1.0)
    assert matriz.loc["cfr_a", "cfr_b"] == pytest.approx(matriz.loc["cfr_b", "cfr_a"])


def test_cfr_por_faixa_ordenado_e_com_as_medianas():
    """Duas releases por faixa: o CFR (b) sobe com a cadencia, o (a) nao."""
    dados = pd.DataFrame({
        "deployment_frequency_semana": [0.1, 0.1, 0.5, 0.5, 2.0, 2.0, 10.0, 10.0],
        "cfr_a": [0.02, 0.04, 0.03, 0.05, 0.06, 0.08, 0.05, 0.07],
        "cfr_b": [0.0, 0.0, 0.1, 0.3, 0.4, 0.6, 0.5, None],
    })
    tabela = rq.cfr_por_faixa(dados).set_index("faixa")
    assert list(tabela.index) == ["Low", "Medium", "High", "Elite"]
    assert tabela.loc["Low", "n"] == 2
    assert tabela.loc["Low", "cfr_b_mediana"] == pytest.approx(0.0)
    assert tabela.loc["Low", "cfr_b_zero"] == pytest.approx(1.0)
    assert tabela.loc["Medium", "cfr_b_mediana"] == pytest.approx(0.2)
    assert tabela.loc["High", "cfr_b_mediana"] == pytest.approx(0.5)
    assert tabela.loc["High", "cfr_b_zero"] == pytest.approx(0.0)
    assert tabela.loc["Medium", "cfr_a_mediana"] == pytest.approx(0.04)
    assert tabela.loc["Elite", "cfr_b_n"] == 1
    assert tabela["cfr_b_mediana"].is_monotonic_increasing


def test_cfr_por_faixa_ignora_frequencia_ausente():
    dados = pd.DataFrame({
        "deployment_frequency_semana": [None, 0.5],
        "cfr_a": [0.5, 0.04],
        "cfr_b": [0.5, 0.2],
    })
    tabela = rq.cfr_por_faixa(dados).set_index("faixa")
    assert tabela.loc["Medium", "n"] == 1
    assert tabela.loc["Elite", "n"] == 0
    assert math.isnan(tabela.loc["Elite", "cfr_b_mediana"])


def test_p_valor_do_rotulo():
    assert rq._p_valor(0.00519) == "p = 0,005"
    assert rq._p_valor(2.52e-27) == "p < 0,001"
    assert rq._p_valor(float("nan")) == "-"


def test_cliffs_delta_nos_extremos():
    assert rq.cliffs_delta([1, 2, 3], [4, 5, 6]) == pytest.approx(-1.0)
    assert rq.cliffs_delta([4, 5, 6], [1, 2, 3]) == pytest.approx(1.0)
    assert rq.cliffs_delta([1, 2, 3], [1, 2, 3]) == pytest.approx(0.0)


def test_forca_do_delta():
    assert rq.forca_delta(0.1) == "desprezivel"
    assert rq.forca_delta(0.2) == "pequeno"
    assert rq.forca_delta(0.4) == "medio"
    assert rq.forca_delta(0.6) == "grande"


def test_forca_do_eps2():
    assert rq.forca_eps2(0.005) == "desprezivel"
    assert rq.forca_eps2(0.03) == "pequeno"
    assert rq.forca_eps2(0.1) == "medio"
    assert rq.forca_eps2(0.35) == "grande"


def test_comparar_grupos_com_kruskal_wallis(dataset):
    serie = dataset["quartil_idade"]
    tabela = rq.comparar_grupos(dataset, serie, "quartil_idade",
                                "Idade do repositorio (quartis)", ["frequencia"])
    linha = tabela.iloc[0]
    assert linha["teste"] == "Kruskal-Wallis"
    assert linha["n"] == 20
    assert linha["n_grupos"] == 4
    assert linha["p"] < 0.05
    assert linha["eps2"] == pytest.approx(linha["H"] / (20 - 1))
    assert linha["tamanho"] in {"desprezivel", "pequeno", "medio", "grande"}
    assert linha["nota"] == ""


def test_comparar_grupos_com_mann_whitney_em_dois_grupos(dataset):
    """Com dois grupos o teste e Mann-Whitney e o efeito e o Cliff's delta."""
    serie = dataset["quartil_idade"].apply(lambda v: "jovem" if v <= 2 else "velho")
    tabela = rq.comparar_grupos(dataset, serie, "faixa_idade", "Idade", ["frequencia"])
    linha = tabela.iloc[0]
    assert linha["teste"] == "Mann-Whitney"
    assert linha["n_grupos"] == 2
    assert linha["delta"] == pytest.approx(rq.cliffs_delta(
        dataset.loc[serie == "jovem", "deployment_frequency_semana"],
        dataset.loc[serie == "velho", "deployment_frequency_semana"]))
    assert linha["tamanho"] in {"desprezivel", "pequeno", "medio", "grande"}


def test_grupo_com_um_somente_repositorio_e_descartado(dataset):
    """Grupo de n=1 nao entra no teste, e o resto continua."""
    serie = dataset["quartil_idade"].astype(str).copy()
    serie.iloc[0] = "sozinho"
    tabela = rq.comparar_grupos(dataset, serie, "quartil_idade", "Idade", ["frequencia"])
    linha = tabela.iloc[0]
    assert linha["n_grupos"] == 4          # o grupo de n=1 ficou de fora
    assert linha["n"] == 19
    assert linha["teste"] == "Kruskal-Wallis"
    assert "sozinho" not in linha["grupos"]


def test_fator_sem_dois_grupos_nao_quebra(dataset):
    serie = pd.Series(["unico"] * 20)
    tabela = rq.comparar_grupos(dataset, serie, "vazio", "Vazio", ["frequencia"])
    linha = tabela.iloc[0]
    assert linha["n_grupos"] == 1
    assert math.isnan(linha["p"])
    assert linha["nota"] == "menos de dois grupos com dados"


def test_corte_de_linguagem_descarta_as_pequenas(dataset, consenso):
    fatores = rq.montar_fatores(dataset, consenso)
    assert fatores["linguagem"].notna().sum() == 16      # so Python tem n >= 15
    assert fatores["linguagem"].dropna().unique().tolist() == ["Python"]
    descricao = rq.descricao_fatores(dataset, fatores).set_index("fator")
    assert descricao.loc["linguagem", "n"] == 16
    assert "4 repositorios fora do fator" in descricao.loc["linguagem", "observacao"]


def test_tipo_de_projeto_vem_do_consenso(dataset, consenso):
    fatores = rq.montar_fatores(dataset, consenso)
    assert fatores["tipo_projeto"].notna().sum() == 20
    assert set(fatores["tipo_projeto"].dropna()) == {"biblioteca/framework", "aplicacao/servico"}


def test_quartis_mantem_os_grupos(dataset, consenso):
    fatores = rq.montar_fatores(dataset, consenso)
    assert fatores["quartil_idade"].notna().sum() == 20
    rotulos = rq.rotulos_grupos("quartil_idade", fatores["quartil_idade"])
    assert sorted(rotulos.values()) == ["Q1", "Q2", "Q3", "Q4"]


def test_medianas_por_grupo(dataset, consenso):
    fatores = rq.montar_fatores(dataset, consenso)
    tabela = rq.medianas_por_grupo(dataset, fatores)
    linha = tabela[(tabela["fator"] == "quartil_idade") & (tabela["metrica"] == "frequencia")
                   & (tabela["grupo"] == "Q1")].iloc[0]
    assert linha["n"] == 5
    assert linha["mediana"] == pytest.approx(1.5)
    assert linha["iqr"] == pytest.approx(0.0)


def test_pos_hoc_para_os_testes_significativos(dataset, consenso):
    fatores = rq.montar_fatores(dataset, consenso)
    grupos = rq.comparar_fatores(dataset, fatores)
    pos = rq.pos_hoc(dataset, fatores, grupos)
    assert not pos.empty
    assert "frequencia" in set(pos["metrica"])
    assert (pos["p_holm"] >= pos["p"]).all()
    assert (pos["n_a"] >= 2).all() and (pos["n_b"] >= 2).all()
    assert pos["delta"].abs().max() <= 1.0
    assert set(pos["tamanho"]) <= {"desprezivel", "pequeno", "medio", "grande"}


def test_pos_hoc_vazio_sem_teste_significativo(dataset, consenso):
    """Sem combinacao significativa nao ha comparacao par a par."""
    fatores = rq.montar_fatores(dataset, consenso)
    grupos = rq.comparar_fatores(dataset, fatores).copy()
    grupos["p_holm"] = float("nan")
    pos = rq.pos_hoc(dataset, fatores, grupos)
    assert pos.empty
    assert "p_holm" in pos.columns


def test_formatacao_no_formato_brasileiro():
    assert rq._formatar(0.5, 3) == "0,5"
    assert rq._formatar(2.0, 3) == "2"
    assert rq._formatar(float("nan"), 3) == "-"
    assert rq._formatar(None, 3) == "-"
    assert "e-" in rq._formatar(2.52e-27, 5)
    assert rq._ptbr(47785, 0) == "47.785"
    assert rq._ptbr(2.5, 1) == "2,5"


def test_main_grava_resultados(dataset, consenso, tmp_path, capsys):
    arquivo = tmp_path / "dataset.csv"
    arquivo_consenso = tmp_path / "consenso.csv"
    dataset.to_csv(arquivo, index=False)
    consenso.to_csv(arquivo_consenso, index=False)
    saida = tmp_path / "saida"
    rq.main(["--dataset", str(arquivo), "--consenso", str(arquivo_consenso),
             "--saida", str(saida)])
    for nome in ("rq05_06.md", "rq05_spearman.csv", "rq05_matriz_spearman.csv",
                 "rq05_cfr_por_faixa.csv", "rq05_dispersao.png", "rq06_grupos.csv",
                 "rq06_medianas.csv", "rq06_pos_hoc.csv", "rq06_efeitos.png"):
        assert (saida / nome).exists()
    assert "RQ 05" in capsys.readouterr().out
