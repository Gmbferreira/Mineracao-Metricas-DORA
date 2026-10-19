import re

PADRAO_VERSAO = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")
SEPARADORES_FINAIS = re.compile(r"[-_@/=.\s]*v?[-_@/=.\s]*$")
PADRAO_CORRECAO = re.compile(
    r"\b(fix(es|ed|ing)?|hotfix(es)?|bug\s?fix(es)?|revert(s|ed)?)\b", re.IGNORECASE
)
# commits de atualizacao de dependencia (renovate, dependabot) usam "fix(deps)"
# mas nao corrigem defeito do projeto
PADRAO_DEPENDENCIA = re.compile(r"^\s*fix\((deps|deps-dev)\)", re.IGNORECASE)
PADRAO_MERGE = re.compile(r"^\s*merge (pull request|branch|remote-tracking)", re.IGNORECASE)
# palavras de correcao e de funcionalidade contadas nas release notes (v6)
CORRECAO_NAS_NOTAS = re.compile(
    r"\b(fix(es|ed|ing)?|bug(s|fix(es)?)?|hotfix(es)?|regression(s)?|crash(es)?|security"
    r"|vulnerabilit(y|ies)|cve-\d+|revert(s|ed)?|patch(es|ed)?)\b",
    re.IGNORECASE,
)
FUNCIONALIDADE_NAS_NOTAS = re.compile(
    r"\b(feat(ure)?s?|add(s|ed)?|new|introduc(e|es|ed)|support(s)?|implement(s|ed)?"
    r"|enhancement(s)?|improve(s|d|ment|ments)?)\b",
    re.IGNORECASE,
)


def versao(tag):
    """(major, minor, patch) da tag, ou None se ela nao segue o formato X.Y[.Z]."""
    achado = PADRAO_VERSAO.search(tag or "")
    if achado is None:
        return None
    return int(achado.group(1)), int(achado.group(2)), int(achado.group(3) or 0)


def linha(tag):
    """Prefixo que identifica a linha da release (o pacote, em monorepos).

    `v1.2.3` e `1.2.3` ficam na mesma linha; `vite@7.1.0` e `create-vite@8.0.1`
    ficam em linhas diferentes. Tags sem versao (ex.: `b8492`) usam o texto
    antes do primeiro numero.
    """
    tag = tag or ""
    achado = PADRAO_VERSAO.search(tag) or re.search(r"\d", tag)
    prefixo = tag[: achado.start()] if achado else tag
    return SEPARADORES_FINAIS.sub("", prefixo.lower())


def e_patch(tag):
    """Release de patch no SemVer: o terceiro numero e maior que zero (2.3.1)."""
    numeros = versao(tag)
    return numeros is not None and numeros[2] > 0


def e_mensagem_de_correcao(mensagem):
    if not mensagem or PADRAO_DEPENDENCIA.match(mensagem):
        return False
    return PADRAO_CORRECAO.search(mensagem) is not None


def proporcao_de_correcoes(mensagens):
    consideradas = [m for m in mensagens if m and not PADRAO_MERGE.match(m)]
    if not consideradas:
        return 0.0
    return sum(1 for m in consideradas if e_mensagem_de_correcao(m)) / len(consideradas)


def tem_correcao(mensagens):
    return any(e_mensagem_de_correcao(mensagem) for mensagem in mensagens)


def notas_de_correcao(notas):
    """As release notes falam de correcao pelo menos tanto quanto de funcionalidade.

    Release sem notas conta como empate (0 a 0).
    """
    texto = notas or ""
    return len(CORRECAO_NAS_NOTAS.findall(texto)) >= len(FUNCIONALIDADE_NAS_NOTAS.findall(texto))


def v1_patch(tag, mensagens, notas=""):
    return e_patch(tag)


def v2_mensagens(tag, mensagens, notas=""):
    return tem_correcao(mensagens)


def v3_patch_e_mensagens(tag, mensagens, notas=""):
    return e_patch(tag) and tem_correcao(mensagens)


def v4_patch_ou_mensagens(tag, mensagens, notas=""):
    return e_patch(tag) or tem_correcao(mensagens)


def v5_patch_e_maioria(tag, mensagens, notas=""):
    return e_patch(tag) and proporcao_de_correcoes(mensagens) >= 0.5


def v6_patch_e_notas(tag, mensagens, notas=""):
    return e_patch(tag) and notas_de_correcao(notas)


# versoes avaliadas contra o consenso da amostra-ouro. As cinco primeiras ficaram
# abaixo de F1 0,70; a v6, criada depois da validacao, e a usada no CFR (b)
HEURISTICAS = {
    "v1_patch": v1_patch,
    "v2_mensagens": v2_mensagens,
    "v3_patch_e_mensagens": v3_patch_e_mensagens,
    "v4_patch_ou_mensagens": v4_patch_ou_mensagens,
    "v5_patch_e_maioria": v5_patch_e_maioria,
    "v6_patch_e_notas": v6_patch_e_notas,
}
PADRAO = "v6_patch_e_notas"
