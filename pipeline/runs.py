import datetime as dt
import math
from concurrent.futures import ThreadPoolExecutor

CAMPOS_RUN = (
    "id",
    "name",
    "workflow_id",
    "event",
    "head_branch",
    "status",
    "conclusion",
    "created_at",
    "run_started_at",
    "updated_at",
    "run_attempt",
)
TETO_API = 1000
MENOR_INTERVALO = dt.timedelta(minutes=1)
UM_SEGUNDO = dt.timedelta(seconds=1)


def reduzir_runs(dados):
    if not isinstance(dados, dict):
        return dados
    return {
        "total_count": dados.get("total_count", 0),
        "workflow_runs": [
            {campo: run.get(campo) for campo in CAMPOS_RUN}
            for run in dados.get("workflow_runs", [])
        ],
    }


def intervalos_mensais(inicio, fim):
    """Divide a janela [inicio, fim] (datas inclusivas) em meses de calendario."""
    intervalos = []
    atual = dt.datetime(inicio.year, inicio.month, inicio.day, tzinfo=dt.timezone.utc)
    limite = dt.datetime(fim.year, fim.month, fim.day, 23, 59, 59, tzinfo=dt.timezone.utc)
    while atual <= limite:
        if atual.month == 12:
            proximo = atual.replace(year=atual.year + 1, month=1, day=1,
                                    hour=0, minute=0, second=0)
        else:
            proximo = atual.replace(month=atual.month + 1, day=1,
                                    hour=0, minute=0, second=0)
        intervalos.append((atual, min(proximo - UM_SEGUNDO, limite)))
        atual = proximo
    return intervalos


def formatar_intervalo(inicio, fim):
    return f"{inicio:%Y-%m-%dT%H:%M:%SZ}..{fim:%Y-%m-%dT%H:%M:%SZ}"


def dividir_intervalo(inicio, fim):
    if fim - inicio < MENOR_INTERVALO:
        return None
    meio = inicio + (fim - inicio) / 2
    meio = meio.replace(microsecond=0)
    return [(inicio, meio), (meio + UM_SEGUNDO, fim)]


def _pagina(cliente, nome, branch, inicio, fim, pagina, per_page):
    return cliente.get(
        f"/repos/{nome}/actions/runs",
        {
            "branch": branch,
            "event": "push",
            "created": formatar_intervalo(inicio, fim),
            "exclude_pull_requests": "true",
            "per_page": per_page,
            "page": pagina,
        },
        aceitar=(403, 404),
        reduzir=reduzir_runs,
    )


def buscar_intervalo(cliente, nome, branch, inicio, fim, per_page=100, teto=TETO_API):
    """Runs criados em [inicio, fim]; divide o intervalo enquanto passar do teto.

    A API devolve no maximo `teto` resultados por consulta filtrada. Se o
    `total_count` passar disso, o intervalo e dividido ao meio ate caber.
    """
    resposta = _pagina(cliente, nome, branch, inicio, fim, 1, per_page)
    if resposta.status_code != 200:
        return {"runs": [], "intervalos": 1, "no_teto": 0, "acesso": False}
    dados = resposta.json()
    total = int(dados.get("total_count", 0))
    if total > teto:
        partes = dividir_intervalo(inicio, fim)
        if partes is not None:
            resultado = {"runs": [], "intervalos": 0, "no_teto": 0, "acesso": True}
            for parte_inicio, parte_fim in partes:
                parcial = buscar_intervalo(cliente, nome, branch, parte_inicio,
                                           parte_fim, per_page, teto)
                resultado["runs"].extend(parcial["runs"])
                resultado["intervalos"] += parcial["intervalos"]
                resultado["no_teto"] += parcial["no_teto"]
            return resultado
    runs = list(dados.get("workflow_runs", []))
    paginas = math.ceil(min(total, teto) / per_page)
    for pagina in range(2, paginas + 1):
        resposta = _pagina(cliente, nome, branch, inicio, fim, pagina, per_page)
        if resposta.status_code != 200:
            break
        itens = resposta.json().get("workflow_runs", [])
        runs.extend(itens)
        if len(itens) < per_page:
            break
    return {"runs": runs, "intervalos": 1, "no_teto": int(total > teto), "acesso": True}


def coletar_runs(cliente, nome, branch, inicio, fim, per_page=100, paralelo=1):
    if not branch:
        return {"runs": [], "intervalos": 0, "intervalos_no_teto": 0, "acesso": False}
    vistos = {}
    intervalos = 0
    no_teto = 0
    acesso = True
    meses = intervalos_mensais(inicio, fim)
    with ThreadPoolExecutor(max_workers=max(1, paralelo)) as executor:
        parciais = list(executor.map(
            lambda mes: buscar_intervalo(cliente, nome, branch, mes[0], mes[1], per_page),
            meses,
        ))
    for parcial in parciais:
        intervalos += parcial["intervalos"]
        no_teto += parcial["no_teto"]
        acesso = acesso and parcial["acesso"]
        for run in parcial["runs"]:
            if run.get("event") != "push" or run.get("head_branch") != branch:
                continue
            vistos[run["id"]] = run
    runs = sorted(vistos.values(), key=lambda run: (run.get("created_at") or "", run["id"]))
    return {
        "runs": runs,
        "intervalos": intervalos,
        "intervalos_no_teto": no_teto,
        "acesso": acesso,
    }
