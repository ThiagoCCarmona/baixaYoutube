"""Atualizações automáticas do app (GitHub Releases) e do motor yt-dlp (PyPI).

Proteções do motor:
1. Tudo que é baixado tem o SHA-256 conferido.
2. Uma versão nova só é ativada depois de passar por uma validação real (consulta a
   um vídeo conhecido) rodando em outro processo — o app em uso nunca é afetado.
3. Se um download falhar com o motor atualizado e ele não passar mais na validação,
   o app volta sozinho para a versão anterior (ou a embutida), sem reiniciar.

Falhas de rede nunca rejeitam uma versão: se o motor atual também falhar na
validação, o problema é a conexão/YouTube e nada é alterado.
"""

import hashlib
import importlib
import importlib.metadata
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from baixa import REPOSITORIO, __version__
from baixa.dados import PASTA_DADOS, gravar_json, ler_json

log = logging.getLogger("baixa.atualizador")

PASTA_MOTOR = PASTA_DADOS / "motor"
ARQUIVO_ESTADO = PASTA_DADOS / "atualizacoes.json"
INTERVALO_MOTOR = 6 * 3600  # segundos entre consultas ao PyPI
TEMPO_VALIDACAO = 180
VIDEO_TESTE = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
PACOTES_MOTOR = ("yt_dlp", "yt_dlp_ejs")
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ErroAtualizacao(Exception):
    pass


@dataclass
class NovaVersao:
    versao: str
    url: str
    sha256: str
    pagina: str


# ---------- utilitários ----------


def congelado() -> bool:
    return bool(getattr(sys, "frozen", False))


def atualizacoes_habilitadas() -> bool:
    """No desenvolvimento quem atualiza é o pip; BAIXA_FORCAR_ATUALIZADOR=1 liga para testes."""
    return congelado() or os.environ.get("BAIXA_FORCAR_ATUALIZADOR") == "1"


def versao_tupla(texto: Optional[str]) -> tuple:
    partes = []
    for parte in (texto or "").strip().lstrip("vV").split("."):
        numero = re.match(r"\d+", parte)
        if not numero:
            break
        partes.append(int(numero.group()))
    return tuple(partes)


def _requisitar(url: str, timeout: int = 20):
    pedido = urllib.request.Request(url, headers={"User-Agent": f"baixa/{__version__}"})
    return urllib.request.urlopen(pedido, timeout=timeout)


def _get_json(url: str) -> dict:
    with _requisitar(url) as resposta:
        return json.load(resposta)


def _baixar_verificado(
    url: str, destino: Path, sha256: str, ao_progresso: Optional[Callable[[float], None]] = None
) -> None:
    resumo = hashlib.sha256()
    with _requisitar(url, timeout=60) as resposta, open(destino, "wb") as arquivo:
        total = int(resposta.headers.get("Content-Length") or 0)
        feito = 0
        while bloco := resposta.read(256 * 1024):
            arquivo.write(bloco)
            resumo.update(bloco)
            feito += len(bloco)
            if ao_progresso and total:
                ao_progresso(feito / total)
    if resumo.hexdigest().lower() != sha256.lower():
        destino.unlink(missing_ok=True)
        raise ErroAtualizacao(f"SHA-256 não confere para {url}")


def _estado() -> dict:
    return ler_json(ARQUIVO_ESTADO)


def _atualizar_estado(**valores) -> None:
    estado = _estado()
    estado.update(valores)
    gravar_json(ARQUIVO_ESTADO, estado)


# ---------- atualização do app ----------


