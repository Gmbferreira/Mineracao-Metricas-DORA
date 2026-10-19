import datetime as dt

from metricas.comum import para_datetime
from pipeline import notas, releases

CONSULTA_TAGS = """
query($dono: String!, $nome: String!, $depois: String) {
  repository(owner: $dono, name: $nome) {
    refs(refPrefix: "refs/tags/", first: 100, after: $depois,
         orderBy: {field: TAG_COMMIT_DATE, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        target {
          __typename
          ... on Commit { oid committedDate }
          ... on Tag { target { __typename ... on Commit { oid committedDate } } }
        }
      }
    }
  }
}
"""
TAMANHO_DO_LOTE = 25


def _commit_da_tag(no):
    alvo = no.get("target") or {}
    if alvo.get("__typename") == "Tag":
        alvo = alvo.get("target") or {}
    return alvo if alvo.get("__typename") == "Commit" else None


def buscar_tags(cliente, nome, inicio, max_paginas=300):
    """Tags com a data do commit apontado, da mais nova para a mais antiga.

    O enunciado manda datar a tag pelo commit que ela aponta. Para quando ja tem
    uma tag anterior a janela, que serve de base para o primeiro compare.
    """
    dono, repositorio = nome.split("/", 1)
    limite = dt.datetime(inicio.year, inicio.month, inicio.day, tzinfo=dt.timezone.utc)
    tags = []
    depois = None
    for _ in range(max_paginas):
        dados = cliente.graphql(CONSULTA_TAGS,
                                {"dono": dono, "nome": repositorio, "depois": depois},
                                repositorio=nome)
        repo = (dados.get("data") or {}).get("repository")
        if dados.get("errors") or repo is None:
            raise RuntimeError(f"tags de {nome}: {str(dados.get('errors'))[:200]}")
        bloco = repo["refs"]
        for no in bloco["nodes"]:
            commit = _commit_da_tag(no)
            if commit and commit.get("committedDate"):
                tags.append({"tag_name": no["name"], "sha": commit["oid"],
                             "published_at": commit["committedDate"]})
        if not bloco["pageInfo"]["hasNextPage"]:
            break
        if tags and para_datetime(tags[-1]["published_at"]) < limite:
            break
        depois = bloco["pageInfo"]["endCursor"]
    return tags


def pares_de_tags(tags, inicio, fim):
    """Cada tag da janela com a tag imediatamente anterior pela data."""
    ordenadas = sorted(tags, key=lambda tag: (para_datetime(tag["published_at"]), tag["tag_name"]))
    pares = []
    for posicao, tag in enumerate(ordenadas):
        if not inicio <= para_datetime(tag["published_at"]).date() <= fim:
            continue
        pares.append((ordenadas[posicao - 1] if posicao else None, tag))
    return pares


def _consulta_de_lote(quantidade):
    parametros = ", ".join(f"$b{i}: String!, $h{i}: String!" for i in range(quantidade))
    blocos = "\n".join(
        f"    c{i}: ref(qualifiedName: $b{i}) {{ compare(headRef: $h{i}) {{ commits(first: 100) "
        f"{{ totalCount pageInfo {{ hasNextPage }} nodes {{ oid authoredDate }} }} }} }}"
        for i in range(quantidade)
    )
    return (f"query($dono: String!, $nome: String!, {parametros}) {{\n"
            f"  repository(owner: $dono, name: $nome) {{\n{blocos}\n  }}\n}}")


def _sozinho(cliente, nome, base, head):
    resultado = releases.buscar_commits(cliente, nome, base, head)
    resultado["commits"] = [{"sha": c["sha"], "data_autor": c["data_autor"]}
                            for c in resultado["commits"]]
    return resultado


