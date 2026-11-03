"""Extração de conteúdo: texto e tabelas."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from ._common import PathLike, abrir_leitor, parse_intervalo_paginas, validar_pdf
from .exceptions import MissingDependencyError


def extrair_texto(
    caminho: PathLike,
    *,
    paginas: str | None = None,
    senha: str | None = None,
    separador_paginas: str = "\n\n--- Página {n} ---\n\n",
) -> str:
    """Extrai o texto do PDF (opcionalmente só de ``paginas``)."""
    leitor = abrir_leitor(caminho, senha)
    total = len(leitor.pages)
    indices = parse_intervalo_paginas(paginas, total) if paginas else range(total)
    partes: list[str] = []
    for i in indices:
        if separador_paginas:
            partes.append(separador_paginas.format(n=i + 1))
        try:
            partes.append(leitor.pages[i].extract_text() or "")
        except Exception:
            partes.append("")
    return "".join(partes).strip()


def extrair_texto_para_arquivo(
    caminho: PathLike,
    saida: PathLike,
    *,
    paginas: str | None = None,
    senha: str | None = None,
) -> Path:
    texto = extrair_texto(caminho, paginas=paginas, senha=senha)
    destino = Path(saida).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    return destino


def extrair_tabelas(
    caminho: PathLike,
    pasta_saida: PathLike,
    *,
    paginas: str | None = None,
    senha: str | None = None,
) -> list[Path]:
    """Extrai tabelas para arquivos CSV (uma por tabela). Requer pdfplumber."""
    try:
        import pdfplumber  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise MissingDependencyError(
            "pdfplumber", "extrair tabelas",
            "Instale com: pip install pdfplumber",
        ) from exc

    origem = validar_pdf(caminho)
    saida = Path(pasta_saida).expanduser()
    saida.mkdir(parents=True, exist_ok=True)

    gerados: list[Path] = []
    abrir_kwargs = {"password": senha} if senha else {}
    with pdfplumber.open(str(origem), **abrir_kwargs) as pdf:
        total = len(pdf.pages)
        alvo = (
            parse_intervalo_paginas(paginas, total) if paginas else range(total)
        )
        for i in alvo:
            tabelas = pdf.pages[i].extract_tables() or []
            for t, tabela in enumerate(tabelas, start=1):
                destino = saida / f"pagina_{i + 1:03d}_tabela_{t}.csv"
                with destino.open("w", newline="", encoding="utf-8") as fh:
                    escritor = csv.writer(fh)
                    for linha in tabela:
                        escritor.writerow(
                            ["" if c is None else c for c in linha]
                        )
                gerados.append(destino)
    return gerados
