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
