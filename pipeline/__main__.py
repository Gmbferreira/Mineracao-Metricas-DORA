import argparse
import csv
import datetime as dt
import json
import os
import time

from pipeline import busca, config, funil, metadados, selecao, store
from pipeline.cliente import ClienteGitHub

DIR_DADOS = "data"
DIR_CK = os.path.join(DIR_DADOS, "checkpoints")
ARQ_AMOSTRA = os.path.join(DIR_DADOS, "amostra.csv")
ARQ_AMOSTRA_META = os.path.join(DIR_DADOS, "amostra_meta.json")
ARQ_FUNIL_CSV = os.path.join(DIR_DADOS, "funil.csv")
ARQ_FUNIL_MD = os.path.join(DIR_DADOS, "funil.md")

CAMPOS_AMOSTRA = [
    "full_name",
    "html_url",
    "stars",
    "linguagem",
    "idade_anos",
    "contributors",
    "quartil_contribuidores",
    "created_at",
    "default_branch",
    "faixa_estrelas",
]


def varrer(cliente, cfg, folhas, alvo, limite):
    e1 = store.mapa(DIR_CK, "e1_workflows.jsonl")
    e2 = store.mapa(DIR_CK, "e2_runs.jsonl")
    e3 = store.mapa(DIR_CK, "e3_releases.jsonl")
    qualificados = {
        nome
        for nome, registro in e3.items()
        if registro["releases"] >= cfg.releases_min
    }
    parar = False
    for faixa, total in folhas:
        if parar:
            break
        if total == 0:
            continue
        rotulo = f"{faixa[0]}..{faixa[1]}" if faixa[1] else f"{faixa[0]}+"
        print(f"faixa de estrelas {rotulo}: {total} candidatos", flush=True)
        for item in busca.enumerar_faixa(cliente, cfg, faixa):
            if len(qualificados) >= alvo:
                parar = True
                break
            nome = item["full_name"]
            registro = e1.get(nome)
            if registro is None:
                if limite is not None and len(e1) >= limite:
                    parar = True
                    break
                candidato = busca.para_candidato(item, faixa)
                workflows = selecao.conta_workflows(cliente, nome)
                registro = {**candidato, "workflows": workflows}
                store.anexar(DIR_CK, "e1_workflows.jsonl", registro)
                e1[nome] = registro
                if len(e1) % 25 == 0:
                    print(
                        f"  escaneados={len(e1)} qualificados={len(qualificados)}",
                        flush=True,
                    )
            if registro["workflows"] == 0:
                continue
            corridas = e2.get(nome)
            if corridas is None:
                runs = selecao.conta_runs_push(
                    cliente, nome, registro.get("default_branch"), cfg.janela_runs
                )
                corridas = {"full_name": nome, "runs": runs}
                store.anexar(DIR_CK, "e2_runs.jsonl", corridas)
                e2[nome] = corridas
            if corridas["runs"] < cfg.runs_min:
                continue
            liberadas = e3.get(nome)
            if liberadas is None:
                releases = selecao.conta_releases(
                    cliente, nome, cfg.janela_inicio, cfg.janela_fim
                )
                liberadas = {"full_name": nome, "releases": releases}
                store.anexar(DIR_CK, "e3_releases.jsonl", liberadas)
                e3[nome] = liberadas
            if liberadas["releases"] >= cfg.releases_min:
                qualificados.add(nome)
                print(
                    f"  + qualificado ({len(qualificados)}/{alvo}): {nome}",
                    flush=True,
                )
    return e1, e2, e3, qualificados


