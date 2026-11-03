"""Extração de imagens e anexos embutidos e achatamento (flatten) de formulários."""

from __future__ import annotations

from pathlib import Path

import pikepdf

from ._common import PathLike, abrir_leitor, validar_pdf
from .exceptions import MissingDependencyError


def extrair_imagens(
    caminho: PathLike,
    pasta_saida: PathLike,
    *,
    senha: str | None = None,
) -> list[Path]:
    """Extrai as imagens embutidas (XObjects) do PDF. Requer PyMuPDF."""
    try:
        import pymupdf as fitz  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise MissingDependencyError(
            "pymupdf", "extrair imagens",
            "Instale com: pip install pymupdf",
        ) from exc

    origem = validar_pdf(caminho)
    saida = Path(pasta_saida).expanduser()
    saida.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(origem))
    try:
        if doc.needs_pass and senha:
            doc.authenticate(senha)
        gerados: list[Path] = []
        vistos: set[int] = set()
        for n in range(doc.page_count):
            for img in doc.load_page(n).get_images(full=True):
                xref = img[0]
                if xref in vistos:
                    continue
                vistos.add(xref)
                base = doc.extract_image(xref)
                ext = base.get("ext", "png")
                destino = saida / f"imagem_{xref:04d}.{ext}"
                destino.write_bytes(base["image"])
                gerados.append(destino)
        return gerados
    finally:
        doc.close()


def extrair_anexos(
    caminho: PathLike,
    pasta_saida: PathLike,
    *,
    senha: str | None = None,
) -> list[Path]:
    """Extrai arquivos embutidos (attachments) do PDF."""
    origem = validar_pdf(caminho)
    saida = Path(pasta_saida).expanduser()
    saida.mkdir(parents=True, exist_ok=True)

    gerados: list[Path] = []
    with pikepdf.open(str(origem), password=senha or "") as pdf:
        try:
            att = pdf.attachments
        except Exception:
            att = {}
        for nome in list(att):
            try:
                dados = att[nome].get_file().read_bytes()
            except Exception:
                continue
            destino = saida / Path(nome).name
            destino.write_bytes(dados)
            gerados.append(destino)
    return gerados


def achatar(
    caminho: PathLike,
    saida: PathLike,
    *,
    senha: str | None = None,
) -> Path:
    """'Achata' (flatten) formulários/anotações, congelando o conteúdo visível.

    Renderiza via PyMuPDF para incorporar os valores como conteúdo estático.
    """
    try:
        import pymupdf as fitz  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise MissingDependencyError(
            "pymupdf", "achatar formulários",
            "Instale com: pip install pymupdf",
        ) from exc

    origem = validar_pdf(caminho)
    destino = Path(saida).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(origem))
    try:
        if doc.needs_pass and senha:
            doc.authenticate(senha)
        # bake() incorpora valores de formulários e anotações como conteúdo
        # estático (flatten). Disponível em PyMuPDF >= 1.24.
        doc.bake()
        doc.save(str(destino), garbage=4, deflate=True)
    finally:
        doc.close()
    return destino
