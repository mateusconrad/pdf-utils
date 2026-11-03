"""OCR: adiciona uma camada de texto pesquisável a PDFs escaneados.

Usa o ocrmypdf (que por sua vez requer o Tesseract e o Ghostscript). Ambos
são opcionais; a função reporta claramente se algo estiver faltando.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ._common import PathLike, validar_pdf
from .exceptions import MissingDependencyError, PdfUtilsError


def ocr(
    caminho: PathLike,
    saida: PathLike,
    *,
    idioma: str = "por",
    forcar: bool = False,
    otimizar: int = 1,
) -> Path:
    """Gera um PDF pesquisável.

    ``idioma`` segue os códigos do Tesseract (ex.: "por", "eng", "por+eng").
    ``forcar`` reaplica OCR mesmo em páginas que já têm texto.
    """
    try:
        import ocrmypdf  # noqa: PLC0415
    except ImportError as exc:
        raise MissingDependencyError(
            "ocrmypdf", "OCR",
            "Instale com: pip install ocrmypdf (e o Tesseract no sistema).",
        ) from exc

    if not shutil.which("tesseract"):
        raise MissingDependencyError(
            "tesseract", "OCR",
            "Instale o Tesseract OCR e garanta que esteja no PATH.",
        )

    origem = validar_pdf(caminho)
    destino = Path(saida).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)

    try:
        ocrmypdf.ocr(
            str(origem),
            str(destino),
            language=idioma,
            force_ocr=forcar,
            skip_text=not forcar,
            optimize=otimizar,
            progress_bar=False,
        )
    except Exception as exc:  # engloba erros do ocrmypdf
        raise PdfUtilsError(f"Falha no OCR: {exc}") from exc
    return destino
