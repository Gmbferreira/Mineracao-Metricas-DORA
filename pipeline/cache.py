import hashlib
import json
import os
import time
import urllib

API = "https://api.github.com"


def _partes(url):
    base = url.replace(API, "").strip("/")
    return [parte for parte in base.split("/") if parte]


def grupo(url):
    partes = _partes(url)
    if partes and partes[0] == "repos" and len(partes) >= 3:
        return "__".join(partes[:3])
    return partes[0] if partes else "raiz"


def rotulo(url):
    partes = _partes(url)
    if partes and partes[0] == "repos" and len(partes) > 3:
        return "__".join(partes[3:])
    return ""


class CacheRespostas:
    def __init__(self, diretorio):
        self.diretorio = diretorio

    def grupo(self, url):
        return grupo(url)

    def chave(self, url, params=None):
        ordenados = sorted((params or {}).items())
        consulta = urllib.parse.urlencode(ordenados)
        return hashlib.sha1(f"{url}?{consulta}".encode("utf-8")).hexdigest()[:16]

    def _caminho(self, grupo_url, url, chave):
        # o hash ja identifica a resposta; cortar o rotulo evita estourar o
        # limite de caminho do Windows com nomes de tag longos no compare
        etiqueta = rotulo(url)[:60]
        nome = f"{etiqueta}__{chave}.json" if etiqueta else f"{chave}.json"
        return os.path.join(self.diretorio, grupo_url, nome)

    def obter(self, grupo_url, url, chave):
        try:
            with open(self._caminho(grupo_url, url, chave), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def salvar(self, grupo_url, url, chave, conteudo):
        caminho = self._caminho(grupo_url, url, chave)
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        temporario = caminho + ".tmp"
        with open(temporario, "w", encoding="utf-8") as f:
            json.dump(conteudo, f, ensure_ascii=False)
        substituir(temporario, caminho)


def substituir(temporario, caminho, tentativas=8, espera=0.25):
    # no Windows o antivirus ou o indexador podem segurar o arquivo recem
    # gravado por alguns instantes; os.replace falha com WinError 32
    for tentativa in range(tentativas):
        try:
            os.replace(temporario, caminho)
            return
        except PermissionError:
            if tentativa == tentativas - 1:
                raise
            time.sleep(espera * (2 ** tentativa))