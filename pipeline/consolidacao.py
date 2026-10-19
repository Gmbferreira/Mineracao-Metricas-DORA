import csv
import datetime as dt
import json

from metricas import cfr, classificacao, corretiva, frequencia, lead_time, recuperacao
from pipeline import metadados

CAMPOS_DATASET = [
    "full_name",
    "html_url",
    "linguagem",
    "stars",
    "quartil_estrelas",
    "idade_anos",
    "quartil_idade",
    "contributors",
    "quartil_contribuidores",
    "created_at",
    "default_branch",
    "releases_janela",
    "deployment_frequency_semana",
    "lead_time_a_horas",
    "lead_time_b_horas",
    "releases_avaliadas",
    "releases_sem_anterior",
    "releases_compare_falho",
    "releases_sem_commits",
    "releases_commits_truncados",
    "commits_avaliados",
    "commits_data_invalida",
    "runs_total",
    "runs_sucesso",
    "runs_falha",
    "runs_ignorados",
    "cfr_a",
    "cfr_b",
    "releases_avaliadas_cfr_b",
    "releases_falha_cfr_b",
    "releases_censuradas_cfr_b",
    "releases_corretivas",
    "recuperacao_horas",
    "episodios",
    "episodios_censurados",
    "proporcao_censurados",
    "falhas_sem_inicio",
    "intervalos_runs",
    "intervalos_no_teto",
    "classe_frequencia",
    "classe_lead_time",
    "classe_cfr",
    "classe_recuperacao",
    "classe_geral",
    "metricas_classificadas",
]

CAMPOS_RELEASES = [
    "full_name",
    "tag_name",
    "tag_anterior",
    "published_at",
    "status_compare",
    "total_commits",
    "commits_coletados",
    "truncado",
    "lead_time_horas",
    "html_url",
]


def _arredondar(valor, casas=4):
    return "" if valor is None else round(valor, casas)


def para_lead_time(avaliadas):
    return [
        {
            "published_at": item["published_at"],
            "status": item["status"],
            "commits": [commit["data_autor"] for commit in item.get("commits", [])],
        }
        for item in avaliadas
    ]


def para_cfr_b(avaliadas, notas=None):
    notas = notas or {}
    return [
        {
            "tag_name": item["tag_name"],
            "published_at": item["published_at"],
            "mensagens": [commit["mensagem"] for commit in item.get("commits", [])],
            "notas": notas.get(item["tag_name"], ""),
        }
        for item in avaliadas
    ]


def metricas_repo(dados, inicio, fim, meta=None):
    meta = meta or {}
    n_releases = frequencia.releases_na_janela(dados["releases"], inicio, fim)
    df = frequencia.deployment_frequency(n_releases, inicio, fim)
    lt = lead_time.lead_time_repositorio(para_lead_time(dados["avaliadas"]))
    falhas = cfr.cfr_ci(dados["runs"])
    entrega = cfr.cfr_entrega(para_cfr_b(dados["avaliadas"], dados.get("notas")), fim)
    rec = recuperacao.tempo_recuperacao_repositorio(dados["runs"])
    classes = classificacao.classificar_repositorio(
        df, lt["lead_time_a_horas"], falhas["cfr_a"], rec["recuperacao_horas"]
    )
    return {
        "full_name": dados["full_name"],
        "html_url": meta.get("html_url", ""),
        "linguagem": meta.get("linguagem", ""),
        "stars": meta.get("stars", ""),
        "idade_anos": meta.get("idade_anos", ""),
        "contributors": meta.get("contributors", ""),
        "created_at": meta.get("created_at", ""),
        "default_branch": dados.get("default_branch") or "",
        "releases_janela": n_releases,
        "deployment_frequency_semana": _arredondar(df),
        "lead_time_a_horas": _arredondar(lt["lead_time_a_horas"], 2),
        "lead_time_b_horas": _arredondar(lt["lead_time_b_horas"], 2),
        "releases_avaliadas": lt["releases_avaliadas"],
        "releases_sem_anterior": lt["releases_sem_anterior"],
        "releases_compare_falho": lt["releases_compare_falho"],
        "releases_sem_commits": lt["releases_sem_commits"],
        "releases_commits_truncados": sum(
            1 for item in dados["avaliadas"] if item.get("truncado")
        ),
        "commits_avaliados": lt["commits_avaliados"],
        "commits_data_invalida": lt["commits_data_invalida"],
        "runs_total": len(dados["runs"]),
        "runs_sucesso": falhas["runs_sucesso"],
        "runs_falha": falhas["runs_falha"],
        "runs_ignorados": falhas["runs_ignorados"],
        "cfr_a": _arredondar(falhas["cfr_a"]),
        "cfr_b": _arredondar(entrega["cfr_b"]),
        "releases_avaliadas_cfr_b": entrega["releases_avaliadas_cfr_b"],
        "releases_falha_cfr_b": entrega["releases_falha_cfr_b"],
        "releases_censuradas_cfr_b": entrega["releases_censuradas_cfr_b"],
        "releases_corretivas": entrega["releases_corretivas"],
        "recuperacao_horas": _arredondar(rec["recuperacao_horas"], 2),
        "episodios": rec["episodios"],
        "episodios_censurados": rec["episodios_censurados"],
        "proporcao_censurados": _arredondar(rec["proporcao_censurados"]),
        "falhas_sem_inicio": rec["falhas_sem_inicio"],
        "intervalos_runs": dados.get("intervalos_runs", 0),
        "intervalos_no_teto": dados.get("intervalos_no_teto", 0),
        **classes,
    }


