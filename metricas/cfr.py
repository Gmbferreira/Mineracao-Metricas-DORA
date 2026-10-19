import datetime as dt
from collections import defaultdict

from metricas import corretiva
from metricas.comum import para_datetime

SUCESSO = {"success"}
FALHA = {"failure", "timed_out", "startup_failure"}


def classificar(conclusion):
    """'sucesso', 'falha' ou None (cancelled, skipped, neutral, em andamento...)."""
    if conclusion in SUCESSO:
        return "sucesso"
    if conclusion in FALHA:
        return "falha"
    return None


def cfr_ci(runs):
    """CFR variante (a): falhas / (falhas + sucessos) dos workflow runs."""
    falhas = sucessos = ignorados = 0
    for run in runs:
        classe = classificar(run.get("conclusion"))
        if classe == "falha":
            falhas += 1
        elif classe == "sucesso":
            sucessos += 1
        else:
            ignorados += 1
    avaliados = falhas + sucessos
    return {
        "cfr_a": falhas / avaliados if avaliados else None,
        "runs_falha": falhas,
        "runs_sucesso": sucessos,
        "runs_ignorados": ignorados,
    }


def fim_da_janela(fim):
    return dt.datetime(fim.year, fim.month, fim.day, 23, 59, 59, tzinfo=dt.timezone.utc)


def cfr_entrega(releases, fim, heuristica=corretiva.PADRAO, dias=7):
    """CFR variante (b): releases seguidas por uma release corretiva em ate `dias`.

    `releases` sao as releases da janela (sem draft e sem pre-release), cada uma
    com `tag_name`, `published_at`, `mensagens` (commits desde a release
    anterior) e `notas` (release notes). A release R falha se a proxima release
    da mesma linha sair em ate `dias` dias e for corretiva. Se esse prazo passa
    do fim da janela, R e censurada e fica fora do denominador.
    """
    e_corretiva = corretiva.HEURISTICAS[heuristica]
    prazo = dt.timedelta(days=dias)
    limite = fim_da_janela(fim)
    por_linha = defaultdict(list)
    for release in releases:
        por_linha[corretiva.linha(release["tag_name"])].append(release)
    avaliadas = falhas = censuradas = corretivas = 0
    for da_linha in por_linha.values():
        da_linha.sort(key=lambda release: (para_datetime(release["published_at"]),
                                           release["tag_name"]))
        for posicao, release in enumerate(da_linha):
            if e_corretiva(release["tag_name"], release.get("mensagens", []),
                           release.get("notas", "")):
                corretivas += 1
            publicada = para_datetime(release["published_at"])
            if publicada + prazo > limite:
                censuradas += 1
                continue
            avaliadas += 1
            if posicao + 1 >= len(da_linha):
                continue
            seguinte = da_linha[posicao + 1]
            if para_datetime(seguinte["published_at"]) - publicada > prazo:
                continue
            if e_corretiva(seguinte["tag_name"], seguinte.get("mensagens", []),
                           seguinte.get("notas", "")):
                falhas += 1
    return {
        "cfr_b": falhas / avaliadas if avaliadas else None,
        "releases_avaliadas_cfr_b": avaliadas,
        "releases_falha_cfr_b": falhas,
        "releases_censuradas_cfr_b": censuradas,
        "releases_corretivas": corretivas,
    }
