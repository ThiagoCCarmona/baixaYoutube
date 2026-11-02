import hashlib
import io
import json
import sys
import zipfile

import pytest

from baixa import __version__, atualizador
from baixa.atualizador import versao_tupla


class RespostaFalsa(io.BytesIO):
    def __init__(self, conteudo: bytes):
        super().__init__(conteudo)
        self.headers = {"Content-Length": str(len(conteudo))}


def estado():
    return json.loads(atualizador.ARQUIVO_ESTADO.read_text(encoding="utf-8"))


def criar_motor(pasta, versao):
    pacote = pasta / versao / "yt_dlp"
    pacote.mkdir(parents=True)
    (pacote / "__init__.py").write_text(f"__version__ = '{versao}'\n")
    return pasta / versao


VERSAO_FUTURA = "9999.1.1"


# ---------- versões ----------


@pytest.mark.parametrize(
    "maior, menor",
    [("0.10.0", "0.9.9"), ("v1.0.0", "0.99.0"), ("2026.10.21.1", "2026.10.21"), ("2026.11.1", "2026.10.31")],
)
def test_comparacao_de_versoes(maior, menor):
    assert versao_tupla(maior) > versao_tupla(menor)


def test_versao_vazia():
    assert versao_tupla("") == () and versao_tupla(None) == ()


# ---------- app ----------


def release(tag, ativos=None, **extra):
    v = tag.lstrip("v")
    nome = f"BaixaYoutube-Setup-{v}.exe"
    if ativos is None:
        ativos = [
            {"name": nome, "browser_download_url": f"https://x/{nome}"},
            {"name": "SHA256SUMS.txt", "browser_download_url": "https://x/SHA256SUMS.txt"},
        ]
    return {"tag_name": tag, "assets": ativos, "html_url": "https://x/release", **extra}


def test_detecta_versao_nova_com_sha256(dados, monkeypatch):
    monkeypatch.setattr(atualizador, "_get_json", lambda url: release("v99.0.0"))
    somas = b"ab12 *BaixaYoutube-Setup-99.0.0.exe\ncd34  outro.exe\n"
    monkeypatch.setattr(atualizador, "_requisitar", lambda url, timeout=20: RespostaFalsa(somas))
    nova = atualizador.verificar_app()
    assert nova.versao == "99.0.0"
    assert nova.sha256 == "ab12"
    assert nova.url.endswith("BaixaYoutube-Setup-99.0.0.exe")


def test_usa_digest_do_github_sem_sha256sums(dados, monkeypatch):
    ativo = {"name": "BaixaYoutube-Setup-99.0.0.exe", "browser_download_url": "u", "digest": "sha256:ff00"}
    monkeypatch.setattr(atualizador, "_get_json", lambda url: release("v99.0.0", [ativo]))
    assert atualizador.verificar_app().sha256 == "ff00"


@pytest.mark.parametrize(
    "dados_release",
    [
        release(f"v{__version__}"),
        release("v0.0.1"),
        release("v99.0.0", prerelease=True),
        release("v99.0.0", ativos=[]),
        release("v99.0.0", ativos=[{"name": "BaixaYoutube-Setup-99.0.0.exe", "browser_download_url": "u"}]),
    ],
    ids=["mesma", "antiga", "prerelease", "sem-instalador", "sem-sha256"],
)
def test_ignora_releases_que_nao_servem(dados, monkeypatch, dados_release):
    monkeypatch.setattr(atualizador, "_get_json", lambda url: dados_release)
    assert atualizador.verificar_app() is None


def test_desligado_fora_do_executavel(monkeypatch):
    monkeypatch.setattr(atualizador, "atualizacoes_habilitadas", lambda: False)
    monkeypatch.setattr(atualizador, "_get_json", lambda url: pytest.fail("não deveria consultar"))
    assert atualizador.verificar_app() is None
    assert atualizador.atualizar_motor(forcar=True) is None


# ---------- download verificado ----------


def test_download_confere_sha256(tmp_path, monkeypatch):
    conteudo = b"instalador"
    monkeypatch.setattr(atualizador, "_requisitar", lambda url, timeout=20: RespostaFalsa(conteudo))
    destino = tmp_path / "setup.exe"
    progresso = []
    atualizador._baixar_verificado("u", destino, hashlib.sha256(conteudo).hexdigest(), progresso.append)
    assert destino.read_bytes() == conteudo
    assert progresso[-1] == 1


def test_download_com_sha256_errado_e_apagado(tmp_path, monkeypatch):
    monkeypatch.setattr(atualizador, "_requisitar", lambda url, timeout=20: RespostaFalsa(b"adulterado"))
    destino = tmp_path / "setup.exe"
    with pytest.raises(atualizador.ErroAtualizacao):
        atualizador._baixar_verificado("u", destino, "00" * 32)
    assert not destino.exists()


# ---------- wheels ----------


def wheel(arquivos: dict) -> bytes:
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w") as zip_roda:
        for nome, texto in arquivos.items():
            zip_roda.writestr(nome, texto)
    return memoria.getvalue()


