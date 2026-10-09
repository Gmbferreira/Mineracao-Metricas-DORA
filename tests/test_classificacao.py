import pytest

from metricas import classificacao as c


@pytest.mark.parametrize("valor, nota", [
    (7, 4), (10, 4), (6.99, 3), (1, 3), (0.99, 2), (0.23, 2), (0.22, 1), (0, 1), (None, None),
])
def test_nota_frequencia(valor, nota):
    assert c.nota_frequencia(valor) == nota


@pytest.mark.parametrize("horas, nota", [
    (0, 4), (23.9, 4), (24, 3), (167.9, 3), (168, 2), (719, 2), (720, 1), (None, None),
])
def test_nota_lead_time(horas, nota):
    assert c.nota_lead_time(horas) == nota


@pytest.mark.parametrize("taxa, nota", [
    (0, 4), (0.15, 4), (0.151, 3), (0.30, 3), (0.31, 2), (0.45, 2), (0.46, 1), (None, None),
])
def test_nota_cfr(taxa, nota):
    assert c.nota_cfr(taxa) == nota


@pytest.mark.parametrize("horas, nota", [
    (0.5, 4), (1, 3), (23.9, 3), (24, 2), (167.9, 2), (168, 1), (None, None),
])
def test_nota_recuperacao(horas, nota):
    assert c.nota_recuperacao(horas) == nota


def test_nota_geral_exemplo_do_enunciado():
    assert c.nota_geral([4, 3, 3, 1]) == 3


def test_nota_geral_arredonda_para_baixo():
    assert c.nota_geral([4, 4, 3, 1]) == 3
    assert c.nota_geral([2, 1]) == 1


def test_nota_geral_com_metrica_faltando():
    assert c.nota_geral([4, None, 2]) == 3
    assert c.nota_geral([4, None, 2, 1]) == 2
    assert c.nota_geral([None, None]) is None


def test_classificar_repositorio():
    resultado = c.classificar_repositorio(
        frequencia=2.0, lead_time_horas=10, cfr=0.5, recuperacao_horas=None
    )
    assert resultado["classe_frequencia"] == "High"
    assert resultado["classe_lead_time"] == "Elite"
    assert resultado["classe_cfr"] == "Low"
    assert resultado["classe_recuperacao"] == ""
    assert resultado["classe_geral"] == "High"
    assert resultado["metricas_classificadas"] == 3
