import csv
import datetime as dt
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from pipeline import releases, runs
from pipeline.cache import substituir


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
    coletadas = releases.coletar_releases(
        cliente, nome, cfg.janela_inicio, cfg.janela_fim, paralelo=paralelo
    )
    execucoes = runs.coletar_runs(
        cliente, nome, default_branch, cfg.janela_inicio, cfg.janela_fim,
        paralelo=paralelo,
    )
    return {
        "full_name": nome,
        "default_branch": default_branch,
        "janela": janela(cfg),
        "coletado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "releases": coletadas["releases"],
        "avaliadas": coletadas["avaliadas"],
        "runs": execucoes["runs"],
        "intervalos_runs": execucoes["intervalos"],
        "intervalos_no_teto": execucoes["intervalos_no_teto"],
        "acesso_runs": execucoes["acesso"],
    }


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
        if dados is None:
            try:
                dados = coletar_repo(
                    cliente, cfg, nome, linha.get("default_branch"), paralelo
                )
                salvar(dir_coleta, nome, dados)
            except (RuntimeError, OSError) as erro:
                with trava:
                    print(f"  [{posicao}/{len(linhas)}] {nome}: erro ({erro})", flush=True)
                    erros.append({"full_name": nome, "erro": str(erro)[:300]})
                return None
            origem = "coletado agora"
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
