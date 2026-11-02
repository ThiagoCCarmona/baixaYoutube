import importlib.util
from pathlib import Path

import pytest

ESPEC = importlib.util.spec_from_file_location(
    "versao", Path(__file__).resolve().parent.parent / "scripts" / "versao.py"
)
versao = importlib.util.module_from_spec(ESPEC)
ESPEC.loader.exec_module(versao)


@pytest.fixture
def arquivos(tmp_path, monkeypatch):
    init = tmp_path / "__init__.py"
    init.write_text('"""x"""\n\n__version__ = "0.4.9"\n\nREPOSITORIO = "a/b"\n')
    requisitos = tmp_path / "requirements-build.txt"
    requisitos.write_text("# c\nyt-dlp[default,pin]==2026.10.21\npytest==9.2.0\n")
    monkeypatch.setattr(versao, "INIT", init)
    monkeypatch.setattr(versao, "REQUISITOS", requisitos)
    return init, requisitos


def test_patch(arquivos):
    versao.main(["patch"])
    assert versao.versao_atual() == "0.4.10"


def test_definir_valida_formato(arquivos):
    versao.main(["definir", "1.2.3"])
    assert versao.versao_atual() == "1.2.3"
    with pytest.raises(SystemExit):
        versao.main(["definir", "1.2"])


def test_fixar_ytdlp(arquivos, capsys):
    versao.main(["fixar-ytdlp", "2026.11.5"])
    _, requisitos = arquivos
    assert "yt-dlp[default,pin]==2026.11.5\n" in requisitos.read_text()
    assert "pytest==9.2.0" in requisitos.read_text()
