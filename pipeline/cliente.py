import json
import os
import time

import requests

from pipeline.cache import CacheRespostas

API = "https://api.github.com"
VERSAO_API = "2022-11-28"
CABECALHOS_CACHE = (
    "Link",
    "X-RateLimit-Resource",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset",
)


class RespostaCache:
    def __init__(self, bloco):
        self._bloco = bloco

    @property
    def status_code(self):
        return self._bloco["status_code"]

    @property
    def headers(self):
        return self._bloco.get("headers", {})

    def json(self):
        dados = self._bloco.get("dados")
        if isinstance(dados, str):
            return json.loads(dados)
        return dados


class ClienteGitHub:
    def __init__(
        self,
        token=None,
        intervalo_busca=2.1,
        cache_dir="data/cache",
        forcar_global=False,
        timeout=30,
        backoff_base=1,
        backoff_cap=60,
        backoff_max_tentativas=6,
    ):
        self.token = (
            token
            or os.environ.get("GITHUB_TOKEN")
            or os.environ.get("GH_TOKEN")
        )
        if not self.token:
            raise SystemExit(
                "GITHUB_TOKEN nao definido no ambiente. "
                "Exporte a variavel antes de rodar o pipeline."
            )
        self.sessao = requests.Session()
        adaptador = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=64)
        self.sessao.mount("https://", adaptador)
        self.sessao.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": VERSAO_API,
                "User-Agent": "mineracao-dora-pipeline",
            }
        )
        self.cache = CacheRespostas(cache_dir) if cache_dir else None
        self.intervalo_busca = intervalo_busca
        self._ultima_busca = 0.0
        self._chamadas = 0
        self._forcar = forcar_global
        self._timeout = timeout
        self.backoff_base = backoff_base
        self.backoff_cap = backoff_cap
        self.backoff_max_tentativas = backoff_max_tentativas
        self._limites = {}

    @property
    def chamadas(self):
        return self._chamadas

    def _atualizar_limites(self, resposta):
        recurso = resposta.headers.get("X-RateLimit-Resource")
        restante = resposta.headers.get("X-RateLimit-Remaining")
        reset = resposta.headers.get("X-RateLimit-Reset")
        if recurso and restante is not None and reset is not None:
            self._limites[recurso] = {
                "remaining": int(restante),
                "reset": int(reset),
            }

    def _aguardar_cota(self, recurso):
        limite = self._limites.get(recurso)
        if not limite or limite["remaining"] > 0:
            return
        tempo = max(1.0, limite["reset"] - time.time() + 1)
        time.sleep(tempo)

    def _dormir_backoff(self, tentativa):
        espera = min(self.backoff_base * (2 ** tentativa), self.backoff_cap)
        time.sleep(espera)

    def _esperar_cota(self, resposta, tentativa):
        if resposta.status_code not in (403, 429):
            return False
        retry_after = resposta.headers.get("Retry-After")
        if retry_after:
            time.sleep(int(retry_after) + 1)
            return True
        if resposta.headers.get("X-RateLimit-Remaining") == "0":
            reset = int(resposta.headers.get("X-RateLimit-Reset", "0"))
            time.sleep(max(1.0, reset - time.time() + 1))
            return True
        self._dormir_backoff(tentativa)
        return True

    def _bloco_para_cache(self, url, params, resposta, reduzir=None):
        cabecalhos = {
            chave: resposta.headers[chave]
            for chave in CABECALHOS_CACHE
            if chave in resposta.headers
        }
        dados = _json_ou_texto(resposta)
        if reduzir is not None:
            dados = reduzir(dados)
        return {
            "url": url,
            "params": dict(params or {}),
            "status_code": resposta.status_code,
            "headers": cabecalhos,
            "dados": dados,
            "salvo_em": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def get(self, caminho, params=None, busca=False, aceitar=(), forcar=False,
            reduzir=None):
        url = caminho if caminho.startswith("http") else API + caminho
        recurso = "search" if busca else "core"
        grupo_url = chave = None
        if self.cache and not (forcar or self._forcar):
            grupo_url = self.cache.grupo(url)
            chave = self.cache.chave(url, params)
            bloco = self.cache.obter(grupo_url, url, chave)
            if bloco is not None and bloco.get("status_code") == 200:
                return RespostaCache(bloco)
        for tentativa in range(self.backoff_max_tentativas):
            self._aguardar_cota(recurso)
            if busca:
                espera = self.intervalo_busca - (time.time() - self._ultima_busca)
                if espera > 0:
                    time.sleep(espera)
                self._ultima_busca = time.time()
            try:
                resposta = self.sessao.get(url, params=params, timeout=self._timeout)
            except requests.RequestException:
                self._dormir_backoff(tentativa)
                continue
            self._chamadas += 1
            self._atualizar_limites(resposta)
            if resposta.status_code == 200:
                bloco = None
                if self.cache or reduzir is not None:
                    bloco = self._bloco_para_cache(url, params, resposta, reduzir)
                if self.cache:
                    if chave is None:
                        grupo_url = self.cache.grupo(url)
                        chave = self.cache.chave(url, params)
                    self.cache.salvar(grupo_url, url, chave, bloco)
                if reduzir is not None:
                    return RespostaCache(bloco)
                return resposta
            if self._esperar_cota(resposta, tentativa):
                continue
            if resposta.status_code in aceitar:
                return resposta
            if 500 <= resposta.status_code < 600:
                self._dormir_backoff(tentativa)
                continue
            raise RuntimeError(
                f"GET {url} -> HTTP {resposta.status_code}: {resposta.text[:300]}"
            )
        raise RuntimeError(
            f"GET {url}: tentativas esgotadas ({self.backoff_max_tentativas})"
        )

    def buscar(self, consulta, per_page=100, pagina=1):
        resposta = self.get(
            "/search/repositories",
            {
                "q": consulta,
                "per_page": per_page,
                "page": pagina,
                "sort": "stars",
                "order": "desc",
            },
            busca=True,
        )
        return resposta.json()


def _json_ou_texto(resposta):
    try:
        return resposta.json()
    except ValueError:
        return resposta.text


def ultima_pagina(link_header):
    if not link_header:
        return None
    for parte in link_header.split(","):
        if 'rel="last"' not in parte:
            continue
        url = parte.split("<", 1)[1].split(">", 1)[0]
        consulta = url.split("?", 1)[1] if "?" in url else ""
        for parametro in consulta.split("&"):
            if parametro.startswith("page="):
                return int(parametro.split("=", 1)[1])
    return None