def instalar_wheel_falso(monkeypatch, conteudo: bytes, destino):
    def baixar(url, caminho, sha256, ao_progresso=None):
        caminho.write_bytes(conteudo)

    monkeypatch.setattr(atualizador, "_baixar_verificado", baixar)
    arquivos = [
        {"packagetype": "sdist", "filename": "yt_dlp-1.tar.gz", "url": "u", "digests": {"sha256": "x"}},
        {"packagetype": "bdist_wheel", "filename": "yt_dlp-1-py3-none-any.whl", "url": "u", "digests": {"sha256": "x"}},
    ]
    atualizador._instalar_roda(arquivos, destino)


def test_extrai_wheel(tmp_path, monkeypatch):
    instalar_wheel_falso(monkeypatch, wheel({"yt_dlp/__init__.py": "x = 1"}), tmp_path)
    assert (tmp_path / "yt_dlp" / "__init__.py").read_text() == "x = 1"
    assert not list(tmp_path.glob("*.whl"))


def test_recusa_wheel_com_caminho_malicioso(tmp_path, monkeypatch):
    destino = tmp_path / "destino"
    destino.mkdir()
    with pytest.raises(atualizador.ErroAtualizacao):
        instalar_wheel_falso(monkeypatch, wheel({"../fora.py": "x"}), destino)
    assert not (tmp_path / "fora.py").exists()


def test_le_pin_do_yt_dlp_ejs():
    requisitos = [
        "brotli; extra == 'default'",
        "yt-dlp-ejs==0.9.1; extra == 'default'",
        "yt-dlp-ejs==0.9.1; extra == 'pin'",
    ]
    assert atualizador._pin_ejs(requisitos) == "0.9.1"
    assert atualizador._pin_ejs(["mutagen; extra == 'default'"]) is None


# ---------- motor ----------


def test_ativa_motor_mais_novo(dados):
    pasta = criar_motor(atualizador.PASTA_MOTOR, VERSAO_FUTURA)
    atualizador._atualizar_estado(motor_ativo=VERSAO_FUTURA)
    atualizador.ativar_motor()
    assert sys.path[0] == str(pasta)
    assert atualizador.motor_em_uso() == (VERSAO_FUTURA, True)


def test_ignora_motor_mais_velho_que_o_embutido(dados):
    criar_motor(atualizador.PASTA_MOTOR, "2000.1.1")
    atualizador._atualizar_estado(motor_ativo="2000.1.1")
    atualizador.ativar_motor()
    assert atualizador.motor_em_uso() == (atualizador.EMBUTIDO_YTDLP, False)


def preparar_pypi(monkeypatch, versao=VERSAO_FUTURA, requisitos=()):
    info = {"info": {"version": versao, "requires_dist": list(requisitos)}, "urls": []}
    monkeypatch.setattr(atualizador, "_get_json", lambda url: info)

    def instalar(arquivos, destino):
        (destino / "yt_dlp").mkdir(exist_ok=True)
        (destino / "yt_dlp" / "__init__.py").write_text("")

    monkeypatch.setattr(atualizador, "_instalar_roda", instalar)


def test_motor_validado_e_ativado(dados, monkeypatch):
    preparar_pypi(monkeypatch)
    monkeypatch.setattr(atualizador, "validar_em_processo_separado", lambda pasta: True)
    assert atualizador.atualizar_motor() == VERSAO_FUTURA
    assert estado()["motor_ativo"] == VERSAO_FUTURA
    assert (atualizador.PASTA_MOTOR / VERSAO_FUTURA / "yt_dlp").is_dir()
    assert not (atualizador.PASTA_MOTOR / f"{VERSAO_FUTURA}.baixando").exists()


def test_respeita_intervalo_entre_verificacoes(dados, monkeypatch):
    preparar_pypi(monkeypatch)
    monkeypatch.setattr(atualizador, "validar_em_processo_separado", lambda pasta: True)
    assert atualizador.atualizar_motor() == VERSAO_FUTURA
    monkeypatch.setattr(atualizador, "_get_json", lambda url: pytest.fail("não deveria consultar"))
    assert atualizador.atualizar_motor() is None


def test_motor_que_falha_na_validacao_e_rejeitado(dados, monkeypatch):
    preparar_pypi(monkeypatch)
    # nova versão falha; motor atual (pasta None) funciona -> a culpa é da versão nova
    monkeypatch.setattr(atualizador, "validar_em_processo_separado", lambda pasta: pasta is None)
    assert atualizador.atualizar_motor() is None
    assert estado().get("motor_ativo") is None
    assert VERSAO_FUTURA in estado()["motor_rejeitadas"]
    assert not any(atualizador.PASTA_MOTOR.iterdir())
    # versão rejeitada não é tentada de novo
    assert atualizador.atualizar_motor(forcar=True) is None


def test_falha_de_rede_nao_rejeita_versao(dados, monkeypatch):
    preparar_pypi(monkeypatch)
    monkeypatch.setattr(atualizador, "validar_em_processo_separado", lambda pasta: False)
    assert atualizador.atualizar_motor() is None
    assert VERSAO_FUTURA not in estado().get("motor_rejeitadas", [])
    assert estado()["motor_verificado_em"] == 0  # tenta de novo no próximo início


