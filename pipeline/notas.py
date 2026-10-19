import datetime as dt

from metricas.comum import para_datetime

CONSULTA_NOTAS = """
query($dono: String!, $nome: String!, $depois: String) {
  repository(owner: $dono, name: $nome) {
    releases(first: 100, after: $depois, orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { tagName createdAt description }
    }
  }
}
"""
# releases criadas um pouco antes da janela ainda podem ter sido publicadas nela
MARGEM = dt.timedelta(days=60)


def coletar_notas(cliente, nome, inicio, tags):
    """Release notes (campo `description` da GraphQL) das releases em `tags`.

    Vai das releases mais novas para as mais antigas e para quando ja achou
    todas as tags ou quando passou do inicio da janela (com uma margem). Tag que
    nao aparecer fica sem notas.
    """
    dono, repositorio = nome.split("/", 1)
    faltam = set(tags)
    notas = {}
    limite = dt.datetime(inicio.year, inicio.month, inicio.day, tzinfo=dt.timezone.utc) - MARGEM
    depois = None
    while faltam:
        dados = cliente.graphql(
            CONSULTA_NOTAS,
            {"dono": dono, "nome": repositorio, "depois": depois},
            repositorio=nome,
        )
        repo = (dados.get("data") or {}).get("repository")
        if dados.get("errors") or repo is None:
            raise RuntimeError(f"release notes de {nome}: {str(dados.get('errors'))[:200]}")
        bloco = repo["releases"]
        for no in bloco["nodes"]:
            if no["tagName"] in faltam:
                notas[no["tagName"]] = no.get("description") or ""
                faltam.discard(no["tagName"])
        datas = [para_datetime(no["createdAt"]) for no in bloco["nodes"] if no.get("createdAt")]
        if not bloco["pageInfo"]["hasNextPage"] or (datas and min(datas) < limite):
            break
        depois = bloco["pageInfo"]["endCursor"]
    return notas
