"""baixa - baixa vídeos do YouTube em MP3 ou MP4 pelo terminal.

Uso:
    baixa <link> <formato> [-o PASTA] [-n NOME] [-q compativel|max]

Exemplos:
    baixa https://www.youtube.com/watch?v=dQw4w9WgXcQ mp3
    baixa https://youtu.be/dQw4w9WgXcQ mp4 -o C:\\Videos -n "meu video"
"""

import argparse
import logging
import sys
from pathlib import Path

from baixa.nucleo import FORMATOS, ErroDownload, baixar


def mostrar_progresso(evento: dict) -> None:
    if evento["etapa"] == "convertendo":
        print("\nConvertendo...", flush=True)
        return
    porcentagem = evento["porcentagem"]
    texto = f"{porcentagem:5.1f}%" if porcentagem is not None else "  ?  "
    print(
        f"\rBaixando {texto}  {evento['velocidade']:>12}  ETA {evento['eta']:<8}",
        end="",
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="baixa",
        description="Baixa vídeos do YouTube em MP3 ou MP4.",
    )
    parser.add_argument("link", help="link do vídeo do YouTube")
    parser.add_argument("formato", choices=FORMATOS, type=str.lower, help="mp3 ou mp4")
    parser.add_argument(
        "-o",
        "--pasta",
        type=Path,
        default=Path.cwd(),
        help="pasta de destino (padrão: pasta atual)",
    )
    parser.add_argument(
        "-n",
        "--nome",
        help="nome do arquivo, sem extensão (padrão: título do vídeo)",
    )
    parser.add_argument(
        "-q",
        "--qualidade",
        choices=("compativel", "max"),
        default="compativel",
        type=str.lower,
        help="mp4: 'compativel' = H.264 até 1080p, abre em qualquer player (padrão); "
        "'max' = melhor qualidade disponível, até 4K/8K (VP9/AV1, pode não abrir em players antigos)",
    )
    args = parser.parse_args()
    qualidade = "maxima" if args.qualidade == "max" else "compativel"

    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    try:
        arquivo = baixar(
            args.link, args.formato, args.pasta, args.nome, mostrar_progresso, qualidade
        )
    except ErroDownload as erro:
        print(f"\nErro: não foi possível baixar o vídeo.\n{erro}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nDownload cancelado.", file=sys.stderr)
        return 130

    print(f"\nConcluído! Arquivo salvo em: {arquivo.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
