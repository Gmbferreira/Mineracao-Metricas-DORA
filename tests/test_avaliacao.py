import sys

import pandas as pd
import pytest

from pipeline import coleta
from validacao import avaliacao

CONFIG = """
janela: {inicio: "2025-10-02", fim: "2026-10-02"}
alvo_qualificados: 300
busca: {estrelas_min: 1000, faixas: [[1000, null]]}
filtros: {releases_min: 5, runs_min: 50}
"""


@pytest.fixture
def exemplo_enunciado():
    # secao 6, passo 5: a heuristica marca 40 releases; o consenso confirma 30
    # e tem 50 corretivas no total -> precisao 0,75, recall 0,60, F1 ~ 0,67
    linhas = []
    for i in range(100):
        corretiva = "sim" if i < 50 else "nao"
        marcada = i < 30 or 50 <= i < 60
        linhas.append({"full_name": "o/r", "tag_name": f"t{i}", "corretiva": corretiva,
                       "marcada": marcada})
    return pd.DataFrame(linhas)


def test_avaliar_reproduz_o_exemplo_do_enunciado(exemplo_enunciado):
    marcadas = set(exemplo_enunciado.loc[exemplo_enunciado["marcada"], "tag_name"])
    heuristicas = {"exemplo": lambda tag, mensagens: tag in marcadas}
    resultado = avaliacao.avaliar(exemplo_enunciado, {}, heuristicas).iloc[0]
    assert resultado["precisao"] == 0.75
    assert resultado["recall"] == 0.6
    assert resultado["f1"] == pytest.approx(0.6667, abs=1e-4)
    assert resultado["verdadeiros_positivos"] == 30
    assert resultado["falsos_positivos"] == 10
    assert resultado["falsos_negativos"] == 20
    assert resultado["corretivas_no_consenso"] == 50


def test_avaliar_usa_as_mensagens_de_cada_release():
    consenso = pd.DataFrame([
        {"full_name": "o/r", "tag_name": "v1.0.1", "corretiva": "sim"},
        {"full_name": "o/r", "tag_name": "v1.0.2", "corretiva": " Nao "},
        {"full_name": "o/r", "tag_name": "v1.1.0", "corretiva": "nao"},
    ])
    mensagens = {("o/r", "v1.0.1"): ["fix: crash"], ("o/r", "v1.0.2"): ["chore: release"]}
    resultado = avaliacao.avaliar(consenso, mensagens).set_index("versao")
    assert list(resultado.index) == list(avaliacao.corretiva.HEURISTICAS)
    assert resultado.loc["v3_patch_e_mensagens", "f1"] == 1.0
    assert resultado.loc["v1_patch", "precisao"] == 0.5


def test_avaliar_sem_acertos_nao_quebra():
    consenso = pd.DataFrame([{"full_name": "o/r", "tag_name": "v1.1.0", "corretiva": "sim"}])
    resultado = avaliacao.avaliar(consenso, {}, {"nunca": lambda tag, m: False}).iloc[0]
    assert resultado["f1"] == 0.0


def test_mensagens_por_tag():
    dados = {"avaliadas": [
        {"tag_name": "v1", "commits": [{"mensagem": "fix: a"}]},
        {"tag_name": "v2", "status": "sem_anterior"},
    ]}
    assert avaliacao.mensagens_por_tag(dados) == {"v1": ["fix: a"], "v2": []}


def _preparar_main(monkeypatch, tmp_path, com_consenso=True, com_coleta=True):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(CONFIG, encoding="utf-8")
    (tmp_path / "validacao").mkdir()
    if com_consenso:
        pd.DataFrame([
            {"id_release": 1, "full_name": "o/r", "tag_name": "v1.0.1", "corretiva": "sim"},
            {"id_release": 2, "full_name": "o/r", "tag_name": "v1.1.0", "corretiva": "nao"},
        ]).to_csv(tmp_path / "validacao" / "consenso_releases.csv", index=False)
    if com_coleta:
        coleta.salvar(str(tmp_path / "data" / "coleta"), "o/r", {
            "janela": {"inicio": "2025-10-02", "fim": "2026-10-02"},
            "avaliadas": [
                {"tag_name": "v1.0.1", "commits": [{"mensagem": "fix: a"}]},
                {"tag_name": "v1.1.0", "commits": [{"mensagem": "feat: b"}]},
            ],
        })
    monkeypatch.setattr(sys, "argv", ["validacao.avaliacao"])


def test_main_grava_resultado(monkeypatch, tmp_path, capsys):
    _preparar_main(monkeypatch, tmp_path)
    avaliacao.main()
    resultado = pd.read_csv(tmp_path / "validacao" / "avaliacao_heuristica.csv")
    assert len(resultado) == len(avaliacao.corretiva.HEURISTICAS)
    assert "melhor versao" in capsys.readouterr().out


def test_main_sem_consenso(monkeypatch, tmp_path):
    _preparar_main(monkeypatch, tmp_path, com_consenso=False)
    with pytest.raises(SystemExit, match="ainda nao existe"):
        avaliacao.main()


def test_main_sem_coleta(monkeypatch, tmp_path):
    _preparar_main(monkeypatch, tmp_path, com_coleta=False)
    with pytest.raises(SystemExit, match="Faltam dados coletados"):
        avaliacao.main()
