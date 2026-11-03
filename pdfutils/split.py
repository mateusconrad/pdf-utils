"""Divisão de PDFs: por página, por intervalos ou em blocos de N páginas."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from pypdf import PageObject, PdfReader, PdfWriter

from ._common import PathLike, abrir_leitor, garantir_pasta, parse_intervalo_paginas


def fingerprint_pagina(pagina: PageObject) -> str:
    """Assinatura SHA-256 do conteúdo de uma página (texto + content stream).

    Detecta duplicatas tanto em páginas com texto quanto baseadas em imagem.
    """
    h = hashlib.sha256()
    try:
        texto = pagina.extract_text() or ""
    except Exception:
        texto = ""
    h.update(texto.encode("utf-8"))
    try:
        conteudo = pagina.get_contents()
        if conteudo is not None:
            h.update(conteudo.get_data())
    except Exception:
        pass
    return h.hexdigest()


def _escrever_paginas(paginas: list[PageObject]) -> bytes:
    escritor = PdfWriter()
    for pg in paginas:
        escritor.add_page(pg)
    buf = io.BytesIO()
    escritor.write(buf)
    return buf.getvalue()


def dividir_por_pagina(
    caminho: PathLike,
    pasta_saida: PathLike,
    *,
    senha: str | None = None,
    ignorar_duplicados: bool = False,
) -> list[Path]:
    """Gera um PDF por página. Retorna a lista de arquivos criados."""
    leitor = abrir_leitor(caminho, senha)
    total = len(leitor.pages)
    if total == 0:
        return []
    saida = garantir_pasta(pasta_saida)
    largura = max(3, len(str(total)))

    gerados: list[Path] = []
    vistos: set[str] = set()
    indice = 0
    for pagina in leitor.pages:
        if ignorar_duplicados:
            assinatura = fingerprint_pagina(pagina)
            if assinatura in vistos:
                continue
            vistos.add(assinatura)
        indice += 1
        destino = saida / f"pagina_{indice:0{largura}d}.pdf"
        destino.write_bytes(_escrever_paginas([pagina]))
        gerados.append(destino)
    return gerados


def dividir_por_blocos(
    caminho: PathLike,
    pasta_saida: PathLike,
    tamanho: int,
    *,
    senha: str | None = None,
) -> list[Path]:
    """Divide o PDF em blocos de ``tamanho`` páginas cada."""
    if tamanho < 1:
        raise ValueError("O tamanho do bloco deve ser >= 1.")
    leitor = abrir_leitor(caminho, senha)
    paginas = list(leitor.pages)
    total = len(paginas)
    if total == 0:
        return []
    saida = garantir_pasta(pasta_saida)
    largura = max(2, len(str((total + tamanho - 1) // tamanho)))

    gerados: list[Path] = []
    for n, inicio in enumerate(range(0, total, tamanho), start=1):
        bloco = paginas[inicio : inicio + tamanho]
        destino = saida / f"bloco_{n:0{largura}d}.pdf"
        destino.write_bytes(_escrever_paginas(bloco))
        gerados.append(destino)
    return gerados


def extrair_intervalos(
    caminho: PathLike,
    pasta_saida: PathLike,
    intervalos: list[str],
    *,
    senha: str | None = None,
) -> list[Path]:
    """Extrai um PDF para cada especificação de intervalo (ex.: ['1-3', '5,7'])."""
    leitor = abrir_leitor(caminho, senha)
    paginas = list(leitor.pages)
    total = len(paginas)
    if total == 0:
        return []
    saida = garantir_pasta(pasta_saida)

    gerados: list[Path] = []
    for n, spec in enumerate(intervalos, start=1):
        indices = parse_intervalo_paginas(spec, total)
        if not indices:
            continue
        selecionadas = [paginas[i] for i in indices]
        rotulo = spec.replace(",", "_").replace("-", "a")
        destino = saida / f"intervalo_{n:02d}_{rotulo}.pdf"
        destino.write_bytes(_escrever_paginas(selecionadas))
        gerados.append(destino)
    return gerados
