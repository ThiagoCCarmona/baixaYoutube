# Gera dist/BaixaYoutube/BaixaYoutube.exe (modo onedir, sem console).
# Uso: pyinstaller build/BaixaYoutube.spec --noconfirm --distpath dist --workpath build/tmp

import os

from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

raiz = os.path.abspath(os.path.join(SPECPATH, ".."))
icone = os.path.join(SPECPATH, "baixa.ico")

datas = collect_data_files("imageio_ffmpeg")  # inclui o ffmpeg.exe
datas += collect_data_files("customtkinter")  # temas e fontes da interface
# Metadados usados pelo atualizador para saber a versão embutida do motor.
datas += copy_metadata("yt-dlp") + copy_metadata("yt-dlp-ejs")
binaries = []
hiddenimports = []
for pacote in ("yt_dlp_ejs",):
    d, b, h = collect_all(pacote)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [os.path.join(SPECPATH, "iniciar_gui.py")],
    pathex=[raiz],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest"],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BaixaYoutube",
    console=False,
    icon=icone if os.path.exists(icone) else None,
    version=os.path.join(SPECPATH, "tmp", "versao.txt") if os.path.exists(os.path.join(SPECPATH, "tmp", "versao.txt")) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="BaixaYoutube")
