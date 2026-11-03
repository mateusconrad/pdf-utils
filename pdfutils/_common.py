"""Utilitários compartilhados: validação, abertura de PDFs e parsing de intervalos."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .exceptions import (
    InvalidPdfError,
    PasswordRequiredError,
    WrongPasswordError,
)

PathLike = str | Path


def validar_pdf(caminho: PathLike) -> Path:
    """Valida que ``caminho`` aponta para um arquivo .pdf existente.

    Retorna o :class:`Path` resolvido. Levanta ``FileNotFoundError``,
    ``IsADirectoryError`` ou :class:`InvalidPdfError`.
    """
    p = Path(caminho).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {p}")
    if not p.is_file():
        raise IsADirectoryError(f"O caminho não é um arquivo: {p}")
    if p.suffix.lower() != ".pdf":
        raise InvalidPdfError(f"O arquivo não tem extensão .pdf: {p.name}")
    return p


def abrir_leitor(caminho: PathLike, senha: str | None = None) -> PdfReader:
    """Abre um PDF com pypdf, tratando criptografia e corrupção.

    Levanta :class:`PasswordRequiredError` quando o PDF é cifrado e nenhuma
    senha (ou a senha errada) é informada.
    """
    p = validar_pdf(caminho)
    try:
        leitor = PdfReader(str(p))
    except PdfReadError as exc:
        raise InvalidPdfError(
            f"PDF inválido ou corrompido: {p.name}"
        ) from exc

    if leitor.is_encrypted:
        try:
            resultado = leitor.decrypt(senha or "")
        except Exception as exc:  # pypdf pode levantar em esquemas não suportados
            raise PasswordRequiredError(
                f"Não foi possível abrir o PDF cifrado: {p.name}"
            ) from exc
        # decrypt retorna 0 quando a senha não serve.
        if resultado == 0:
            if senha:
                raise WrongPasswordError("Senha incorreta para o PDF.")
            raise PasswordRequiredError(
                "O PDF está protegido por senha. Informe a senha."
            )
    return leitor


def garantir_pasta(caminho: PathLike) -> Path:
    """Cria (se preciso) e retorna uma pasta de saída."""
    p = Path(caminho).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def parse_intervalo_paginas(spec: str, total: int) -> list[int]:
    """Converte uma especificação de páginas 1-indexada em índices 0-indexados.

    Exemplos (com total=10):
        "1,3,5"   -> [0, 2, 4]
        "2-4"     -> [1, 2, 3]
        "7-"      -> [6, 7, 8, 9]
        "-3"      -> [0, 1, 2]
        "1-3,8,10" -> [0, 1, 2, 7, 9]

    Preserva a ordem informada e remove duplicatas mantendo a 1ª ocorrência.
    """
    if total <= 0:
        return []
    indices: list[int] = []
    vistos: set[int] = set()

    def _add(i0: int) -> None:
        if 0 <= i0 < total and i0 not in vistos:
            vistos.add(i0)
            indices.append(i0)

    for parte in spec.split(","):
        parte = parte.strip()
        if not parte:
            continue
        if "-" in parte:
            ini_s, _, fim_s = parte.partition("-")
            ini = int(ini_s) if ini_s.strip() else 1
            fim = int(fim_s) if fim_s.strip() else total
            if ini > fim:
                ini, fim = fim, ini
            for n in range(ini, fim + 1):
                _add(n - 1)
        else:
            _add(int(parte) - 1)

    return indices


def _iter_indices(selecao: Iterable[int] | None, total: int) -> list[int]:
    """Normaliza uma seleção opcional de índices; ``None`` = todas as páginas."""
    if selecao is None:
        return list(range(total))
    return [i for i in selecao if 0 <= i < total]
