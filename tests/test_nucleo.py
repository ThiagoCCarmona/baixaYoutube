from pathlib import Path

import pytest

from baixa.nucleo import baixar, opcoes_ytdlp


def test_mp3_converte_para_192kbps(tmp_path):
    opcoes = opcoes_ytdlp("mp3", tmp_path)
    assert opcoes["format"] == "bestaudio/best"
    (pos,) = opcoes["postprocessors"]
    assert pos["key"] == "FFmpegExtractAudio"
    assert (pos["preferredcodec"], pos["preferredquality"]) == ("mp3", "192")


def test_mp4_compativel_prefere_h264_aac(tmp_path):
    opcoes = opcoes_ytdlp("mp4", tmp_path)
    assert opcoes["format"].startswith("bv*[ext=mp4][vcodec^=avc]+ba[ext=m4a]")
    assert opcoes["merge_output_format"] == "mp4"


def test_mp4_maxima_aceita_qualquer_codec(tmp_path):
    opcoes = opcoes_ytdlp("mp4", tmp_path, qualidade="maxima")
    assert opcoes["format"] == "bv*+ba/b"
    assert opcoes["merge_output_format"] == "mp4"


def test_qualidade_maxima_nao_afeta_mp3(tmp_path):
    assert opcoes_ytdlp("mp3", tmp_path, qualidade="maxima")["format"] == "bestaudio/best"


def test_sem_nome_usa_titulo(tmp_path):
    assert Path(opcoes_ytdlp("mp3", tmp_path)["outtmpl"]).name == "%(title)s.%(ext)s"
    assert Path(opcoes_ytdlp("mp3", tmp_path, "   ")["outtmpl"]).name == "%(title)s.%(ext)s"


def test_nome_personalizado_e_sanitizado(tmp_path):
    modelo = Path(opcoes_ytdlp("mp3", tmp_path, ' minha/musica:"boa" ')["outtmpl"])
    assert modelo.parent == tmp_path
    assert modelo.name.endswith(".%(ext)s")
    assert not any(c in modelo.name for c in '/\\:"')


@pytest.mark.parametrize("formato, qualidade", [("wav", "compativel"), ("mp3", "ultra")])
def test_parametros_invalidos(tmp_path, formato, qualidade):
    with pytest.raises(ValueError):
        baixar("https://youtu.be/x", formato, tmp_path, qualidade=qualidade)
