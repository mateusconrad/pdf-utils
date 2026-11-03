"""Conversão entre PDF e imagens.

- PDF → imagens (PNG/JPEG) usando PyMuPDF (sem binário externo).
- imagens → PDF usando Pillow.
"""

from __future__ import annotations

from pathlib import Path

from ._common import PathLike, parse_intervalo_paginas, validar_pdf
from .exceptions import MissingDependencyError

PathLikeList = list[PathLike]


def pdf_para_imagens(
    caminho: PathLike,
    pasta_saida: PathLike,
    *,
    dpi: int = 150,
    formato: str = "png",
    paginas: str | None = None,
    senha: str | None = None,
) -> list[Path]:
    """Renderiza páginas do PDF como imagens. Requer PyMuPDF (pymupdf)."""
    try:
        import pymupdf as fitz  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise MissingDependencyError(
            "pymupdf", "converter PDF em imagens",
            "Instale com: pip install pymupdf",
        ) from exc

    origem = validar_pdf(caminho)
    saida = Path(pasta_saida).expanduser()
    saida.mkdir(parents=True, exist_ok=True)
    formato = formato.lower().lstrip(".")
    if formato in ("jpg", "jpeg"):
        formato = "jpeg"

    doc = fitz.open(str(origem))
    try:
        if doc.needs_pass:
            if not senha or not doc.authenticate(senha):
                from .exceptions import PasswordRequiredError

                raise PasswordRequiredError(
                    "O PDF está protegido; informe a senha correta."
                )
        total = doc.page_count
        alvo = parse_intervalo_paginas(paginas, total) if paginas else range(total)
        largura = max(3, len(str(total)))
        zoom = dpi / 72.0
        matriz = fitz.Matrix(zoom, zoom)

        gerados: list[Path] = []
        for i in alvo:
            pix = doc.load_page(i).get_pixmap(matrix=matriz)
            ext = "png" if formato == "png" else "jpg"
            destino = saida / f"pagina_{i + 1:0{largura}d}.{ext}"
            pix.save(str(destino))
            gerados.append(destino)
        return gerados
    finally:
        doc.close()


def imagens_para_pdf(
    imagens: PathLikeList,
    saida: PathLike,
) -> Path:
    """Monta um PDF a partir de uma lista de imagens (uma por página)."""
    try:
        from PIL import Image  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise MissingDependencyError(
            "Pillow", "converter imagens em PDF",
            "Instale com: pip install Pillow",
        ) from exc

    if not imagens:
        raise ValueError("Informe ao menos uma imagem.")

    quadros = []
    for caminho in imagens:
        p = Path(caminho).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"Imagem não encontrada: {p}")
        img = Image.open(p)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        quadros.append(img)

    destino = Path(saida).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)
    primeira, resto = quadros[0], quadros[1:]
    primeira.save(str(destino), "PDF", save_all=True, append_images=resto)
    return destino
