"""Testes de fumaça do core. Gera um PDF sintético com reportlab."""

from __future__ import annotations

import io

import pytest
from pypdf import PdfReader

import pdfutils as pu
from pdfutils._common import parse_intervalo_paginas


@pytest.fixture()
def pdf_tres_paginas(tmp_path):
    reportlab = pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    caminho = tmp_path / "amostra.pdf"
    c = canvas.Canvas(str(caminho))
    for i in range(1, 4):
        c.drawString(72, 720, f"Pagina {i} - conteudo de teste")
        c.showPage()
    c.save()
    return caminho


def _n_paginas(caminho) -> int:
    return len(PdfReader(str(caminho)).pages)


def test_parse_intervalo():
    assert parse_intervalo_paginas("1,3,5", 10) == [0, 2, 4]
    assert parse_intervalo_paginas("2-4", 10) == [1, 2, 3]
    assert parse_intervalo_paginas("7-", 10) == [6, 7, 8, 9]
    assert parse_intervalo_paginas("-3", 10) == [0, 1, 2]
    assert parse_intervalo_paginas("3,1,2", 3) == [2, 0, 1]  # preserva ordem


def test_split_por_pagina(pdf_tres_paginas, tmp_path):
    ger = pu.split.dividir_por_pagina(pdf_tres_paginas, tmp_path / "out")
    assert len(ger) == 3
    assert all(p.exists() for p in ger)


def test_split_blocos(pdf_tres_paginas, tmp_path):
    ger = pu.split.dividir_por_blocos(pdf_tres_paginas, tmp_path / "out", 2)
    assert len(ger) == 2
    assert _n_paginas(ger[0]) == 2
    assert _n_paginas(ger[1]) == 1


def test_merge(pdf_tres_paginas, tmp_path):
    destino = pu.merge.juntar(
        [pdf_tres_paginas, pdf_tres_paginas], tmp_path / "m.pdf"
    )
    assert _n_paginas(destino) == 6


def test_rotate_remove_reorder(pdf_tres_paginas, tmp_path):
    pu.pages.rotacionar(pdf_tres_paginas, tmp_path / "r.pdf", 90)
    rem = pu.pages.remover(pdf_tres_paginas, tmp_path / "rm.pdf", "2")
    assert _n_paginas(rem) == 2
    reo = pu.pages.reordenar(pdf_tres_paginas, tmp_path / "ro.pdf", "3,1")
    assert _n_paginas(reo) == 2


def test_protect_unlock_recover(pdf_tres_paginas, tmp_path):
    prot = pu.security.proteger(pdf_tres_paginas, tmp_path / "p.pdf", "abc123")
    with pytest.raises(pu.WrongPasswordError):
        pu.security.remover_senha(prot, tmp_path / "x.pdf", "errada")
    unlocked = pu.security.remover_senha(prot, tmp_path / "u.pdf", "abc123")
    assert _n_paginas(unlocked) == 3
    achou = pu.security.recuperar_senha(prot, ["000", "abc123", "zzz"])
    assert achou == "abc123"


def test_metadata(pdf_tres_paginas, tmp_path):
    out = pu.metadata.editar_metadados(
        pdf_tres_paginas, tmp_path / "meta.pdf",
        {"title": "Titulo", "author": "Autor"},
    )
    info = pu.metadata.ler_metadados(out)
    assert info["title"] == "Titulo"
    assert info["author"] == "Autor"
    limpo = pu.metadata.limpar_metadados(out, tmp_path / "limpo.pdf")
    info2 = pu.metadata.ler_metadados(limpo)
    assert "title" not in info2


def test_extrair_texto(pdf_tres_paginas):
    texto = pu.extract.extrair_texto(pdf_tres_paginas)
    assert "Pagina 1" in texto


def test_watermark_numerar(pdf_tres_paginas, tmp_path):
    wm = pu.watermark.marca_dagua_texto(
        pdf_tres_paginas, tmp_path / "wm.pdf", "RASCUNHO"
    )
    assert _n_paginas(wm) == 3
    num = pu.watermark.numerar_paginas(pdf_tres_paginas, tmp_path / "n.pdf")
    assert _n_paginas(num) == 3


def test_compress(pdf_tres_paginas, tmp_path):
    r = pu.compress.comprimir(
        pdf_tres_paginas, tmp_path / "c.pdf", forcar_lossless=True
    )
    assert r["bytes_depois"] > 0
    assert (tmp_path / "c.pdf").exists()