def test_baixa_yt_dlp_ejs_quando_o_pin_muda(dados, monkeypatch):
    preparar_pypi(monkeypatch, requisitos=["yt-dlp-ejs==99.0.0; extra == 'default'"])
    consultas = []
    original = atualizador._get_json
    monkeypatch.setattr(atualizador, "_get_json", lambda url: consultas.append(url) or original(url))
    monkeypatch.setattr(atualizador, "validar_em_processo_separado", lambda pasta: True)
    atualizador.atualizar_motor()
    assert "https://pypi.org/pypi/yt-dlp-ejs/99.0.0/json" in consultas


def test_volta_ao_embutido_quando_motor_quebra(dados, monkeypatch):
    pasta = criar_motor(atualizador.PASTA_MOTOR, VERSAO_FUTURA)
    atualizador._atualizar_estado(motor_ativo=VERSAO_FUTURA)
    atualizador.ativar_motor()
    recargas = []
    monkeypatch.setattr(atualizador, "recarregar_motor", lambda: recargas.append(1))
    monkeypatch.setattr(atualizador, "validar_em_processo_separado", lambda p: p != pasta)

    assert atualizador.recuperar_motor() is True
    assert estado()["motor_ativo"] is None
    assert VERSAO_FUTURA in estado()["motor_rejeitadas"]
    assert recargas == [1]


def test_volta_para_o_anterior_quando_existe(dados, monkeypatch):
    anterior = "9999.1.0"
    criar_motor(atualizador.PASTA_MOTOR, anterior)
    pasta = criar_motor(atualizador.PASTA_MOTOR, VERSAO_FUTURA)
    atualizador._atualizar_estado(motor_ativo=VERSAO_FUTURA, motor_anterior=anterior)
    atualizador.ativar_motor()
    monkeypatch.setattr(atualizador, "recarregar_motor", lambda: None)
    monkeypatch.setattr(atualizador, "validar_em_processo_separado", lambda p: p != pasta)

    assert atualizador.recuperar_motor() is True
    assert estado()["motor_ativo"] == anterior


def test_nao_reverte_se_motor_ainda_funciona(dados, monkeypatch):
    criar_motor(atualizador.PASTA_MOTOR, VERSAO_FUTURA)
    atualizador._atualizar_estado(motor_ativo=VERSAO_FUTURA)
    atualizador.ativar_motor()
    monkeypatch.setattr(atualizador, "validar_em_processo_separado", lambda p: True)
    assert atualizador.recuperar_motor() is False
    assert estado()["motor_ativo"] == VERSAO_FUTURA


def test_nao_reverte_se_nada_funciona(dados, monkeypatch):
    criar_motor(atualizador.PASTA_MOTOR, VERSAO_FUTURA)
    atualizador._atualizar_estado(motor_ativo=VERSAO_FUTURA)
    atualizador.ativar_motor()
    monkeypatch.setattr(atualizador, "validar_em_processo_separado", lambda p: False)
    assert atualizador.recuperar_motor() is False
    assert estado()["motor_ativo"] == VERSAO_FUTURA


def test_sem_motor_externo_nao_ha_o_que_recuperar(dados):
    assert atualizador.recuperar_motor() is False


def test_baixar_com_recuperacao_tenta_de_novo_apos_trocar(dados, monkeypatch):
    import baixa.nucleo as nucleo

    tentativas = []

    def baixar_falso(*args, **kwargs):
        tentativas.append(args)
        if len(tentativas) == 1:
            raise RuntimeError("motor quebrado")
        return "ok"

    monkeypatch.setattr(nucleo, "baixar", baixar_falso)
    monkeypatch.setitem(atualizador._motor, "pasta", "x")  # simula motor externo
    monkeypatch.setattr(atualizador, "recuperar_motor", lambda: True)
    avisos = []
    resultado = atualizador.baixar_com_recuperacao(
        "link", "mp3", ao_verificar=lambda: avisos.append("verificando"),
        ao_trocar_motor=lambda: avisos.append("trocado"),
    )
    assert resultado == "ok" and len(tentativas) == 2
    assert avisos == ["verificando", "trocado"]


def test_baixar_com_recuperacao_repassa_erro_com_motor_embutido(dados, monkeypatch):
    import baixa.nucleo as nucleo

    def baixar_falso(*args, **kwargs):
        raise nucleo.ErroDownload("vídeo indisponível")

    monkeypatch.setattr(nucleo, "baixar", baixar_falso)
    monkeypatch.setattr(atualizador, "recuperar_motor", lambda: pytest.fail("não deveria validar"))
    with pytest.raises(nucleo.ErroDownload):
        atualizador.baixar_com_recuperacao("link", "mp3")


# ---------- rede (pytest -m rede) ----------


@pytest.mark.rede
def test_validacao_real_do_motor_embutido():
    assert atualizador.validar_em_processo_separado(None) is True
