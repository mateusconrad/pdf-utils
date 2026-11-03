"""Compressão/otimização de PDFs.

Usa Ghostscript quando disponível (melhor taxa, recomprime imagens). Caso
contrário, aplica uma otimização lossless com pikepdf (recompressão de streams
e coleta de objetos não referenciados).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pikepdf

from ._common import PathLike, validar_pdf

# nível -> preset do Ghostscript
_GS_PRESETS = {
    "leve": "/printer",   # ~300 dpi
    "medio": "/ebook",    # ~150 dpi
    "forte": "/screen",   # ~72 dpi
}


def _achar_ghostscript() -> str | None:
    for nome in ("gswin64c", "gswin32c", "gs"):
        if shutil.which(nome):
            return nome
    return None


def _comprimir_ghostscript(gs: str, origem: Path, destino: Path, nivel: str) -> None:
    preset = _GS_PRESETS.get(nivel, "/ebook")
    cmd = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.6",
        f"-dPDFSETTINGS={preset}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        "-dDetectDuplicateImages=true",
        f"-sOutputFile={destino}",
        str(origem),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _comprimir_pikepdf(origem: Path, destino: Path, senha: str | None) -> None:
    with pikepdf.open(str(origem), password=senha or "") as pdf:
        pdf.save(
            str(destino),
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
            recompress_flate=True,
            linearize=True,
        )


def comprimir(
    caminho: PathLike,
    saida: PathLike,
    *,
    nivel: str = "medio",
    senha: str | None = None,
    forcar_lossless: bool = False,
) -> dict:
    """Comprime um PDF e retorna estatísticas.

    ``nivel`` ∈ {"leve", "medio", "forte"} (só afeta o modo Ghostscript).
    Retorna dict com ``engine``, ``bytes_antes``, ``bytes_depois`` e ``reducao``.
    """
    origem = validar_pdf(caminho)
    destino = Path(saida).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)
    bytes_antes = origem.stat().st_size

    gs = None if forcar_lossless else _achar_ghostscript()
    if gs:
        engine = f"ghostscript ({_GS_PRESETS.get(nivel, '/ebook')})"
        _comprimir_ghostscript(gs, origem, destino, nivel)
    else:
        engine = "pikepdf (lossless)"
        _comprimir_pikepdf(origem, destino, senha)

    bytes_depois = destino.stat().st_size
    reducao = 1 - (bytes_depois / bytes_antes) if bytes_antes else 0.0
    return {
        "engine": engine,
        "bytes_antes": bytes_antes,
        "bytes_depois": bytes_depois,
        "reducao": reducao,
        "saida": destino,
    }