def linhas_releases(dados):
    linhas = []
    for item in dados["avaliadas"]:
        datas = [commit["data_autor"] for commit in item.get("commits", [])]
        horas = None
        if item["status"] == "ok":
            horas = lead_time.lead_time_por_release(item["published_at"], datas)
        linhas.append(
            {
                "full_name": dados["full_name"],
                "tag_name": item["tag_name"],
                "tag_anterior": item.get("tag_anterior") or "",
                "published_at": item["published_at"],
                "status_compare": item["status"],
                "total_commits": "" if item.get("total_commits") is None else item["total_commits"],
                "commits_coletados": len(datas),
                "truncado": int(bool(item.get("truncado"))),
                "lead_time_horas": _arredondar(horas, 2),
                "html_url": item.get("html_url") or "",
            }
        )
    return linhas


def escrever_csv(caminho, campos, linhas):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas)


def _numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def adicionar_quartis(linhas):
    """Quartis de estrelas, idade e contribuidores calculados sobre o dataset."""
    limites_por_coluna = {}
    for coluna, destino in (("stars", "quartil_estrelas"), ("idade_anos", "quartil_idade"),
                            ("contributors", "quartil_contribuidores")):
        com_valor = [linha for linha in linhas if _numero(linha.get(coluna)) is not None]
        limites, rotulos = metadados.quartis([_numero(linha[coluna]) for linha in com_valor])
        for linha in linhas:
            linha[destino] = ""
        for linha, rotulo in zip(com_valor, rotulos):
            linha[destino] = rotulo
        limites_por_coluna[destino] = limites
    return limites_por_coluna


def consolidar(coletados, inicio, fim, arq_dataset, arq_releases, amostra=None,
               arq_meta=None):
    metadados_por_repo = {linha["full_name"]: linha for linha in amostra or []}
    ordenados = sorted(coletados, key=lambda dados: dados["full_name"].lower())
    dataset = [
        metricas_repo(dados, inicio, fim, metadados_por_repo.get(dados["full_name"]))
        for dados in ordenados
    ]
    limites = adicionar_quartis(dataset)
    releases = [linha for dados in ordenados for linha in linhas_releases(dados)]
    escrever_csv(arq_dataset, CAMPOS_DATASET, dataset)
    escrever_csv(arq_releases, CAMPOS_RELEASES, releases)
    if arq_meta:
        meta = {
            "gerado_em": dt.datetime.now().isoformat(timespec="seconds"),
            "janela_inicio": inicio.isoformat(),
            "janela_fim": fim.isoformat(),
            "n_repositorios": len(dataset),
            "n_releases": len(releases),
            "heuristica_cfr_b": corretiva.PADRAO,
            "quartis": limites,
            "criterio_quartis": (
                "percentis 25/50/75 com interpolacao linear; "
                "valores iguais ao limite ficam no grupo inferior"
            ),
        }
        with open(arq_meta, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    return dataset, releases
