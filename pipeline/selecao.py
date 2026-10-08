import datetime as dt


def conta_workflows(cliente, nome):
    resposta = cliente.get(
        f"/repos/{nome}/actions/workflows",
        {"per_page": 1},
        aceitar=(403, 404),
    )
    if resposta.status_code != 200:
        return 0
    return int(resposta.json().get("total_count", 0))


def conta_runs_push(cliente, nome, default_branch, janela_runs):
    if not default_branch:
        return 0
    resposta = cliente.get(
        f"/repos/{nome}/actions/runs",
        {
            "branch": default_branch,
            "event": "push",
            "created": janela_runs,
            "per_page": 1,
        },
        aceitar=(403, 404),
    )
    if resposta.status_code != 200:
        return 0
    return int(resposta.json().get("total_count", 0))


def releases_na_janela(itens, inicio, fim):
    total = 0
    for item in itens:
        if item.get("draft") or item.get("prerelease"):
            continue
        publicada = item.get("published_at")
        if not publicada:
            continue
        data = dt.date.fromisoformat(publicada[:10])
        if inicio <= data <= fim:
            total += 1
    return total


def conta_releases(cliente, nome, inicio, fim, max_paginas=10, per_page=100):
    total = 0
    pagina = 1
    while pagina <= max_paginas:
        resposta = cliente.get(
            f"/repos/{nome}/releases",
            {"per_page": per_page, "page": pagina},
            aceitar=(403, 404),
        )
        if resposta.status_code != 200:
            break
        itens = resposta.json()
        if not isinstance(itens, list) or not itens:
            break
        total += releases_na_janela(itens, inicio, fim)
        if len(itens) < per_page:
            break
        ultima = itens[-1].get("created_at") or ""
        if ultima[:10] < inicio.isoformat():
            break
        pagina += 1
    return total


def qualifica(workflows_total, runs, releases, runs_min, releases_min):
    return workflows_total > 0 and runs >= runs_min and releases >= releases_min