def verificar_app() -> Optional[NovaVersao]:
    """Consulta o último release no GitHub. Devolve a versão nova ou None."""
    if not atualizacoes_habilitadas():
        return None
    release = _get_json(f"https://api.github.com/repos/{REPOSITORIO}/releases/latest")
    if release.get("draft") or release.get("prerelease"):
        return None
    tag = release.get("tag_name", "")
    if versao_tupla(tag) <= versao_tupla(__version__):
        return None

    versao = tag.lstrip("vV")
    ativos = {ativo["name"]: ativo for ativo in release.get("assets", [])}
    nome = f"BaixaYoutube-Setup-{versao}.exe"
    instalador = ativos.get(nome)
    if not instalador:
        log.warning("Release %s sem o instalador %s", tag, nome)
        return None
    sha256 = _sha256_publicado(ativos, nome) or instalador.get("digest", "").removeprefix("sha256:")
    if not sha256:
        log.warning("Release %s sem SHA-256 para %s", tag, nome)
        return None
    return NovaVersao(versao, instalador["browser_download_url"], sha256, release.get("html_url", ""))


def _sha256_publicado(ativos: dict, nome: str) -> Optional[str]:
    somas = ativos.get("SHA256SUMS.txt")
    if not somas:
        return None
    with _requisitar(somas["browser_download_url"]) as resposta:
        texto = resposta.read().decode("utf-8", "replace")
    for linha in texto.splitlines():
        partes = linha.split()
        if len(partes) == 2 and partes[1].lstrip("*") == nome:
            return partes[0]
    return None


def instalar_app(nova: NovaVersao, ao_progresso: Optional[Callable[[float], None]] = None) -> None:
    """Baixa o instalador, confere o SHA-256 e o inicia em modo silencioso.

    O instalador fecha esta instância e reabre o app atualizado; quem chama deve sair logo depois.
    """
    pasta = Path(tempfile.mkdtemp(prefix="baixa-atualizacao-"))
    instalador = pasta / f"BaixaYoutube-Setup-{nova.versao}.exe"
    _baixar_verificado(nova.url, instalador, nova.sha256, ao_progresso)
    subprocess.Popen(
        [
            str(instalador),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/CURRENTUSER",
            "/CLOSEAPPLICATIONS",
        ],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )


# ---------- motor yt-dlp ----------


def _versao_pacote(nome: str) -> str:
    try:
        return importlib.metadata.version(nome)
    except importlib.metadata.PackageNotFoundError:
        return "0"


# Lidas na importação, antes de qualquer pasta externa entrar no sys.path.
EMBUTIDO_YTDLP = _versao_pacote("yt-dlp")
EMBUTIDO_EJS = _versao_pacote("yt-dlp-ejs")

_motor = {"versao": EMBUTIDO_YTDLP, "pasta": None}


def motor_em_uso() -> tuple:
    """(versão do yt-dlp em uso, True se for uma versão atualizada fora do pacote)."""
    return _motor["versao"], _motor["pasta"] is not None


def _pasta_valida(versao: Optional[str]) -> Optional[Path]:
    if not versao or versao_tupla(versao) <= versao_tupla(EMBUTIDO_YTDLP):
        return None
    pasta = PASTA_MOTOR / versao
    return pasta if (pasta / "yt_dlp" / "__init__.py").is_file() else None


def ativar_motor() -> None:
    """Põe no sys.path o motor atualizado, se houver. Chamar antes de importar yt_dlp."""
    if not atualizacoes_habilitadas():
        return
    versao = _estado().get("motor_ativo")
    pasta = _pasta_valida(versao)
    if pasta:
        sys.path.insert(0, str(pasta))
        _motor.update(versao=versao, pasta=pasta)


def recarregar_motor() -> None:
    """Descarrega o yt-dlp da memória e ativa o motor indicado no estado (troca a quente)."""
    for nome in list(sys.modules):
        if nome.split(".")[0] in PACOTES_MOTOR or nome == "baixa.nucleo":
            del sys.modules[nome]
    if _motor["pasta"] is not None:
        try:
            sys.path.remove(str(_motor["pasta"]))
        except ValueError:
            pass
    _motor.update(versao=EMBUTIDO_YTDLP, pasta=None)
    importlib.invalidate_caches()
    ativar_motor()


def _pin_ejs(requisitos: list) -> Optional[str]:
    """Versão do yt-dlp-ejs exigida pelo extra 'default' do yt-dlp."""
    for requisito in requisitos:
        encontrado = re.match(r"^\s*yt-dlp-ejs\s*==\s*([\w.]+)", requisito)
        if encontrado and "default" in requisito:
            return encontrado.group(1)
    return None


