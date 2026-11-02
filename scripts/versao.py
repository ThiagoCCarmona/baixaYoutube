"""Ferramentas de versão usadas localmente e pelo CI.

  python scripts/versao.py atual                 imprime a versão do app
  python scripts/versao.py definir 0.5.0         define a versão do app
  python scripts/versao.py patch                 incrementa o último número (0.4.0 -> 0.4.1)
  python scripts/versao.py ytdlp-fixado          imprime a versão do yt-dlp em requirements-build.txt
  python scripts/versao.py fixar-ytdlp 2026.11.1 troca a versão do yt-dlp em requirements-build.txt
"""

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INIT = RAIZ / "baixa" / "__init__.py"
REQUISITOS = RAIZ / "requirements-build.txt"

PADRAO_VERSAO = re.compile(r'^__version__ = "([^"]+)"', re.M)
PADRAO_YTDLP = re.compile(r"^(yt-dlp\[[^\]]*\]==)(\S+)", re.M)


def ler(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


def gravar(caminho: Path, texto: str) -> None:
    caminho.write_text(texto, encoding="utf-8", newline="\n")


def versao_atual() -> str:
    return PADRAO_VERSAO.search(ler(INIT)).group(1)


def definir(nova: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", nova):
        raise SystemExit(f"Versão inválida: {nova} (use X.Y.Z)")
    gravar(INIT, PADRAO_VERSAO.sub(f'__version__ = "{nova}"', ler(INIT), count=1))


def main(argumentos: list) -> None:
    comando = argumentos[0] if argumentos else "atual"
    if comando == "atual":
        print(versao_atual())
    elif comando == "definir":
        definir(argumentos[1])
        print(versao_atual())
    elif comando == "patch":
        maior, menor, correcao = map(int, versao_atual().split("."))
        definir(f"{maior}.{menor}.{correcao + 1}")
        print(versao_atual())
    elif comando == "ytdlp-fixado":
        print(PADRAO_YTDLP.search(ler(REQUISITOS)).group(2))
    elif comando == "fixar-ytdlp":
        gravar(REQUISITOS, PADRAO_YTDLP.sub(rf"\g<1>{argumentos[1]}", ler(REQUISITOS), count=1))
        print(PADRAO_YTDLP.search(ler(REQUISITOS)).group(2))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