def commits_em_lote(cliente, nome, pares, tamanho=TAMANHO_DO_LOTE):
    """Commits de varios compares numa so consulta GraphQL.

    Uma consulta com ate `tamanho` compares custa cerca de 1 ponto da cota. Compare
    com mais de 100 commits, tag apagada ou erro sai pelo caminho normal
    (`releases.buscar_commits`), que completa pelo REST quando preciso.
    """
    dono, repositorio = nome.split("/", 1)
    resultados = {}
    pendentes = [list(pares[i:i + tamanho]) for i in range(0, len(pares), tamanho)]
    while pendentes:
        lote = pendentes.pop()
        variaveis = {"dono": dono, "nome": repositorio}
        for i, (base, head) in enumerate(lote):
            variaveis[f"b{i}"] = "refs/tags/" + base
            variaveis[f"h{i}"] = "refs/tags/" + head
        try:
            dados = cliente.graphql(_consulta_de_lote(len(lote)), variaveis, repositorio=nome)
        except RuntimeError:
            dados = {}
        repo = (dados.get("data") or {}).get("repository")
        if repo is None:
            if len(lote) > 1:
                metade = len(lote) // 2
                pendentes += [lote[:metade], lote[metade:]]
            else:
                resultados[lote[0]] = _sozinho(cliente, nome, *lote[0])
            continue
        for i, par in enumerate(lote):
            comparacao = (repo.get(f"c{i}") or {}).get("compare")
            if not comparacao or comparacao["commits"]["pageInfo"]["hasNextPage"]:
                resultados[par] = _sozinho(cliente, nome, *par)
                continue
            pagina = comparacao["commits"]
            resultados[par] = {
                "status": "ok",
                "total_commits": pagina["totalCount"],
                "commits": [{"sha": no["oid"], "data_autor": releases._data_utc(no["authoredDate"])}
                            for no in pagina["nodes"]],
                "truncado": False,
            }
    return resultados


def _avaliadas(pares, ja_coletados, novos):
    lista = []
    for anterior, unidade in pares:
        item = {"tag_name": unidade["tag_name"], "published_at": unidade["published_at"],
                "tag_anterior": anterior["tag_name"] if anterior else None}
        if anterior is None:
            item.update(status="sem_anterior", total_commits=None, commits=[], truncado=False)
        else:
            chave = (anterior["tag_name"], unidade["tag_name"])
            resultado = ja_coletados.get(chave) or novos[chave]
            item.update(status=resultado["status"], total_commits=resultado.get("total_commits"),
                        commits=[{"sha": c.get("sha"), "data_autor": c["data_autor"]}
                                 for c in resultado.get("commits", [])],
                        truncado=resultado.get("truncado", False))
        lista.append(item)
    return lista


def coletar_variantes(cliente, nome, inicio, fim, dados):
    """Unidades de deploy da RQ 07: release + pre-release e tag.

    Reaproveita os compares que ja estao em `dados["avaliadas"]` (pares iguais
    aos da release principal) e completa as release notes das pre-releases.
    """
    ja_coletados = {
        (item["tag_anterior"], item["tag_name"]): item
        for item in dados.get("avaliadas", []) if item.get("tag_anterior")
    }
    pares_pre = releases.montar_pares(dados["releases"], inicio, fim, incluir_pre=True)
    tags = buscar_tags(cliente, nome, inicio)
    pares_tag = pares_de_tags(tags, inicio, fim)
    faltam = []
    for anterior, unidade in pares_pre + pares_tag:
        if anterior is None:
            continue
        chave = (anterior["tag_name"], unidade["tag_name"])
        if chave not in ja_coletados and chave not in faltam:
            faltam.append(chave)
    novos = commits_em_lote(cliente, nome, faltam)
    sem_notas = [unidade["tag_name"] for _, unidade in pares_pre
                 if unidade["tag_name"] not in dados.get("notas", {})]
    notas_novas = notas.coletar_notas(cliente, nome, inicio, sem_notas) if sem_notas else {}
    return {
        "release_pre": {"avaliadas": _avaliadas(pares_pre, ja_coletados, novos)},
        "tag": {"tags": [t for t in tags if para_datetime(t["published_at"]).date() <= fim],
                "avaliadas": _avaliadas(pares_tag, ja_coletados, novos)},
        "notas": notas_novas,
    }
