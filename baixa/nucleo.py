"""Núcleo de download: sem print nem interface, reaproveitável por CLI, GUI ou mobile."""

import logging
from pathlib import Path
from typing import Callable, Optional

import imageio_ffmpeg
import yt_dlp
from yt_dlp.utils import sanitize_filename

from baixa.erros import ErroDownload

FORMATOS = ("mp3", "mp4")
# "compativel": MP4 em H.264 + AAC (abre em qualquer player; no YouTube vai até 1080p).
# "maxima": melhor vídeo e áudio de qualquer codec (VP9/AV1 até 4K/8K) — só afeta o MP4.
QUALIDADES = ("compativel", "maxima")

log = logging.getLogger("baixa.nucleo")


__all__ = ["FORMATOS", "QUALIDADES", "ErroDownload", "baixar", "opcoes_ytdlp"]


class _LoggerYtdlp:
    """Encaminha as mensagens do yt-dlp para o logging (não depende de console)."""

    def debug(self, msg):
        log.debug(msg)

    def info(self, msg):
        log.info(msg)

    def warning(self, msg):
        log.warning(msg)

    def error(self, msg):
        log.error(msg)


def opcoes_ytdlp(
    formato: str, pasta: Path, nome: Optional[str] = None, qualidade: str = "compativel"
) -> dict:
    nome = sanitize_filename(nome.strip(), restricted=False) if nome and nome.strip() else ""
    modelo = f"{nome}.%(ext)s" if nome else "%(title)s.%(ext)s"
    opcoes = {
        "outtmpl": str(pasta / modelo),
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
        "noplaylist": True,
        "windowsfilenames": True,
        "noprogress": True,
        "logger": _LoggerYtdlp(),
        # Usa Deno ou Node se estiverem instalados; sem eles, alguns formatos podem faltar.
        "js_runtimes": {"deno": {}, "node": {}},
    }
    if formato == "mp3":
        opcoes["format"] = "bestaudio/best"
        opcoes["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    elif qualidade == "maxima":
        opcoes["format"] = "bv*+ba/b"
        opcoes["merge_output_format"] = "mp4"
    else:
        # Prefere vídeo H.264 + áudio AAC para máxima compatibilidade com players.
        opcoes["format"] = (
            "bv*[ext=mp4][vcodec^=avc]+ba[ext=m4a]/"
            "bv*[ext=mp4]+ba[ext=m4a]/"
            "bv*+ba/b"
        )
        opcoes["merge_output_format"] = "mp4"
    return opcoes


def baixar(
    link: str,
    formato: str,
    pasta: Path,
    nome: Optional[str] = None,
    ao_progresso: Optional[Callable[[dict], None]] = None,
    qualidade: str = "compativel",
) -> Path:
    """Baixa o vídeo e devolve o caminho do arquivo final.

    `ao_progresso` recebe dicts como:
      {"etapa": "baixando", "porcentagem": 42.0, "velocidade": "1.2MiB/s", "eta": "00:05"}
      {"etapa": "convertendo"}
    """
    formato = formato.lower()
    if formato not in FORMATOS:
        raise ValueError(f"Formato inválido: {formato!r} (use mp3 ou mp4)")
    if qualidade not in QUALIDADES:
        raise ValueError(f"Qualidade inválida: {qualidade!r} (use compativel ou maxima)")
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)

    opcoes = opcoes_ytdlp(formato, pasta, nome, qualidade)

    if ao_progresso:

        def gancho_download(d):
            if d["status"] != "downloading":
                return
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            porcentagem = d["downloaded_bytes"] / total * 100 if total else None
            ao_progresso(
                {
                    "etapa": "baixando",
                    "porcentagem": porcentagem,
                    "velocidade": (d.get("_speed_str") or "").strip(),
                    "eta": (d.get("_eta_str") or "").strip(),
                }
            )

        def gancho_pos(d):
            if d["status"] == "started":
                ao_progresso({"etapa": "convertendo"})

        opcoes["progress_hooks"] = [gancho_download]
        opcoes["postprocessor_hooks"] = [gancho_pos]

    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(link, download=True)
    except yt_dlp.utils.DownloadError as erro:
        mensagem = str(erro).removeprefix("ERROR: ").strip()
        raise ErroDownload(mensagem) from erro

    downloads = info.get("requested_downloads") or [{}]
    caminho = downloads[0].get("filepath") or info.get("filepath")
    if not caminho:
        raise ErroDownload("Download terminou, mas o arquivo final não foi encontrado.")
    return Path(caminho)
