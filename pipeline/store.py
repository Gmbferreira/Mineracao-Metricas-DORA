import json
import os

META = "meta.json"


def _caminho(dir_ck, nome):
    return os.path.join(dir_ck, nome)


def preparar(dir_ck, cfg, reiniciar=False):
    os.makedirs(dir_ck, exist_ok=True)
    if reiniciar:
        for nome in os.listdir(dir_ck):
            os.remove(_caminho(dir_ck, nome))
    meta = _caminho(dir_ck, META)
    fingerprint = cfg.fingerprint()
    if os.path.exists(meta):
        with open(meta, encoding="utf-8") as f:
            atual = json.load(f)
        if atual != fingerprint:
            raise SystemExit(
                "Checkpoints em data/checkpoints/ pertencem a outra janela ou "
                "configuracao. Rode com --reiniciar para limpar."
            )
    else:
        with open(meta, "w", encoding="utf-8") as f:
            json.dump(fingerprint, f, indent=2, ensure_ascii=False)


def ler(dir_ck, nome):
    caminho = _caminho(dir_ck, nome)
    if not os.path.exists(caminho):
        return []
    itens = []
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha:
                itens.append(json.loads(linha))
    return itens


def anexar(dir_ck, nome, obj):
    with open(_caminho(dir_ck, nome), "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def escrever_tudo(dir_ck, nome, objs):
    with open(_caminho(dir_ck, nome), "w", encoding="utf-8") as f:
        for obj in objs:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def mapa(dir_ck, nome):
    return {obj["full_name"]: obj for obj in ler(dir_ck, nome)}
