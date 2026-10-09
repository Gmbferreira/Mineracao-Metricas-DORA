import datetime as dt
import statistics


def para_datetime(valor):
    if valor is None or valor == "":
        return None
    if isinstance(valor, dt.datetime):
        data = valor
    else:
        data = dt.datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    if data.tzinfo is None:
        data = data.replace(tzinfo=dt.timezone.utc)
    return data


def horas_entre(inicio, fim):
    return (para_datetime(fim) - para_datetime(inicio)).total_seconds() / 3600


def mediana(valores):
    valores = [valor for valor in valores if valor is not None]
    if not valores:
        return None
    return float(statistics.median(valores))
