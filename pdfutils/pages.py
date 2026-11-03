"""Operações estruturais de páginas: rotacionar, remover e reordenar."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter

from ._common import PathLike, abrir_leitor, parse_intervalo_paginas


def _salvar(escritor: PdfWriter, saida: PathLike) -> Path:
    destino = Path(saida).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("wb") as fh:
        escritor.write(fh)
    return destino


def rotacionar(
    caminho: PathLike,
    saida: PathLike,
    graus: int,
    *,
    paginas: str | None = None,
    senha: str | None = None,
) -> Path:
    """Rotaciona páginas em múltiplos de 90°.

    ``paginas`` é um intervalo (ex.: "1-3,5"); ``None`` rotaciona todas.
    """
    if graus % 90 != 0:
        raise ValueError("A rotação deve ser múltiplo de 90 graus.")
    leitor = abrir_leitor(caminho, senha)
    total = len(leitor.pages)
    alvo = set(
        parse_intervalo_paginas(paginas, total) if paginas else range(total)
    )
    escritor = PdfWriter()
    for i, pagina in enumerate(leitor.pages):
        if i in alvo:
            pagina.rotate(graus)
        escritor.add_page(pagina)
    return _salvar(escritor, saida)


def remover(
    caminho: PathLike,
    saida: PathLike,
    paginas: str,
    *,
    senha: str | None = None,
) -> Path:
    """Remove as páginas indicadas pelo intervalo ``paginas`` (ex.: "2,4-6")."""
    leitor = abrir_leitor(caminho, senha)
    total = len(leitor.pages)
    remover_idx = set(parse_intervalo_paginas(paginas, total))
    if len(remover_idx) >= total:
        raise ValueError("A operação removeria todas as páginas do PDF.")
    escritor = PdfWriter()
    for i, pagina in enumerate(leitor.pages):
        if i not in remover_idx:
            escritor.add_page(pagina)
    return _salvar(escritor, saida)


def reordenar(
    caminho: PathLike,
    saida: PathLike,
    ordem: str,
    *,
    senha: str | None = None,
) -> Path:
    """Reordena/filtra páginas segundo ``ordem`` (ex.: "3,1,2" ou "5-1").

    A ordem é respeitada exatamente; páginas fora da lista são descartadas.
    """
    leitor = abrir_leitor(caminho, senha)
    total = len(leitor.pages)
    indices = parse_intervalo_paginas(ordem, total)
    if not indices:
        raise ValueError("A nova ordem não selecionou nenhuma página válida.")
    paginas = list(leitor.pages)
    escritor = PdfWriter()
    for i in indices:
        escritor.add_page(paginas[i])
    return _salvar(escritor, saida)
