from metricas.comum import horas_entre, mediana


def lead_times_por_commit(data_release, datas_commits):
    """Lead time (horas) de cada commit incluido na release.

    Commits com data de autor depois da publicacao da release (relogio errado,
    data reescrita) dariam lead time negativo; ficam de fora e sao contados.
    """
    validos = []
    negativos = 0
    for data_commit in datas_commits:
        if not data_commit:
            continue
        horas = horas_entre(data_commit, data_release)
        if horas < 0:
            negativos += 1
            continue
        validos.append(horas)
    return validos, negativos


def lead_time_por_release(data_release, datas_commits):
    """Variante (a): data da release menos a data do commit mais antigo."""
    validos, _ = lead_times_por_commit(data_release, datas_commits)
    if not validos:
        return None
    return max(validos)


def lead_time_repositorio(releases):
    """Agrega o lead time de um repositorio pela mediana.

    Cada item de `releases` e um dict com `published_at`, `commits` (lista de
    datas de autor) e `status` do compare. Releases sem release anterior
    (`sem_anterior`) ou com compare falho (`404`, `erro`) nao entram no
    calculo; releases sem commits novos tambem nao, mas sao contadas.
    """
    por_release = []
    por_commit = []
    contagem = {
        "releases_avaliadas": 0,
        "releases_sem_anterior": 0,
        "releases_compare_falho": 0,
        "releases_sem_commits": 0,
        "commits_avaliados": 0,
        "commits_data_invalida": 0,
    }
    for release in releases:
        status = release.get("status", "ok")
        if status == "sem_anterior":
            contagem["releases_sem_anterior"] += 1
            continue
        if status != "ok":
            contagem["releases_compare_falho"] += 1
            continue
        validos, negativos = lead_times_por_commit(
            release["published_at"], release.get("commits", [])
        )
        contagem["commits_data_invalida"] += negativos
        if not validos:
            contagem["releases_sem_commits"] += 1
            continue
        contagem["releases_avaliadas"] += 1
        contagem["commits_avaliados"] += len(validos)
        por_release.append(max(validos))
        por_commit.extend(validos)
    return {
        "lead_time_a_horas": mediana(por_release),
        "lead_time_b_horas": mediana(por_commit),
        **contagem,
    }
