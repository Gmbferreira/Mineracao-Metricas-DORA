import argparse
import os

import pandas as pd
from openpyxl import load_workbook
from statsmodels.stats.inter_rater import aggregate_raters, fleiss_kappa

from validacao.sorteio import AVALIADORES, CORRETIVA, ENTREGAS_REAIS, TIPOS_PROJETO

DIR_VALIDACAO = "validacao"

# (dimensao, aba da planilha, coluna do rotulo, itens esperados, categorias)
DIMENSOES = (
    ("tipo_projeto", "repositorios", 4, 60, TIPOS_PROJETO),
    ("entregas_reais", "repositorios", 5, 60, ENTREGAS_REAIS),
    ("corretiva", "releases", 8, 300, CORRETIVA),
)
COLUNA_ID = 1


def planilhas(diretorio=DIR_VALIDACAO, avaliadores=AVALIADORES):
    return [os.path.join(diretorio, f"rotulos_{nome}.xlsx") for nome in avaliadores]


def ler_planilha(caminho):
    """Le uma planilha de rotulagem -> {dimensao: Series indexada por id}."""
    livro = load_workbook(caminho, read_only=True)
    rotulos = {}
    for nome, aba, col_rotulo, _, _ in DIMENSOES:
        ws = livro[aba]
        valores = {}
        for linha in ws.iter_rows(min_row=2, min_col=COLUNA_ID, max_col=col_rotulo,
                                  values_only=True):
            ident = linha[COLUNA_ID - 1]
            if ident is None:
                continue
            valores[int(ident)] = linha[col_rotulo - 1]
        rotulos[nome] = pd.Series(valores, dtype=object).sort_index()
    livro.close()
    return rotulos


def conferir(rotulos, caminho=""):
    """Erros de completude e de valores de uma planilha; [] quando esta pronta."""
    erros = []
    for nome, _, _, n_esperado, categorias in DIMENSOES:
        permitidos = {c.lower() for c in categorias}
        serie = rotulos.get(nome, pd.Series(dtype=object))
        preenchidos = [v for v in serie if v is not None and str(v).strip() != ""]
        if len(preenchidos) != n_esperado:
            erros.append(f"{caminho} {nome}: {len(preenchidos)}/{n_esperado} preenchidos")
        fora = sorted({str(v).strip() for v in preenchidos
                       if str(v).strip().lower() not in permitidos})
        if fora:
            erros.append(f"{caminho} {nome}: valores fora da lista {fora}")
    return erros


def normalizar(serie, categorias):
    canonicos = {c.lower(): c for c in categorias}
    mapeado = {}
    invalidos = []
    for ident, valor in serie.items():
        if valor is None or str(valor).strip() == "":
            invalidos.append(ident)
            continue
        texto = str(valor).strip().lower()
        if texto not in canonicos:
            invalidos.append(ident)
            continue
        mapeado[ident] = canonicos[texto]
    if invalidos:
        raise SystemExit(f"rotulos ausentes/invalidos nos ids: {invalidos}")
    return mapeado


def calcular(rotulos_por_avaliador, dimensao):
    """Kappa de Fleiss, concordancia bruta e divergencias de uma dimensao.

    `rotulos_por_avaliador` mapeia nome do avaliador -> {dimensao: Series}.
    Concordancia bruta = fracao de itens com unanimidade dos avaliadores.
    """
    categorias = next(c[4] for c in DIMENSOES if c[0] == dimensao)
    nomes = sorted(rotulos_por_avaliador)
    valores = {nome: normalizar(rotulos_por_avaliador[nome][dimensao], categorias)
               for nome in nomes}
    ids = sorted(next(iter(valores.values())))
    for nome in nomes:
        if sorted(valores[nome]) != ids:
            raise SystemExit(f"ids divergentes entre planilhas na dimensao {dimensao}")

    codigos = {c: i for i, c in enumerate(categorias)}
    matriz = [[codigos[valores[nome][ident]] for nome in nomes] for ident in ids]
    tabela, _ = aggregate_raters(matriz, n_cat=len(categorias))
    kappa = float(fleiss_kappa(tabela))
    unanimidade = [ident for ident, linha in zip(ids, matriz) if len(set(linha)) == 1]
    bruta = len(unanimidade) / len(ids) if ids else float("nan")
    linhas = [
        {"id": ident, **{nome: valores[nome][ident] for nome in nomes}}
        for ident in ids if ident not in set(unanimidade)
    ]
    return {
        "dimensao": dimensao,
        "itens": len(ids),
        "avaliadores": len(nomes),
        "concordancia_bruta": bruta,
        "kappa": kappa,
        "interpretacao": interpretar(kappa),
        "divergencias": pd.DataFrame(linhas),
    }


def interpretar(kappa):
    """Escala de Landis & Koch (1977), como no enunciado."""
    if kappa < 0:
        return "pobre"
    if kappa <= 0.20:
        return "leve"
    if kappa <= 0.40:
        return "razoavel"
    if kappa <= 0.60:
        return "moderada"
    if kappa <= 0.80:
        return "substancial"
    return "quase perfeita"


def main(diretorio=DIR_VALIDACAO, argv=None):
    parser = argparse.ArgumentParser(
        prog="validacao.concordancia",
        description="Calcula o kappa de Fleiss entre os avaliadores da amostra-ouro.",
    )
    parser.add_argument("--diretorio", default=diretorio)
    args = parser.parse_args(argv)

    faltando = [c for c in planilhas(args.diretorio) if not os.path.exists(c)]
    if faltando:
        raise SystemExit(
            "Planilhas de rotulagem ausentes: " + ", ".join(faltando)
            + ". Termine a rotulagem (issues #10 e #11) antes de calcular a concordancia."
        )
    todos, erros = {}, []
    for caminho in planilhas(args.diretorio):
        rotulos = ler_planilha(caminho)
        pendentes = conferir(rotulos, os.path.basename(caminho))
        if pendentes:
            erros += pendentes
        else:
            nome = os.path.basename(caminho).removeprefix("rotulos_").removesuffix(".xlsx")
            todos[nome] = rotulos
    if erros:
        raise SystemExit("Rotulagem incompleta:\n- " + "\n- ".join(erros)
                         + "\nComplete as planilhas antes de calcular a concordancia.")

    print(f"avaliadores: {', '.join(sorted(todos))}")
    print(f"{'dimensao':<16} {'itens':>5} {'unanim.':>8} {'kappa':>7}  interpretacao")
    for nome, _, _, _, _ in DIMENSOES:
        r = calcular(todos, nome)
        print(f"{nome:<16} {r['itens']:>5} {r['concordancia_bruta']:>7.1%} "
              f"{r['kappa']:>7.3f}  {r['interpretacao']}")
        div = r["divergencias"]
        if len(div):
            print(f"  divergencias ({len(div)}):")
            for linha in div.itertuples(index=False):
                dados = ", ".join(f"{campo}={valor}" for campo, valor in
                                  zip(linha._fields[1:], linha[1:]))
                print(f"    id {linha.id}: {dados}")


if __name__ == "__main__":
    main()
