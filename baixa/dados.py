"""Pasta de dados do usuário (%APPDATA%\\baixa) e configuração persistente."""

import json
import os
from pathlib import Path

# BAIXA_DADOS permite isolar os dados em testes.
PASTA_DADOS = Path(
    os.environ.get("BAIXA_DADOS") or Path(os.environ.get("APPDATA", Path.home())) / "baixa"
)
ARQUIVO_CONFIG = PASTA_DADOS / "config.json"
ARQUIVO_LOG = PASTA_DADOS / "baixa.log"


def ler_json(caminho: Path) -> dict:
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def gravar_json(caminho: Path, dados: dict) -> None:
    """Grava de forma atômica (arquivo temporário + rename) para nunca deixar JSON pela metade."""
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = caminho.with_suffix(caminho.suffix + ".tmp")
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporario, caminho)
    except OSError:
        pass


def carregar_config() -> dict:
    return ler_json(ARQUIVO_CONFIG)


def salvar_config(config: dict) -> None:
    gravar_json(ARQUIVO_CONFIG, config)
