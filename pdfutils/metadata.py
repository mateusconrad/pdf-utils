"""Leitura e edição de metadados; limpeza de dados sensíveis."""

from __future__ import annotations

from pathlib import Path

import pikepdf

from ._common import PathLike, abrir_leitor, validar_pdf


def ler_metadados(caminho: PathLike, *, senha: str | None = None) -> dict:
    """Retorna os metadados do documento (DocInfo) e dados estruturais."""
    leitor = abrir_leitor(caminho, senha)
    meta = leitor.metadata or {}
    info = {k.lstrip("/").lower(): str(v) for k, v in dict(meta).items()}
    info["_paginas"] = len(leitor.pages)
    info["_cifrado"] = leitor.is_encrypted
    return info


def editar_metadados(
    caminho: PathLike,
    saida: PathLike,
    campos: dict[str, str],
    *,
    senha: str | None = None,
) -> Path:
    """Define/atualiza campos do DocInfo (ex.: {"title": "...", "author": "..."})."""
    origem = validar_pdf(caminho)
    destino = Path(saida).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)

    # DocInfo keys reconhecidos (o que ler_metadados devolve).
    mapa = {
        "title": "/Title",
        "author": "/Author",
        "subject": "/Subject",
        "keywords": "/Keywords",
        "creator": "/Creator",
        "producer": "/Producer",
    }
    with pikepdf.open(str(origem), password=senha or "") as pdf:
        with pdf.open_metadata(set_pikepdf_as_editor=False) as md:
            # Mantém o XMP em sincronia com o DocInfo quando possível.
            xmp = {
                "title": "dc:title",
                "author": "dc:creator",
                "subject": "dc:description",
                "keywords": "pdf:Keywords",
                "creator": "xmp:CreatorTool",
                "producer": "pdf:Producer",
            }
            for chave, valor in campos.items():
                prop = xmp.get(chave.lower())
                if not prop:
                    continue
                # dc:creator e dc:* de autoria esperam lista de strings.
                md[prop] = [valor] if prop == "dc:creator" else valor
        docinfo = pdf.docinfo
        for chave, valor in campos.items():
            nome = mapa.get(chave.lower())
            if nome:
                docinfo[pikepdf.Name(nome)] = valor
        pdf.save(str(destino))
    return destino


def limpar_metadados(
    caminho: PathLike,
    saida: PathLike,
    *,
    senha: str | None = None,
    remover_js: bool = True,
) -> Path:
    """Remove metadados (DocInfo + XMP) e, opcionalmente, JavaScript embutido."""
    origem = validar_pdf(caminho)
    destino = Path(saida).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)

    with pikepdf.open(str(origem), password=senha or "") as pdf:
        if pdf.docinfo is not None:
            for chave in list(pdf.docinfo.keys()):
                del pdf.docinfo[chave]
        try:
            with pdf.open_metadata() as md:
                for chave in list(md.keys()):
                    del md[chave]
        except Exception:
            pass
        if remover_js:
            root = pdf.Root
            if "/Names" in root and "/JavaScript" in root.Names:
                del root.Names["/JavaScript"]
            if "/OpenAction" in root:
                del root["/OpenAction"]
        pdf.save(str(destino))
    return destino
