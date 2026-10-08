import datetime as dt

import yaml


class Config:
    def __init__(self, dados):
        self.janela_inicio = dt.date.fromisoformat(str(dados["janela"]["inicio"]))
        self.janela_fim = dt.date.fromisoformat(str(dados["janela"]["fim"]))
        self.alvo_qualificados = int(dados["alvo_qualificados"])
        self.ordem_varredura = dados.get("ordem_varredura", "estrelas_desc")
        self.limite_candidatos = int(dados.get("limite_candidatos", 0) or 0)
        busca = dados["busca"]
        self.estrelas_min = int(busca["estrelas_min"])
        self.per_page_busca = int(busca.get("per_page", 100))
        self.max_resultados_por_faixa = int(busca.get("max_resultados_por_faixa", 1000))
        self.max_paginas_por_faixa = int(busca.get("max_paginas_por_faixa", 30))
        self.faixas_iniciais = [
            (int(a), None if b is None else int(b)) for a, b in busca["faixas"]
        ]
        self.pre_filtros = busca.get("pre_filtros", {}) or {}
        self.releases_min = int(dados["filtros"]["releases_min"])
        self.runs_min = int(dados["filtros"]["runs_min"])
        self.cache_dir = dados.get("cache_dir", "data/cache")
        rede = dados.get("rede", {}) or {}
        self.timeout = int(rede.get("timeout", 30))
        self.backoff_base = float(rede.get("backoff_base", 1))
        self.backoff_cap = int(rede.get("backoff_cap", 60))
        self.backoff_max_tentativas = int(rede.get("backoff_max_tentativas", 6))

    @property
    def janela_runs(self):
        return f"{self.janela_inicio.isoformat()}..{self.janela_fim.isoformat()}"

    def fingerprint(self):
        return {
            "janela_inicio": self.janela_inicio.isoformat(),
            "janela_fim": self.janela_fim.isoformat(),
            "estrelas_min": self.estrelas_min,
            "pre_filtros": self.pre_filtros,
            "faixas": [[a, b] for a, b in self.faixas_iniciais],
            "releases_min": self.releases_min,
            "runs_min": self.runs_min,
        }


def carregar(caminho):
    with open(caminho, encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    for chave in ("janela", "alvo_qualificados", "busca", "filtros"):
        if chave not in dados:
            raise SystemExit(f"config.yaml sem a chave obrigatoria: {chave}")
    return Config(dados)