def _instalar_roda(arquivos_pypi: list, destino: Path) -> None:
    roda = next(
        (
            a
            for a in arquivos_pypi
            if a.get("packagetype") == "bdist_wheel" and a["filename"].endswith("-none-any.whl")
        ),
        None,
    )
    if not roda:
        raise ErroAtualizacao("Pacote sem wheel universal no PyPI")
    caminho = destino / roda["filename"]
    _baixar_verificado(roda["url"], caminho, roda["digests"]["sha256"])
    with zipfile.ZipFile(caminho) as zip_roda:
        raiz = destino.resolve()
        for membro in zip_roda.namelist():
            if not (raiz / membro).resolve().is_relative_to(raiz):
                raise ErroAtualizacao(f"Caminho suspeito no wheel: {membro}")
        zip_roda.extractall(destino)
    caminho.unlink()


def validar_em_processo_separado(pasta: Optional[Path]) -> bool:
    """Valida um motor (ou o embutido, com pasta=None) num processo novo."""
    alvo = str(pasta) if pasta else ""
    if congelado():
        comando = [sys.executable, "--validar-motor", alvo]
    else:
        comando = [sys.executable, "-m", "baixa.atualizador", "--validar-motor", alvo]
    ambiente = dict(os.environ, BAIXA_FORCAR_ATUALIZADOR="0")
    try:
        resultado = subprocess.run(
            comando, capture_output=True, text=True, timeout=TEMPO_VALIDACAO,
            creationflags=SEM_JANELA, env=ambiente,
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        log.warning("Validação do motor %s não terminou: %s", alvo or "embutido", erro)
        return False
    if resultado.returncode != 0:
        log.warning(
            "Validação do motor %s falhou (código %s): %s",
            alvo or "embutido", resultado.returncode, (resultado.stdout + resultado.stderr)[-2000:],
        )
    return resultado.returncode == 0


def validar_motor(pasta: Optional[str]) -> int:
    """Roda no processo filho: importa o motor da pasta e faz uma consulta real ao YouTube.

    Nunca deixa exceção escapar: no .exe sem console isso abriria uma caixa de erro
    esperando clique, e a validação só terminaria no tempo limite.
    """
    try:
        return _validar_motor(pasta)
    except BaseException:  # noqa: BLE001
        import traceback

        print(traceback.format_exc())
        return 4


def _validar_motor(pasta: Optional[str]) -> int:
    if pasta:
        sys.path.insert(0, pasta)
    import yt_dlp

    if pasta and not Path(yt_dlp.__file__).resolve().is_relative_to(Path(pasta).resolve()):
        print(f"yt_dlp carregado de {yt_dlp.__file__}, não de {pasta}")
        return 2
    from baixa.nucleo import opcoes_ytdlp

    with tempfile.TemporaryDirectory() as temporaria:
        for formato in ("mp3", "mp4"):
            with yt_dlp.YoutubeDL(opcoes_ytdlp(formato, Path(temporaria))) as ydl:
                info = ydl.extract_info(VIDEO_TESTE, download=False)
            if not (info.get("requested_formats") or info.get("format_id")):
                print(f"Nenhum formato selecionado para {formato}")
                return 3
    return 0


def atualizar_motor(forcar: bool = False) -> Optional[str]:
    """Baixa, valida e registra um yt-dlp mais novo. Devolve a versão ativada ou None.

    A troca na memória é feita por quem chama, com `recarregar_motor()`, quando não houver
    download em andamento.
    """
    if not atualizacoes_habilitadas():
        return None
    estado = _estado()
    if not forcar and time.time() - estado.get("motor_verificado_em", 0) < INTERVALO_MOTOR:
        return None

    info = _get_json("https://pypi.org/pypi/yt-dlp/json")
    _atualizar_estado(motor_verificado_em=time.time())
    nova = info["info"]["version"]
    atual = max(EMBUTIDO_YTDLP, estado.get("motor_ativo") or "0", key=versao_tupla)
    if versao_tupla(nova) <= versao_tupla(atual) or nova in estado.get("motor_rejeitadas", []):
        return None

    log.info("Instalando motor yt-dlp %s", nova)
    temporaria = PASTA_MOTOR / f"{nova}.baixando"
    shutil.rmtree(temporaria, ignore_errors=True)
    temporaria.mkdir(parents=True)
    try:
        _instalar_roda(info["urls"], temporaria)
        pin = _pin_ejs(info["info"].get("requires_dist") or [])
        if pin and pin != EMBUTIDO_EJS:
            _instalar_roda(_get_json(f"https://pypi.org/pypi/yt-dlp-ejs/{pin}/json")["urls"], temporaria)

        if not validar_em_processo_separado(temporaria):
            # Só rejeita se o motor atual funciona; senão é a rede/YouTube, tenta mais tarde.
            if validar_em_processo_separado(_motor["pasta"]):
                _atualizar_estado(motor_rejeitadas=(estado.get("motor_rejeitadas", []) + [nova])[-20:])
                log.warning("Motor yt-dlp %s rejeitado na validação", nova)
            else:
                _atualizar_estado(motor_verificado_em=0)
            return None

        final = PASTA_MOTOR / nova
        shutil.rmtree(final, ignore_errors=True)
        temporaria.rename(final)
        anterior = estado.get("motor_ativo")
        _atualizar_estado(motor_ativo=nova, motor_anterior=anterior)
        _limpar_motores({nova, anterior})
        log.info("Motor yt-dlp %s ativado", nova)
        return nova
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)


