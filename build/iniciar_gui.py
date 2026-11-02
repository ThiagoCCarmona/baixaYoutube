"""Ponto de entrada do executável (PyInstaller).

Modos sem janela (usados pelo atualizador e pelo CI):
  --validar-motor PASTA   valida um yt-dlp baixado (PASTA vazia = o embutido); código 0 = ok
  --verificar ARQUIVO     checagem offline do pacote (imports, extratores, ffmpeg)
  --autoteste PASTA       baixa um vídeo curto em MP3 e MP4 e grava PASTA/autoteste.txt
  --atualizar-motor ARQ   procura, valida e ativa um yt-dlp mais novo agora; grava o resultado em ARQ
"""

import sys

if len(sys.argv) == 3 and sys.argv[1] == "--validar-motor":
    from baixa.atualizador import validar_motor

    sys.exit(validar_motor(sys.argv[2] or None))

from baixa import atualizador  # noqa: E402

atualizador.ativar_motor()


def verificar(arquivo: str) -> int:
    import subprocess
    import traceback
    from pathlib import Path

    linhas = []
    codigo = 0
    try:
        import customtkinter  # noqa: F401
        import imageio_ffmpeg
        import yt_dlp
        from yt_dlp.extractor import gen_extractor_classes

        import baixa.nucleo  # noqa: F401

        extratores = len(list(gen_extractor_classes()))
        linhas.append(f"OK yt-dlp {yt_dlp.version.__version__} ({extratores} extratores)")
        if extratores < 500:
            codigo = 1
            linhas.append("FALHA poucos extratores carregados")
        ffmpeg = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-version"], capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        linhas.append(f"{'OK' if ffmpeg.returncode == 0 else 'FALHA'} {ffmpeg.stdout.splitlines()[0]}")
        codigo |= ffmpeg.returncode != 0
    except Exception:
        codigo = 1
        linhas.append(f"FALHA\n{traceback.format_exc()}")
    Path(arquivo).write_text("\n".join(linhas), encoding="utf-8")
    return codigo


def autoteste(pasta: str) -> int:
    import traceback
    from pathlib import Path

    destino = Path(pasta)
    destino.mkdir(parents=True, exist_ok=True)
    linhas = [f"motor no início: yt-dlp {atualizador.motor_em_uso()[0]}"]
    codigo = 0
    for formato in ("mp3", "mp4"):
        try:
            arquivo = atualizador.baixar_com_recuperacao(
                atualizador.VIDEO_TESTE, formato, destino, f"autoteste-{formato}",
                ao_trocar_motor=lambda: linhas.append(
                    f"motor revertido para yt-dlp {atualizador.motor_em_uso()[0]}"
                ),
            )
            linhas.append(f"OK {formato} {arquivo.name} {arquivo.stat().st_size}")
        except Exception:
            codigo = 1
            linhas.append(f"FALHA {formato}\n{traceback.format_exc()}")
    (destino / "autoteste.txt").write_text("\n".join(linhas), encoding="utf-8")
    return codigo


def atualizar_motor(arquivo: str) -> int:
    import logging
    import traceback
    from pathlib import Path

    logging.basicConfig(filename=arquivo + ".log", level=logging.INFO, encoding="utf-8")
    try:
        ativada = atualizador.atualizar_motor(forcar=True)
        Path(arquivo).write_text(f"ativada={ativada}", encoding="utf-8")
        return 0
    except Exception:
        Path(arquivo).write_text(traceback.format_exc(), encoding="utf-8")
        return 1


if len(sys.argv) == 3 and sys.argv[1] == "--atualizar-motor":
    sys.exit(atualizar_motor(sys.argv[2]))
if len(sys.argv) == 3 and sys.argv[1] == "--verificar":
    sys.exit(verificar(sys.argv[2]))
if len(sys.argv) == 3 and sys.argv[1] == "--autoteste":
    sys.exit(autoteste(sys.argv[2]))

from baixa.gui import main  # noqa: E402

main()
