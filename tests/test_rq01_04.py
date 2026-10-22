import pandas as pd
import pytest

from analises import rq01_04_metricas as rq01
from metricas import classificacao


@pytest.fixture
def dataset():
    """Quatro repositorios com as classes ja classificadas a mao.

    a/a: freq Medium, lead time Elite, CFR Elite, recuperacao Elite -> Elite
    b/b: freq High, lead time High, CFR High, recuperacao High -> High
    c/c: freq Elite, lead time High, CFR Low, recuperacao Medium -> Medium
    d/d: freq Low, lead time Low, CFR Elite, sem recuperacao -> Low
    """
    return pd.DataFrame({
        "full_name": ["a/a", "b/b", "c/c", "d/d"],
        "deployment_frequency_semana": [0.5, 2.0, 8.0, 0.1],
        "lead_time_a_horas": [10.0, 48.0, 100.0, 1000.0],
        "lead_time_b_horas": [5.0, 24.0, 200.0, 800.0],
        "cfr_a": [0.1, 0.2, 0.5, 0.05],
        "cfr_b": [0.25, 0.5, None, 0.1],
        "recuperacao_horas": [0.5, 5.0, 30.0, None],
        "episodios": [4, 2, 3, 0],
        "episodios_censurados": [0, 1, 0, 0],
        "proporcao_censurados": [0.0, 0.5, 0.0, None],
        "falhas_sem_inicio": [1, 0, 2, 0],
        "releases_censuradas_cfr_b": [1, 0, 0, 0],
        "releases_avaliadas_cfr_b": [9, 8, 7, 6],
        "classe_frequencia": ["Medium", "High", "Elite", "Low"],
        "classe_lead_time": ["Elite", "High", "High", "Low"],
        "classe_cfr": ["Elite", "High", "Low", "Elite"],
        "classe_recuperacao": ["Elite", "High", "Medium", None],
        "classe_geral": ["Elite", "High", "Medium", "Low"],
    })


def test_resumo_metricas(dataset):
    tabela = rq01.resumo_metricas(dataset).set_index("metrica")
    frequencia = tabela.loc["frequencia"]
    assert frequencia["n"] == 4
    assert frequencia["mediana"] == pytest.approx(1.25)
    assert frequencia["iqr"] == pytest.approx(frequencia["q3"] - frequencia["q1"])
    assert pd.isna(frequencia["mediana_dias"])


def test_resumo_conta_valores_ausentes(dataset):
    tabela = rq01.resumo_metricas(dataset).set_index("metrica")
    assert tabela.loc["cfr_b"]["n"] == 3          # c/c nao tem CFR (b)
    assert tabela.loc["recuperacao"]["n"] == 3    # d/d nao tem tempo de recuperacao
    assert tabela.loc["lead_time_b"]["mediana"] == pytest.approx(112.0)


def test_resumo_em_dias_so_para_metricas_em_horas(dataset):
    tabela = rq01.resumo_metricas(dataset).set_index("metrica")
    lead = tabela.loc["lead_time_a"]
    assert lead["mediana"] == pytest.approx(74.0)
    assert lead["mediana_dias"] == pytest.approx(74.0 / 24)
    assert lead["iqr_dias"] == pytest.approx(lead["iqr"] / 24)
    assert pd.isna(tabela.loc["cfr_a"]["mediana_dias"])


def test_pares_variantes(dataset):
    tabela = rq01.pares_variantes(dataset).set_index("par")
    lead = tabela.loc["lead_time (a) x (b)"]
    assert lead["n"] == 4
    assert lead["mediana_a"] == pytest.approx(74.0)
    assert lead["mediana_b"] == pytest.approx(112.0)
    assert lead["proporcao_b_maior"] == pytest.approx(0.25)
    assert lead["razao_mediana_b_a"] == pytest.approx(0.65)
    assert lead["diferenca_mediana_b_a"] == pytest.approx(-14.5)
    cfr = tabela.loc["cfr (a) x (b)"]
    assert cfr["n"] == 3
    assert cfr["proporcao_b_maior"] == pytest.approx(1.0)
    assert cfr["razao_mediana_b_a"] == pytest.approx(2.5)
    assert cfr["diferenca_mediana_b_a"] == pytest.approx(0.15)


