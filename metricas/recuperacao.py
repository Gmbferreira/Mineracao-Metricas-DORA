from collections import defaultdict

from metricas.cfr import classificar
from metricas.comum import horas_entre, mediana, para_datetime


def _ordem(run):
    return (para_datetime(run.get("created_at")), run.get("id") or 0)


def episodios_de_falha(runs):
    """Episodios de falha de um unico workflow.

    O episodio comeca na primeira falha depois de um sucesso e termina no
    proximo sucesso. Duracao = updated_at do sucesso - run_started_at da
    primeira falha. Sem sucesso ate o fim da janela, o episodio e censurado.
    Falhas no comeco da janela, sem sucesso antes, nao tem inicio conhecido e
    so sao contadas em `sem_inicio`.
    """
    episodios = []
    sem_inicio = 0
    houve_sucesso = False
    aberto = None
    for run in sorted(runs, key=_ordem):
        classe = classificar(run.get("conclusion"))
        if classe is None:
            continue
        if classe == "falha":
            if aberto is None and houve_sucesso:
                aberto = run
            elif not houve_sucesso:
                sem_inicio += 1
            continue
        houve_sucesso = True
        if aberto is not None:
            inicio = aberto.get("run_started_at") or aberto.get("created_at")
            fim = run.get("updated_at")
            episodios.append(
                {"inicio": inicio, "fim": fim, "horas": horas_entre(inicio, fim),
                 "censurado": False}
            )
            aberto = None
    if aberto is not None:
        inicio = aberto.get("run_started_at") or aberto.get("created_at")
        episodios.append({"inicio": inicio, "fim": None, "horas": None, "censurado": True})
    return episodios, sem_inicio


def agrupar_por_workflow(runs):
    grupos = defaultdict(list)
    for run in runs:
        grupos[run.get("workflow_id") or run.get("name")].append(run)
    return grupos


def tempo_recuperacao_repositorio(runs):
    """Mediana (horas) dos episodios recuperados de todos os workflows."""
    episodios = []
    sem_inicio = 0
    for runs_workflow in agrupar_por_workflow(runs).values():
        do_workflow, falhas_sem_inicio = episodios_de_falha(runs_workflow)
        episodios.extend(do_workflow)
        sem_inicio += falhas_sem_inicio
    censurados = sum(1 for episodio in episodios if episodio["censurado"])
    return {
        "recuperacao_horas": mediana(
            episodio["horas"] for episodio in episodios if not episodio["censurado"]
        ),
        "episodios": len(episodios),
        "episodios_censurados": censurados,
        "proporcao_censurados": censurados / len(episodios) if episodios else None,
        "falhas_sem_inicio": sem_inicio,
    }
