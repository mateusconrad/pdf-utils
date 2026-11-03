"""pdf-utils — utilidades locais e open-source para trabalhar com PDFs.

Todas as operações rodam na sua máquina; nada é enviado para a internet.
"""

from __future__ import annotations

from . import (
    attachments,
    compress,
    extract,
    images,
    merge,
    metadata,
    ocr,
    pages,
    security,
    split,
    watermark,
)
from .exceptions import (
    InvalidPdfError,
    MissingDependencyError,
    PasswordRequiredError,
    PdfUtilsError,
    WrongPasswordError,
)

__version__ = "0.1.0"

__all__ = [
    "attachments",
    "compress",
    "extract",
    "images",
    "merge",
    "metadata",
    "ocr",
    "pages",
    "security",
    "split",
    "watermark",
    "PdfUtilsError",
    "InvalidPdfError",
    "PasswordRequiredError",
    "WrongPasswordError",
    "MissingDependencyError",
    "__version__",
]
