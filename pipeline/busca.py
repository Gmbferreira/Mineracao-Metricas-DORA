from pipeline import store


def filtros_base(cfg):
    partes = []
    pre = cfg.pre_filtros
    if pre.get("fork") is False:
        partes.append("fork:false")
    if pre.get("archived") is False:
        partes.append("archived:false")
    if pre.get("pushed_apos_inicio"):
        partes.append(f"pushed:>={cfg.janela_inicio.isoformat()}")
    return " ".join(partes)


def consulta_total(cfg):
    base = filtros_base(cfg)
    return f"stars:>={cfg.estrelas_min} {base}".strip()


def consulta_faixa(cfg, faixa):
    a, b = faixa
    qualificador = f"stars:{a}..{b}" if b is not None else f"stars:>={a}"
    base = filtros_base(cfg)
    return f"{qualificador} {base}".strip()


def contar(cliente, consulta):
    dados = cliente.buscar(consulta, per_page=1, pagina=1)
    return int(dados.get("total_count", 0))


def dividir_faixa(faixa):
    a, b = faixa
    if b is None:
        return [(a, a * 2), (a * 2 + 1, None)]
    if a >= b:
        return None
    meio = (a + b) // 2
    return [(a, meio), (meio + 1, b)]


def faixas_folha(cliente, cfg, faixa=None, nivel=0):
    if faixa is None:
        folhas = []
        for faixa_inicial in cfg.faixas_iniciais:
            folhas.extend(faixas_folha(cliente, cfg, faixa_inicial, 0))
        return folhas
    total = contar(cliente, consulta_faixa(cfg, faixa))
    if total <= cfg.max_resultados_por_faixa:
        return [(faixa, total)]
    partes = dividir_faixa(faixa)
    if partes is None or nivel > 30:
        return [(faixa, total)]
    folhas = []
    for parte in partes:
        folhas.extend(faixas_folha(cliente, cfg, parte, nivel + 1))
    return folhas


def carregar_faixas(cliente, cfg, dir_ck):
    caminho = "faixas.json"
    existentes = store.ler(dir_ck, caminho)
    if existentes:
        return [(tuple(item["faixa"]), item["total"]) for item in existentes]
    folhas = faixas_folha(cliente, cfg)
    folhas.sort(key=lambda par: par[0][0], reverse=True)
    store.escrever_tudo(
        dir_ck,
        caminho,
        [{"faixa": [a, b], "total": total} for (a, b), total in folhas],
    )
    return folhas


def para_candidato(item, faixa):
    return {
        "full_name": item["full_name"],
        "html_url": item["html_url"],
        "stars": item["stargazers_count"],
        "linguagem": item.get("language"),
        "created_at": item["created_at"],
        "default_branch": item.get("default_branch"),
        "faixa_estrelas": f"{faixa[0]}..{faixa[1]}" if faixa[1] else f"{faixa[0]}+",
    }


def enumerar_faixa(cliente, cfg, faixa):
    consulta = consulta_faixa(cfg, faixa)
    itens = []
    pagina = 1
    while pagina <= cfg.max_paginas_por_faixa:
        dados = cliente.buscar(consulta, per_page=cfg.per_page_busca, pagina=pagina)
        pagina_itens = dados.get("items", [])
        itens.extend(pagina_itens)
        if len(pagina_itens) < cfg.per_page_busca:
            break
        if len(itens) >= int(dados.get("total_count", 0)):
            break
        pagina += 1
    return itens
