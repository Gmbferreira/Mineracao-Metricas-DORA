import datetime as dt
import math
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from metricas.comum import para_datetime

CAMPOS_RELEASE = (
    "id",
    "tag_name",
    "name",
    "draft",
    "prerelease",
    "created_at",
    "published_at",
    "target_commitish",
    "html_url",
)


# Comparison da GraphQL: mesmos commits do compare REST, mas so os 1000 mais
# recentes; o resto vem das primeiras paginas do REST
CONSULTA_COMPARE = """
query($dono: String!, $nome: String!, $base: String!, $head: String!, $depois: String) {
  repository(owner: $dono, name: $nome) {
    ref(qualifiedName: $base) {
      compare(headRef: $head) {
        commits(first: 100, after: $depois) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes { oid authoredDate message }
        }
      }
    }
  }
}
"""


def reduzir_releases(dados):
    if not isinstance(dados, list):
        return dados
    return [{campo: item.get(campo) for campo in CAMPOS_RELEASE} for item in dados]


def reduzir_compare(dados):
    if not isinstance(dados, dict):
        return dados
    commits = []
    for item in dados.get("commits", []):
        commit = item.get("commit") or {}
        mensagem = (commit.get("message") or "").split("\n", 1)[0][:300]
        commits.append(
            {
                "sha": item.get("sha"),
                "commit": {
                    "author": {"date": (commit.get("author") or {}).get("date")},
                    "committer": {"date": (commit.get("committer") or {}).get("date")},
                    "message": mensagem,
                },
            }
        )
    return {
        "status": dados.get("status"),
        "ahead_by": dados.get("ahead_by"),
        "behind_by": dados.get("behind_by"),
        "total_commits": dados.get("total_commits"),
        "commits": commits,
    }


def _valida(release, incluir_pre=False):
    if release.get("draft") or not release.get("published_at"):
        return False
    return incluir_pre or not release.get("prerelease")


def buscar_releases(cliente, nome, inicio, per_page=100, max_paginas=20):
    """Todas as releases da janela e ao menos uma anterior a ela.

    A release anterior a primeira da janela pode estar fora da janela e e
    necessaria para o compare. Para quando a pagina vem incompleta (fim do
    historico) ou quando ja existe uma release publicada antes do inicio.
    """
    releases = []
    pagina = 1
    while pagina <= max_paginas:
        resposta = cliente.get(
            f"/repos/{nome}/releases",
            {"per_page": per_page, "page": pagina},
            aceitar=(403, 404),
            reduzir=reduzir_releases,
        )
        if resposta.status_code != 200:
            break
        itens = resposta.json()
        if not isinstance(itens, list) or not itens:
            break
        releases.extend(reduzir_releases(itens))
        if len(itens) < per_page:
            break
        if any(
            _valida(item) and para_datetime(item["published_at"]).date() < inicio
            for item in itens
        ):
            break
        pagina += 1
    return releases


def ordenar_validas(releases, incluir_pre=False):
    validas = [release for release in releases if _valida(release, incluir_pre)]
    return sorted(validas, key=lambda release: para_datetime(release["published_at"]))


def montar_pares(releases, inicio, fim, incluir_pre=False):
    """Cada release da janela com a release imediatamente anterior a ela."""
    validas = ordenar_validas(releases, incluir_pre)
    pares = []
    for posicao, release in enumerate(validas):
        data = para_datetime(release["published_at"]).date()
        if not inicio <= data <= fim:
            continue
        anterior = validas[posicao - 1] if posicao > 0 else None
        pares.append((anterior, release))
    return pares


def _caminho_compare(nome, base, head):
    return "/repos/{}/compare/{}...{}".format(
        nome,
        urllib.parse.quote(base, safe=""),
        urllib.parse.quote(head, safe=""),
    )


