"""Junção (merge) de vários PDFs em um único arquivo."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter

from ._common import PathLike, abrir_leitor


def juntar(
    entradas: list[PathLike],
    saida: PathLike,
    *,
    senhas: dict[str, str] | None = None,
) -> Path:
    """Concatena ``entradas`` (na ordem informada) em um único PDF.

    ``senhas`` mapeia, opcionalmente, caminho -> senha para PDFs cifrados.
    Retorna o caminho do arquivo gerado.
    """
    if not entradas:
        raise ValueError("Informe ao menos um PDF para juntar.")
    senhas = senhas or {}
    escritor = PdfWriter()
    for entrada in entradas:
        chave = str(entrada)
        leitor = abrir_leitor(entrada, senhas.get(chave))
        for pagina in leitor.pages:
            escritor.add_page(pagina)

    destino = Path(saida).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("wb") as fh:
        escritor.write(fh)
    return destino
