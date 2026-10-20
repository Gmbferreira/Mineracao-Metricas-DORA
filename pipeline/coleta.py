import csv
import datetime as dt
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from pipeline import notas, releases, runs, variantes
from pipeline.cache import substituir

PARALELO_INTERNO = 3


def arquivo_repo(dir_coleta, nome):
    return os.path.join(dir_coleta, nome.replace("/", "__") + ".json")


def janela(cfg):
    return {"inicio": cfg.janela_inicio.isoformat(), "fim": cfg.janela_fim.isoformat()}


def carregar(dir_coleta, nome, cfg):
    try:
        with open(arquivo_repo(dir_coleta, nome), encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return None
    if dados.get("janela") != janela(cfg):
        return None
    return dados


def salvar(dir_coleta, nome, dados):
    os.makedirs(dir_coleta, exist_ok=True)
    caminho = arquivo_repo(dir_coleta, nome)
    temporario = caminho + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False)
    substituir(temporario, caminho)


def ler_amostra(caminho):
    with open(caminho, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def coletar_repo(cliente, cfg, nome, default_branch, paralelo=1):
    # dentro de um repositorio, no maximo 3 requisicoes ao mesmo tempo: com
    # varios repositorios em paralelo, isso fica abaixo do limite de
    # requisicoes simultaneas do GitHub
    paralelo = min(paralelo, PARALELO_INTERNO)
    coletadas = releases.coletar_releases(
        cliente, nome, cfg.janela_inicio, cfg.janela_fim, paralelo=paralelo
    )
    execucoes = runs.coletar_runs(
        cliente, nome, default_branch, cfg.janela_inicio, cfg.janela_fim,
        paralelo=paralelo,
    )
    dados = {
        "full_name": nome,
        "default_branch": default_branch,
        "janela": janela(cfg),
        "coletado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "releases": coletadas["releases"],
        "avaliadas": coletadas["avaliadas"],
        "notas": coletar_notas_da_janela(cliente, cfg, nome, coletadas["avaliadas"]),
        "runs": execucoes["runs"],
        "intervalos_runs": execucoes["intervalos"],
        "intervalos_no_teto": execucoes["intervalos_no_teto"],
        "acesso_runs": execucoes["acesso"],
    }
    completar_variantes(cliente, cfg, dados)
    return dados


def completar_variantes(cliente, cfg, dados):
    """Pre-releases e tags (unidades de deploy da RQ 07), junto do resto da coleta."""
    resultado = variantes.coletar_variantes(
        cliente, dados["full_name"], cfg.janela_inicio, cfg.janela_fim, dados,
        paralelo=PARALELO_INTERNO,
    )
    dados.setdefault("notas", {}).update(resultado.pop("notas"))
    dados["variantes"] = resultado


def coletar_notas_da_janela(cliente, cfg, nome, avaliadas):
    tags = [item["tag_name"] for item in avaliadas]
    return notas.coletar_notas(cliente, nome, cfg.janela_inicio, tags)


def coletar_amostra(cliente, cfg, amostra, dir_coleta, limite=None, paralelo=1):
    """Coleta releases, commits e runs de cada repositorio da amostra.

    Cada repositorio vira um JSON em `dir_coleta`; os ja coletados nesta
    janela sao pulados, entao rodar de novo continua de onde parou. Um erro
    num repositorio nao interrompe os demais. Com `paralelo` > 1, varios
    repositorios (e, dentro de cada um, os meses e os compares) sao coletados
    ao mesmo tempo; a cota da API continua sendo respeitada pelo cliente.
    """
    linhas = amostra[:limite] if limite else amostra
    trava = threading.Lock()
    erros = []

    def processar(posicao, linha):
        nome = linha["full_name"]
        dados = carregar(dir_coleta, nome, cfg)
        origem = "ja coletado"
        try:
            if dados is None:
                dados = coletar_repo(
                    cliente, cfg, nome, linha.get("default_branch"), paralelo
                )
                salvar(dir_coleta, nome, dados)
                origem = "coletado agora"
            else:
                # coletas antigas nao tinham as release notes (Sprint 02) nem as
                # unidades de deploy da RQ 07 (Sprint 03)
                completou = []
                if "notas" not in dados:
                    dados["notas"] = coletar_notas_da_janela(cliente, cfg, nome, dados["avaliadas"])
                    completou.append("notas")
                if "variantes" not in dados:
                    completar_variantes(cliente, cfg, dados)
                    completou.append("variantes")
                if completou:
                    salvar(dir_coleta, nome, dados)
                    origem = f"ja coletado, {' e '.join(completou)} coletadas agora"
        except (RuntimeError, OSError) as erro:
            with trava:
                print(f"  [{posicao}/{len(linhas)}] {nome}: erro ({erro})", flush=True)
                erros.append({"full_name": nome, "erro": str(erro)[:300]})
            return None
        with trava:
            print(
                f"  [{posicao}/{len(linhas)}] {nome}: {len(dados['avaliadas'])} releases "
                f"na janela, {len(dados['runs'])} runs ({origem})",
                flush=True,
            )
        return dados

    with ThreadPoolExecutor(max_workers=max(1, paralelo)) as executor:
        resultados = list(executor.map(processar, range(1, len(linhas) + 1), linhas))
    coletados = [dados for dados in resultados if dados is not None]
    return coletados, erros