def _data_utc(valor):
    if not valor:
        return valor
    return para_datetime(valor).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _commits_graphql(cliente, nome, base, head):
    """(total, commits) pela GraphQL, ou None se a resposta sair do normal."""
    dono, repositorio = nome.split("/", 1)
    commits = []
    depois = None
    while True:
        try:
            dados = cliente.graphql(
                CONSULTA_COMPARE,
                {"dono": dono, "nome": repositorio, "base": "refs/tags/" + base,
                 "head": "refs/tags/" + head, "depois": depois},
                repositorio=nome,
            )
        except RuntimeError:
            return None
        if dados.get("errors"):
            return None
        ref = ((dados.get("data") or {}).get("repository") or {}).get("ref") or {}
        comparacao = ref.get("compare")
        if not comparacao:
            return None
        pagina = comparacao["commits"]
        for no in pagina["nodes"]:
            commits.append(
                {
                    "sha": no["oid"],
                    "data_autor": _data_utc(no.get("authoredDate")),
                    "mensagem": (no.get("message") or "").split("\n", 1)[0][:300],
                }
            )
        if not pagina["pageInfo"]["hasNextPage"]:
            return pagina["totalCount"], commits
        depois = pagina["pageInfo"]["endCursor"]


def buscar_commits(cliente, nome, base, head, per_page=100, max_paginas=100):
    """Commits da release `head` desde a release `base`.

    Vai primeiro na GraphQL, que tem cota separada da REST. Ela devolve os
    mesmos commits do compare REST, na mesma ordem, mas no maximo os 1000 mais
    recentes; se o compare for maior, os mais antigos vem das primeiras paginas
    do REST. Se o REST desse par ja esta no cache ou a GraphQL nao responde
    como esperado, o compare sai todo pelo REST, como antes.
    """
    caminho = _caminho_compare(nome, base, head)
    em_cache = getattr(cliente, "em_cache", None)
    ja_no_cache = em_cache is not None and em_cache(caminho, {"per_page": per_page, "page": 1})
    if not hasattr(cliente, "graphql") or ja_no_cache:
        return _commits_rest(cliente, caminho, per_page, max_paginas)
    resultado = _commits_graphql(cliente, nome, base, head)
    if resultado is None:
        return _commits_rest(cliente, caminho, per_page, max_paginas)
    total, recentes = resultado
    if len(recentes) >= total:
        return {"status": "ok", "total_commits": total, "commits": recentes, "truncado": False}
    faltam = total - len(recentes)
    antigos = _commits_rest(cliente, caminho, per_page,
                            min(max_paginas, math.ceil(faltam / per_page)))
    if antigos["status"] != "ok":
        return antigos
    vistos = {commit["sha"] for commit in antigos["commits"]}
    commits = antigos["commits"] + [c for c in recentes if c["sha"] not in vistos]
    return {"status": "ok", "total_commits": total, "commits": commits,
            "truncado": len(commits) < total}


def _commits_rest(cliente, caminho, per_page=100, max_paginas=100):
    commits = []
    total = None
    pagina = 1
    while pagina <= max_paginas:
        try:
            resposta = cliente.get(
                caminho,
                {"per_page": per_page, "page": pagina},
                aceitar=(404, 422),
                reduzir=reduzir_compare,
            )
        except RuntimeError as erro:
            return {"status": "erro", "erro": str(erro)[:200], "total_commits": None,
                    "commits": [], "truncado": False}
        if resposta.status_code != 200:
            return {"status": str(resposta.status_code), "total_commits": None,
                    "commits": [], "truncado": False}
        dados = reduzir_compare(resposta.json())
        total = dados.get("total_commits") or 0
        pagina_commits = dados.get("commits", [])
        for item in pagina_commits:
            commits.append(
                {
                    "sha": item["sha"],
                    "data_autor": item["commit"]["author"]["date"],
                    "mensagem": item["commit"]["message"],
                }
            )
        if len(pagina_commits) < per_page or len(commits) >= total:
            break
        pagina += 1
    return {
        "status": "ok",
        "total_commits": total,
        "commits": commits,
        "truncado": total is not None and len(commits) < total,
    }


def coletar_releases(cliente, nome, inicio, fim, paralelo=1):
    releases = buscar_releases(cliente, nome, inicio)

    def avaliar(par):
        anterior, release = par
        item = {
            "tag_name": release["tag_name"],
            "published_at": release["published_at"],
            "html_url": release.get("html_url"),
            "tag_anterior": anterior["tag_name"] if anterior else None,
        }
        if anterior is None:
            item.update(status="sem_anterior", total_commits=None, commits=[],
                        truncado=False)
        else:
            item.update(
                buscar_commits(cliente, nome, anterior["tag_name"], release["tag_name"])
            )
        return item

    pares = montar_pares(releases, inicio, fim)
    with ThreadPoolExecutor(max_workers=max(1, paralelo)) as executor:
        avaliadas = list(executor.map(avaliar, pares))
    return {"releases": releases, "avaliadas": avaliadas}
