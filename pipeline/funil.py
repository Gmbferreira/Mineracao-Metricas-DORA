import csv
import datetime as dt


def montar_tabela(identificados, escaneados, passaram_workflows, passaram_runs, qualificados, amostra, alvo):
    if escaneados >= identificados:
        descarte_busca = 0
        motivo_busca = "varredura completa"
    else:
        descarte_busca = identificados - escaneados
        motivo_busca = f"varredura parcial: parada ao atingir o alvo de {alvo} (ordem: estrelas decrescentes)"
    return [
        {
            "etapa": "Candidatos identificados (stars >1000, pre-filtros)",
            "entrada": "",
            "saida": identificados,
            "descartados": "",
            "motivo": "busca fatiada por faixas de estrelas",
        },
        {
            "etapa": "Candidatos escaneados",
            "entrada": identificados,
            "saida": escaneados,
            "descartados": descarte_busca,
            "motivo": motivo_busca,
        },
        {
            "etapa": "E1 - utiliza GitHub Actions",
            "entrada": escaneados,
            "saida": passaram_workflows,
            "descartados": escaneados - passaram_workflows,
            "motivo": "total_count de workflows = 0",
        },
        {
            "etapa": "E2 - >=50 runs de push no default branch na janela",
            "entrada": passaram_workflows,
            "saida": passaram_runs,
            "descartados": passaram_workflows - passaram_runs,
            "motivo": "menos de 50 runs de push na janela",
        },
        {
            "etapa": "E3 - >=5 releases publicadas na janela",
            "entrada": passaram_runs,
            "saida": qualificados,
            "descartados": passaram_runs - qualificados,
            "motivo": "menos de 5 releases publicadas na janela",
        },
        {
            "etapa": "Amostra final com metadados completos",
            "entrada": qualificados,
            "saida": amostra,
            "descartados": qualificados - amostra,
            "motivo": "contribuidores/idade coletados para todos",
        },
    ]


def escrever_csv(caminho, linhas):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(
            f, fieldnames=["etapa", "entrada", "saida", "descartados", "motivo"]
        )
        escritor.writeheader()
        escritor.writerows(linhas)


def escrever_md(caminho, linhas, notas):
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("# Funil de selecao\n\n")
        f.write(f"Gerado em: {dt.datetime.now().isoformat(timespec='seconds')}\n\n")
        f.write("| Etapa | Entrada | Saida | Descartados | Motivo |\n")
        f.write("|---|---:|---:|---:|---|\n")
        for linha in linhas:
            f.write(
                "| {etapa} | {entrada} | {saida} | {descartados} | {motivo} |\n".format(
                    **linha
                )
            )
        f.write("\nNotas:\n")
        for nota in notas:
            f.write(f"- {nota}\n")
