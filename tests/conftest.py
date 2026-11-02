import os
import sys
import tempfile
from pathlib import Path

# Isola os dados do usuário antes de qualquer import do pacote.
os.environ["BAIXA_DADOS"] = tempfile.mkdtemp(prefix="baixa-testes-")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from baixa import atualizador  # noqa: E402


@pytest.fixture
def dados(tmp_path, monkeypatch):
    """Estado do atualizador numa pasta temporária, com atualizações habilitadas."""
    monkeypatch.setattr(atualizador, "PASTA_MOTOR", tmp_path / "motor")
    monkeypatch.setattr(atualizador, "ARQUIVO_ESTADO", tmp_path / "atualizacoes.json")
    monkeypatch.setattr(atualizador, "atualizacoes_habilitadas", lambda: True)
    motor_original = dict(atualizador._motor)
    caminhos_originais = list(sys.path)
    yield tmp_path
    atualizador._motor.clear()
    atualizador._motor.update(motor_original)
    sys.path[:] = caminhos_originais
