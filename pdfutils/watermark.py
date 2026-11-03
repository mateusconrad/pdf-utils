"""Marca d'água, carimbo e numeração de páginas via overlay (reportlab)."""

from __future__ import annotations

import io
import math
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from ._common import PathLike, abrir_leitor
from .exceptions import MissingDependencyError


def _reportlab():
    try:
        from reportlab.lib.colors import Color  # noqa: PLC0415
        from reportlab.pdfgen import canvas  # noqa: PLC0415

        return canvas, Color
    except ImportError as exc:  # pragma: no cover
        raise MissingDependencyError(
            "reportlab", "marca d'água / numeração",
            "Instale com: pip install reportlab",
        ) from exc


def _salvar(escritor: PdfWriter, saida: PathLike) -> Path:
    destino = Path(saida).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("wb") as fh:
        escritor.write(fh)
    return destino


def _overlay_texto_diagonal(
    largura: float, altura: float, texto: str, opacidade: float, tamanho: int
) -> PdfReader:
    canvas, Color = _reportlab()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(largura, altura))
    c.setFont("Helvetica-Bold", tamanho)
    c.setFillColor(Color(0.5, 0.5, 0.5, alpha=opacidade))
    c.saveState()
    c.translate(largura / 2, altura / 2)
    c.rotate(math.degrees(math.atan2(altura, largura)))
    c.drawCentredString(0, 0, texto)
    c.restoreState()
    c.save()
    buf.seek(0)
    return PdfReader(buf)


def marca_dagua_texto(
    caminho: PathLike,
    saida: PathLike,
    texto: str,
    *,
    opacidade: float = 0.15,
    tamanho: int = 48,
    senha: str | None = None,
) -> Path:
    """Aplica uma marca d'água de texto na diagonal em todas as páginas."""
    leitor = abrir_leitor(caminho, senha)
    escritor = PdfWriter()
    for pagina in leitor.pages:
        cx = float(pagina.mediabox.width)
        cy = float(pagina.mediabox.height)
        overlay = _overlay_texto_diagonal(cx, cy, texto, opacidade, tamanho)
        pagina.merge_page(overlay.pages[0])
        escritor.add_page(pagina)
    return _salvar(escritor, saida)


def numerar_paginas(
    caminho: PathLike,
    saida: PathLike,
    *,
    formato: str = "{n} / {total}",
    tamanho: int = 10,
    margem: float = 28.0,
    senha: str | None = None,
) -> Path:
    """Adiciona numeração no rodapé centralizado de cada página."""
    canvas, _ = _reportlab()
    leitor = abrir_leitor(caminho, senha)
    total = len(leitor.pages)
    escritor = PdfWriter()
    for i, pagina in enumerate(leitor.pages, start=1):
        largura = float(pagina.mediabox.width)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(largura, float(pagina.mediabox.height)))
        c.setFont("Helvetica", tamanho)
        c.drawCentredString(
            largura / 2, margem, formato.format(n=i, total=total)
        )
        c.save()
        buf.seek(0)
        pagina.merge_page(PdfReader(buf).pages[0])
        escritor.add_page(pagina)
    return _salvar(escritor, saida)