def test_pares_variantes_sem_razao_quando_a_tem_zero():
    """No CFR ha repositorios com (a) = 0: a razao (b)/(a) nao e calculada."""
    dados = pd.DataFrame({"cfr_a": [0.0, 0.2], "cfr_b": [0.1, 0.1]})
    tabela = rq01.pares_variantes(dados).set_index("par")
    assert pd.isna(tabela.loc["cfr (a) x (b)", "razao_mediana_b_a"])


def test_censura_dos_episodios(dataset):
    tabela = rq01.censura(dataset).set_index("indicador")
    assert tabela.loc["episodios no total", "valor"] == 9
    assert tabela.loc["episodios censurados", "valor"] == 1
    assert tabela.loc["proporcao censurada agregada", "valor"] == pytest.approx(1 / 9)
    assert tabela.loc["repositorios com ao menos um episodio censurado", "valor"] == 1
    assert tabela.loc["proporcao desses repositorios", "valor"] == pytest.approx(1 / 3)
    assert tabela.loc["repositorios com todos os episodios censurados", "valor"] == 0


def test_repositorio_sem_episodio_nao_entra_como_zero(dataset):
    """d/d nao tem episodio: nao pode virar "0% censurados"."""
    tabela = rq01.censura(dataset).set_index("indicador")
    assert tabela.loc["repositorios sem episodio de falha", "valor"] == 1
    assert tabela.loc["repositorios com tempo de recuperacao", "valor"] == 3
    # a proporcao de d/d e NaN e fica fora do resumo por repositorio
    assert tabela.loc["mediana da proporcao", "valor"] == 0.0
    assert tabela.loc["q3 da proporcao", "valor"] == pytest.approx(0.25)


def test_censura_das_releases_do_cfr_b(dataset):
    tabela = rq01.censura(dataset).set_index("indicador")
    assert tabela.loc["releases censuradas", "valor"] == 1
    assert tabela.loc["releases avaliadas", "valor"] == 30
    assert tabela.loc["repositorios sem CFR (b)", "valor"] == 1


def test_classes_dora(dataset):
    tabela = rq01.classes_dora(dataset).set_index("metrica")
    geral = tabela.loc["geral"]
    assert geral["n"] == 4
    assert geral["sem_valor"] == 0
    assert geral["Elite"] == pytest.approx(0.25)
    assert geral["Low"] == pytest.approx(0.25)


def test_classe_sem_valor_fora_do_denominador(dataset):
    tabela = rq01.classes_dora(dataset).set_index("metrica")
    recuperacao = tabela.loc["recuperacao"]
    assert recuperacao["n"] == 3
    assert recuperacao["sem_valor"] == 1
    assert recuperacao["Elite"] == pytest.approx(1 / 3)
    assert recuperacao["Medium"] == pytest.approx(1 / 3)


def test_numero_trata_nan_como_none():
    assert rq01.numero(float("nan")) is None
    assert rq01.numero(None) is None
    assert rq01.numero(1.5) == 1.5


def test_metrica_sem_valor_nao_vira_classe_low(dataset):
    """NaN cru passaria pelas faixas e cairia em "Low" em vez de ficar vazia."""
    linha = dataset.iloc[3]
    classes = classificacao.classificar_repositorio(
        rq01.numero(linha["deployment_frequency_semana"]),
        rq01.numero(linha["lead_time_a_horas"]),
        rq01.numero(linha["cfr_a"]),
        rq01.numero(linha["recuperacao_horas"]),
    )
    assert classes["classe_recuperacao"] == ""
    assert classes["metricas_classificadas"] == 3


def test_conferir_classificacao_sem_divergencias(dataset):
    assert rq01.conferir_classificacao(dataset).empty


def test_conferir_classificacao_acha_divergencia(dataset):
    errado = dataset.assign(classe_geral="Elite")
    divergencias = rq01.conferir_classificacao(errado)
    assert len(divergencias) == 3
    assert set(divergencias["coluna"]) == {"classe_geral"}


def test_main_grava_resultados(dataset, tmp_path, capsys):
    arquivo = tmp_path / "dataset.csv"
    dataset.to_csv(arquivo, index=False)
    rq01.main(["--dataset", str(arquivo), "--saida", str(tmp_path / "saida")])
    for nome in ("rq01_04_resumo.csv", "rq01_04_pares.csv", "rq01_04_censura.csv",
                 "rq01_04_classes.csv", "rq01_04_distribuicao.png", "rq01_04_classes.png",
                 "rq01_04.md"):
        assert (tmp_path / "saida" / nome).exists()
    assert "classificação DORA" in capsys.readouterr().out
