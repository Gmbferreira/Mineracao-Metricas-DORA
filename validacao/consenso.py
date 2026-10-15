import argparse
import os

import pandas as pd

from validacao import concordancia

DIR_VALIDACAO = "validacao"
ARQ_AMOSTRA = os.path.join(DIR_VALIDACAO, "amostra_ouro.csv")
ARQ_RELEASES = os.path.join(DIR_VALIDACAO, "releases_ouro.csv")
ARQ_DECISOES = os.path.join(DIR_VALIDACAO, "decisoes_desempate.csv")
ARQ_CONSENSO_REPOS = os.path.join(DIR_VALIDACAO, "consenso_repositorios.csv")
ARQ_CONSENSO_RELEASES = os.path.join(DIR_VALIDACAO, "consenso_releases.csv")

CABECALHO_DECISOES = ["dimensao", "id", "consenso", "motivo"]


def carregar_decisoes(caminho=ARQ_DECISOES):
    """Decisoes de desempate registradas na discussao (issue #12)."""
    if not os.path.exists(caminho):
        return pd.DataFrame(columns=CABECALHO_DECISOES)
    decisoes = pd.read_csv(caminho).fillna("")
    faltando = [c for c in CABECALHO_DECISOES if c not in decisoes.columns]
    if faltando:
        raise SystemExit(f"{caminho}: colunas ausentes {faltando}")
    return decisoes


def montar(rotulos_por_avaliador, decisoes=None):
    """Rotulo de consenso por dimensao: acordo dos avaliadores ou desempate.

    Devolve {dimensao: {id: rotulo}}. Toda divergencia precisa de uma linha em
    `decisoes` (`dimensao`, `id`, `consenso`, `motivo`), como manda o protocolo.
    """
    decisoes = pd.DataFrame(columns=CABECALHO_DECISOES) if decisoes is None else decisoes
    nomes = sorted(rotulos_por_avaliador)
    consenso = {}
    for dimensao, _, _, _, categorias in concordancia.DIMENSOES:
        valores = {nome: concordancia.normalizar(rotulos_por_avaliador[nome][dimensao],
                                                 categorias)
                   for nome in nomes}
        ids = sorted(next(iter(valores.values())))
        registradas = {}
        for linha in decisoes[decisoes["dimensao"] == dimensao].itertuples(index=False):
            if str(linha.consenso).strip().lower() not in {c.lower() for c in categorias}:
                raise SystemExit(
                    f"decisao de desempate com rotulo invalido: {dimensao} id {linha.id}"
                )
            registradas[int(linha.id)] = str(linha.consenso).strip()
        divergentes, resultado, sem_decisao = [], {}, []
        for ident in ids:
            escolhidos = {valores[nome][ident] for nome in nomes}
            if len(escolhidos) == 1:
                resultado[ident] = escolhidos.pop()
                continue
            divergentes.append(ident)
            if ident not in registradas:
                sem_decisao.append(ident)
            else:
                resultado[ident] = registradas[ident]
        sobrando = sorted(set(registradas) - set(divergentes))
        if sobrando:
            raise SystemExit(
                f"decisoes de desempate para casos sem divergencia: "
                f"{dimensao} {sobrando}"
            )
        if sem_decisao:
            raise SystemExit(
                f"divergencias sem decisao de desempate em {dimensao}: {sem_decisao}. "
                f"Registre cada uma em {ARQ_DECISOES} com o motivo."
            )
        consenso[dimensao] = resultado
    return consenso


def gerar(rotulos_por_avaliador, decisoes, amostra, releases):
    """Monta os dois DataFrames de consenso, prontos para virar CSV."""
    consenso = montar(rotulos_por_avaliador, decisoes)
    repos = amostra[["id_repo", "full_name"]].copy()
    repos["tipo_projeto"] = [consenso["tipo_projeto"][i] for i in repos["id_repo"]]
    repos["entregas_reais"] = [consenso["entregas_reais"][i] for i in repos["id_repo"]]
    tabela_releases = releases[["id_release", "full_name", "tag_name"]].copy()
    tabela_releases["corretiva"] = [consenso["corretiva"][i]
                                    for i in tabela_releases["id_release"]]
    return repos, tabela_releases


def main(diretorio=DIR_VALIDACAO, argv=None):
    parser = argparse.ArgumentParser(
        prog="validacao.consenso",
        description="Gera os CSVs de consenso (acordo + desempates) da amostra-ouro.",
    )
    parser.add_argument("--diretorio", default=diretorio)
    parser.add_argument("--decisoes", default=None)
    args = parser.parse_args(argv)
    dir_ = args.diretorio
    caminho_decisoes = args.decisoes or os.path.join(dir_, os.path.basename(ARQ_DECISOES))

    caminhos = concordancia.planilhas(dir_)
    faltando = [c for c in caminhos if not os.path.exists(c)]
    if faltando:
        raise SystemExit("Planilhas de rotulagem ausentes: " + ", ".join(faltando))
    todos, erros = {}, []
    for caminho in caminhos:
        rotulos = concordancia.ler_planilha(caminho)
        pendentes = concordancia.conferir(rotulos, os.path.basename(caminho))
        if pendentes:
            erros += pendentes
        else:
            nome = os.path.basename(caminho).removeprefix("rotulos_").removesuffix(".xlsx")
            todos[nome] = rotulos
    if erros:
        raise SystemExit("Rotulagem incompleta:\n- " + "\n- ".join(erros))

    amostra = pd.read_csv(os.path.join(dir_, os.path.basename(ARQ_AMOSTRA)))
    releases = pd.read_csv(os.path.join(dir_, os.path.basename(ARQ_RELEASES)))
    repos, tabela_releases = gerar(todos, carregar_decisoes(caminho_decisoes),
                                   amostra, releases)
    repos.to_csv(os.path.join(dir_, os.path.basename(ARQ_CONSENSO_REPOS)), index=False)
    tabela_releases.to_csv(os.path.join(dir_, os.path.basename(ARQ_CONSENSO_RELEASES)),
                           index=False)
    print(f"{len(repos)} repositorios e {len(tabela_releases)} releases de consenso; "
          f"sim em corretiva: {sum(tabela_releases['corretiva'] == 'sim')}", flush=True)


if __name__ == "__main__":
    main()
