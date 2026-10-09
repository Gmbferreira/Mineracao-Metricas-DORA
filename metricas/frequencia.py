from metricas.comum import para_datetime


def semanas_da_janela(inicio, fim):
    return (fim - inicio).days / 7


def releases_na_janela(releases, inicio, fim, incluir_pre=False):
    total = 0
    for release in releases:
        if release.get("draft"):
            continue
        if release.get("prerelease") and not incluir_pre:
            continue
        publicada = para_datetime(release.get("published_at"))
        if publicada is None:
            continue
        if inicio <= publicada.date() <= fim:
            total += 1
    return total


def deployment_frequency(n_releases, inicio, fim):
    """Releases por semana dentro da janela."""
    semanas = semanas_da_janela(inicio, fim)
    if semanas <= 0:
        return None
    return n_releases / semanas
