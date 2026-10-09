import math

ROTULOS = {4: "Elite", 3: "High", 2: "Medium", 1: "Low"}
DIA = 24
SEMANA = 7 * DIA
MES_EM_SEMANAS = 365.25 / 12 / 7


def nota_frequencia(releases_por_semana):
    if releases_por_semana is None:
        return None
    if releases_por_semana >= 7:
        return 4
    if releases_por_semana >= 1:
        return 3
    if releases_por_semana >= 1 / MES_EM_SEMANAS:
        return 2
    return 1


def nota_lead_time(horas):
    if horas is None:
        return None
    if horas < DIA:
        return 4
    if horas < SEMANA:
        return 3
    if horas < 30 * DIA:
        return 2
    return 1


def nota_cfr(taxa):
    if taxa is None:
        return None
    if taxa <= 0.15:
        return 4
    if taxa <= 0.30:
        return 3
    if taxa <= 0.45:
        return 2
    return 1


def nota_recuperacao(horas):
    if horas is None:
        return None
    if horas < 1:
        return 4
    if horas < DIA:
        return 3
    if horas < SEMANA:
        return 2
    return 1


def nota_geral(notas):
    """Mediana das notas disponiveis, arredondada para baixo."""
    validas = sorted(nota for nota in notas if nota is not None)
    if not validas:
        return None
    meio = len(validas) // 2
    if len(validas) % 2:
        return validas[meio]
    return math.floor((validas[meio - 1] + validas[meio]) / 2)


def classificar_repositorio(frequencia, lead_time_horas, cfr, recuperacao_horas):
    notas = {
        "frequencia": nota_frequencia(frequencia),
        "lead_time": nota_lead_time(lead_time_horas),
        "cfr": nota_cfr(cfr),
        "recuperacao": nota_recuperacao(recuperacao_horas),
    }
    geral = nota_geral(notas.values())
    return {
        **{f"classe_{chave}": ROTULOS.get(nota, "") for chave, nota in notas.items()},
        "classe_geral": ROTULOS.get(geral, ""),
        "metricas_classificadas": sum(1 for nota in notas.values() if nota is not None),
    }
