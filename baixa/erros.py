"""Exceções do baixa, num módulo que nunca é recarregado na troca do motor."""


class ErroDownload(Exception):
    """Falha ao baixar ou converter o vídeo."""
