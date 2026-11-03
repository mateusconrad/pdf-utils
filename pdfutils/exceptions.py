"""Exceções da biblioteca pdf-utils."""

from __future__ import annotations


class PdfUtilsError(Exception):
    """Erro base para todas as operações do pdf-utils."""


class InvalidPdfError(PdfUtilsError):
    """O arquivo não é um PDF válido ou está corrompido."""


class PasswordRequiredError(PdfUtilsError):
    """O PDF está protegido e precisa de senha para ser aberto."""


class WrongPasswordError(PdfUtilsError):
    """A senha informada não abre o PDF."""


class MissingDependencyError(PdfUtilsError):
    """Uma dependência opcional (binário externo ou pacote) não está instalada."""

    def __init__(self, dependency: str, feature: str, hint: str = "") -> None:
        self.dependency = dependency
        self.feature = feature
        msg = (
            f"A funcionalidade '{feature}' precisa de '{dependency}', "
            f"que não foi encontrada."
        )
        if hint:
            msg += f" {hint}"
        super().__init__(msg)