def recuperar_motor() -> bool:
    """Chamar quando um download falhar. Se o motor atualizado estiver quebrado, volta ao
    anterior (ou ao embutido) e recarrega. Devolve True se trocou — vale tentar de novo."""
    versao, externo = motor_em_uso()
    if not externo:
        return False
    if validar_em_processo_separado(_motor["pasta"]):
        return False  # motor funciona: o problema é o vídeo ou o link
    estado = _estado()
    anterior = estado.get("motor_anterior")
    reserva = anterior if anterior != versao and _pasta_valida(anterior) else None
    if not validar_em_processo_separado(PASTA_MOTOR / reserva if reserva else None):
        return False  # nada funciona: rede/YouTube fora do ar, não mexe em nada
    _atualizar_estado(
        motor_ativo=reserva,
        motor_anterior=None,
        motor_rejeitadas=(estado.get("motor_rejeitadas", []) + [versao])[-20:],
    )
    log.warning("Motor yt-dlp %s revertido para %s", versao, reserva or f"embutido {EMBUTIDO_YTDLP}")
    recarregar_motor()
    return True


def baixar_com_recuperacao(
    *args,
    ao_verificar: Optional[Callable[[], None]] = None,
    ao_trocar_motor: Optional[Callable[[], None]] = None,
    **kwargs,
):
    """`nucleo.baixar` com volta automática do motor.

    Qualquer falha (inclusive o motor nem conseguir ser importado) com um motor atualizado
    dispara `recuperar_motor()`; se ele trocar de versão, tenta mais uma vez.
    """
    try:
        from baixa.nucleo import baixar

        return baixar(*args, **kwargs)
    except Exception:
        if not motor_em_uso()[1]:
            raise
        if ao_verificar:
            ao_verificar()
        if not recuperar_motor():
            raise
        if ao_trocar_motor:
            ao_trocar_motor()
        from baixa.nucleo import baixar

        return baixar(*args, **kwargs)


def _limpar_motores(manter: set) -> None:
    if not PASTA_MOTOR.is_dir():
        return
    for pasta in PASTA_MOTOR.iterdir():
        if pasta.is_dir() and pasta.name not in manter and pasta != _motor["pasta"]:
            shutil.rmtree(pasta, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--validar-motor":
        sys.exit(validar_motor(sys.argv[2] or None))
    print("Uso: python -m baixa.atualizador --validar-motor PASTA")
    sys.exit(64)