def gerar_amostra(cliente, cfg, qualificados, e1_map):
    contribuidores = store.mapa(DIR_CK, "amostra_contribuidores.jsonl")
    for nome in sorted(qualificados):
        if nome in contribuidores:
            continue
        total = metadados.contar_contribuidores(cliente, nome)
        registro = {"full_name": nome, "contributors": total}
        store.anexar(DIR_CK, "amostra_contribuidores.jsonl", registro)
        contribuidores[nome] = registro
    linhas = []
    for nome in sorted(qualificados):
        registro = e1_map[nome]
        linhas.append(
            {
                "full_name": nome,
                "html_url": registro.get("html_url", ""),
                "stars": registro.get("stars", ""),
                "linguagem": registro.get("linguagem") or "",
                "idade_anos": metadados.idade_anos(
                    registro["created_at"], cfg.janela_fim
                ),
                "contributors": contribuidores[nome]["contributors"],
                "quartil_contribuidores": "",
                "created_at": registro.get("created_at", ""),
                "default_branch": registro.get("default_branch") or "",
                "faixa_estrelas": registro.get("faixa_estrelas", ""),
            }
        )
    limites, rotulos = metadados.quartis(
        [linha["contributors"] for linha in linhas]
    )
    for linha, rotulo in zip(linhas, rotulos):
        linha["quartil_contribuidores"] = rotulo
    with open(ARQ_AMOSTRA, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS_AMOSTRA)
        escritor.writeheader()
        escritor.writerows(linhas)
    meta = {
        "gerado_em": dt.datetime.now().isoformat(timespec="seconds"),
        "janela_inicio": cfg.janela_inicio.isoformat(),
        "janela_fim": cfg.janela_fim.isoformat(),
        "alvo_qualificados": cfg.alvo_qualificados,
        "n_repositorios": len(linhas),
        "ordem_varredura": cfg.ordem_varredura,
        "quartis_contribuidores": limites,
        "criterio_quartis": (
            "percentis 25/50/75 com interpolacao linear; "
            "valores iguais ao limite ficam no grupo inferior"
        ),
    }
    with open(ARQ_AMOSTRA_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return linhas


def gerar_funil(cfg, folhas, identificados, e1, e2, e3, qualificados, amostra, alvo):
    linhas = funil.montar_tabela(
        identificados=identificados,
        escaneados=len(e1),
        passaram_workflows=len(e2),
        passaram_runs=len(e3),
        qualificados=len(qualificados),
        amostra=len(amostra),
        alvo=alvo,
    )
    notas = [
        f"Janela de observacao: {cfg.janela_inicio.isoformat()} a {cfg.janela_fim.isoformat()} (12 meses).",
        f"Criterio de inclusao: >= {cfg.releases_min} releases publicadas "
        f"(draft=false e prerelease=false) e >= {cfg.runs_min} workflow runs de push "
        "no default branch dentro da janela.",
        "Pre-filtros da busca: stars >= 1000, fork:false, archived:false, "
        f"pushed:>= {cfg.janela_inicio.isoformat()}.",
        f"Alvo da sprint: {alvo} repositorios qualificados; ordem de varredura: "
        f"{cfg.ordem_varredura} (estrelas decrescentes).",
        "A varredura de candidatos e parcial por definicao: para ao atingir o alvo e "
        "e retomavel (checkpoints em data/checkpoints/).",
        "Candidatos por faixa de estrelas: "
        + "; ".join(
            f"{a}..{b if b else '+'} = {total}" for (a, b), total in folhas
        )
        + ".",
    ]
    funil.escrever_csv(ARQ_FUNIL_CSV, linhas)
    funil.escrever_md(ARQ_FUNIL_MD, linhas, notas)
    return linhas


def main():
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="Selecao de repositorios, metadados e funil (Issue #1).",
    )
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--smoke", action="store_true",
                        help="20 candidatos, 3 qualificados (teste de fumaca)")
    parser.add_argument("--max-candidatos", type=int, default=None,
                        help="limite de candidatos escaneados nesta execucao")
    parser.add_argument("--reiniciar", action="store_true",
                        help="apaga os checkpoints e recomeca do zero")
    parser.add_argument("--forcar-atualizacao", action="store_true",
                        help="ignora o cache de respostas nesta execucao")
    args = parser.parse_args()

    cfg = config.carregar(args.config)
    alvo = cfg.alvo_qualificados
    limite = cfg.limite_candidatos or None
    if args.smoke:
        alvo = 3
        limite = 20
    if args.max_candidatos:
        limite = args.max_candidatos

    store.preparar(DIR_CK, cfg, reiniciar=args.reiniciar)
    cliente = ClienteGitHub(
        cache_dir=cfg.cache_dir,
        forcar_global=args.forcar_atualizacao,
        timeout=cfg.timeout,
        backoff_base=cfg.backoff_base,
        backoff_cap=cfg.backoff_cap,
        backoff_max_tentativas=cfg.backoff_max_tentativas,
    )

    print(
        f"janela {cfg.janela_inicio}..{cfg.janela_fim} | alvo={alvo} | "
        f"limite_candidatos={limite or 'sem'}",
        flush=True,
    )
    inicio = time.time()
    folhas = busca.carregar_faixas(cliente, cfg, DIR_CK)
    identificados = sum(total for _, total in folhas)
    print(
        f"candidatos identificados: {identificados} em {len(folhas)} faixas de estrelas",
        flush=True,
    )

    e1, e2, e3, qualificados = varrer(cliente, cfg, folhas, alvo, limite)
    print(
        f"varredura concluida: escaneados={len(e1)} qualificados={len(qualificados)}",
        flush=True,
    )

    amostra = gerar_amostra(cliente, cfg, qualificados, e1)
    linhas = gerar_funil(
        cfg, folhas, identificados, e1, e2, e3, qualificados, amostra, alvo
    )

    print("", flush=True)
    for linha in linhas:
        print(
            f"{linha['etapa']}: {linha['saida']}"
            + (f" (descartados: {linha['descartados']})" if linha["descartados"] != "" else ""),
            flush=True,
        )
    print("", flush=True)
    print(f"amostra: {ARQ_AMOSTRA} ({len(amostra)} repositorios)", flush=True)
    print(f"funil:   {ARQ_FUNIL_CSV} e {ARQ_FUNIL_MD}", flush=True)
    print(
        f"chamadas de API: {cliente.chamadas} | "
        f"tempo: {time.time() - inicio:.0f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
