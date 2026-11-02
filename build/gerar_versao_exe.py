"""Gera build/tmp/versao.txt (recurso de versão do .exe, visto em Propriedades > Detalhes)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from baixa import __version__  # noqa: E402

numeros = (tuple(int(p) for p in __version__.split(".")) + (0, 0, 0, 0))[:4]
modelo = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numeros}, prodvers={numeros}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041604B0', [
      StringStruct('CompanyName', 'baixa'),
      StringStruct('FileDescription', 'BaixaYoutube - YouTube para MP3/MP4'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', 'BaixaYoutube'),
      StringStruct('OriginalFilename', 'BaixaYoutube.exe'),
      StringStruct('ProductName', 'BaixaYoutube'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [0x0416, 1200])])
  ]
)
"""
destino = Path(__file__).resolve().parent / "tmp" / "versao.txt"
destino.parent.mkdir(parents=True, exist_ok=True)
destino.write_text(modelo, encoding="utf-8")
print(destino)
