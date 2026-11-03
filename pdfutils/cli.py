"""CLI unificado do pdf-utils.

Uso: pdfutils <comando> [opções]
Rode `pdfutils --help` ou `pdfutils <comando> --help` para detalhes.
"""

from __future__ import annotations

import argparse
import string
import sys
from pathlib import Path

from . import (
    attachments,
    compress as _compress,
    extract,
    images,
    merge as _merge,
    metadata as _metadata,
    ocr as _ocr,
    pages as _pages,
    security,
    split as _split,
    watermark,
)
from .exceptions import PdfUtilsError

PROG = "pdfutils"


def _fmt_bytes(n: int) -> str:
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return f"{n:.1f} {unidade}" if unidade != "B" else f"{n} B"
        n /= 1024
    return f"{n} B"


# ──────────────────────────────────────────────
# Handlers
# ──────────────────────────────────────────────

def _cmd_split(a: argparse.Namespace) -> int:
    saida = a.saida or Path(a.pdf).with_name(Path(a.pdf).stem + "_paginas")
    if a.blocos:
        ger = _split.dividir_por_blocos(a.pdf, saida, a.blocos, senha=a.senha)
    elif a.intervalos:
        ger = _split.extrair_intervalos(a.pdf, saida, a.intervalos, senha=a.senha)
    else:
        ger = _split.dividir_por_pagina(
            a.pdf, saida, senha=a.senha, ignorar_duplicados=a.sem_duplicados
        )
    print(f"{len(ger)} arquivo(s) gerado(s) em: {saida}")
    return 0


def _cmd_merge(a: argparse.Namespace) -> int:
    destino = _merge.juntar(a.pdfs, a.saida)
    print(f"PDF combinado salvo em: {destino}")
    return 0


def _cmd_rotate(a: argparse.Namespace) -> int:
    d = _pages.rotacionar(a.pdf, a.saida, a.graus, paginas=a.paginas, senha=a.senha)
    print(f"Salvo em: {d}")
    return 0


def _cmd_remove(a: argparse.Namespace) -> int:
    d = _pages.remover(a.pdf, a.saida, a.paginas, senha=a.senha)
    print(f"Salvo em: {d}")
    return 0


def _cmd_reorder(a: argparse.Namespace) -> int:
    d = _pages.reordenar(a.pdf, a.saida, a.ordem, senha=a.senha)
    print(f"Salvo em: {d}")
    return 0


def _cmd_compress(a: argparse.Namespace) -> int:
    r = _compress.comprimir(
        a.pdf, a.saida, nivel=a.nivel, senha=a.senha, forcar_lossless=a.lossless
    )
    print(f"Engine     : {r['engine']}")
    print(f"Antes      : {_fmt_bytes(r['bytes_antes'])}")
    print(f"Depois     : {_fmt_bytes(r['bytes_depois'])}")
    print(f"Redução    : {r['reducao'] * 100:.1f}%")
    print(f"Salvo em   : {r['saida']}")
    return 0


def _cmd_protect(a: argparse.Namespace) -> int:
    d = security.proteger(
        a.pdf, a.saida, a.senha_usuario,
        senha_dono=a.senha_dono, senha_atual=a.senha_atual,
        permitir_impressao=not a.sem_impressao,
        permitir_copia=not a.sem_copia,
        permitir_modificacao=a.permitir_modificacao,
    )
    print(f"PDF protegido salvo em: {d}")
    return 0


def _cmd_unlock(a: argparse.Namespace) -> int:
    d = security.remover_senha(a.pdf, a.saida, a.senha)
    print(f"PDF sem senha salvo em: {d}")
    return 0


def _cmd_recover(a: argparse.Namespace) -> int:
    from .recover_mp import recuperar_paralelo

    if a.mode == "numeric":
        largura = a.width or len(str(a.max))
        total = a.max - a.min
        ger = security.gerar_numerico(a.min, a.max, largura)
    elif a.mode == "alpha":
        charset = a.charset or string.digits
        total = len(charset) ** a.length
        ger = security.gerar_alfabeto(charset, a.length)
    else:  # wordlist
        if not a.wordlist or not Path(a.wordlist).exists():
            print("Erro: informe --wordlist <arquivo> válido.", file=sys.stderr)
            return 1
        with open(a.wordlist, errors="ignore") as fh:
            total = sum(1 for _ in fh)
        ger = security.gerar_wordlist(a.wordlist)

    print(f"Recuperando senha de: {a.pdf}")
    senha = recuperar_paralelo(
        str(Path(a.pdf).expanduser()), ger,
        total=total, n_workers=a.workers, chunk_size=a.chunk,
    )
    if senha is not None:
        print(f"\n  SENHA ENCONTRADA: {senha}")
        if a.saida:
            security.remover_senha(a.pdf, a.saida, senha)
            print(f"  PDF sem senha salvo em: {a.saida}")
        return 0
    print("\n  Senha não encontrada no espaço buscado.")
    return 2


def _cmd_text(a: argparse.Namespace) -> int:
    if a.saida:
        d = extract.extrair_texto_para_arquivo(
            a.pdf, a.saida, paginas=a.paginas, senha=a.senha
        )
        print(f"Texto salvo em: {d}")
    else:
        print(extract.extrair_texto(a.pdf, paginas=a.paginas, senha=a.senha))
    return 0


def _cmd_tables(a: argparse.Namespace) -> int:
    ger = extract.extrair_tabelas(a.pdf, a.saida, paginas=a.paginas, senha=a.senha)
    print(f"{len(ger)} tabela(s) exportada(s) em: {a.saida}")
    return 0


def _cmd_to_images(a: argparse.Namespace) -> int:
    ger = images.pdf_para_imagens(
        a.pdf, a.saida, dpi=a.dpi, formato=a.formato,
        paginas=a.paginas, senha=a.senha,
    )
    print(f"{len(ger)} imagem(ns) gerada(s) em: {a.saida}")
    return 0


def _cmd_from_images(a: argparse.Namespace) -> int:
    d = images.imagens_para_pdf(a.imagens, a.saida)
    print(f"PDF criado em: {d}")
    return 0


def _cmd_ocr(a: argparse.Namespace) -> int:
    d = _ocr.ocr(a.pdf, a.saida, idioma=a.idioma, forcar=a.forcar)
    print(f"PDF pesquisável salvo em: {d}")
    return 0


def _cmd_watermark(a: argparse.Namespace) -> int:
    d = watermark.marca_dagua_texto(
        a.pdf, a.saida, a.texto, opacidade=a.opacidade,
        tamanho=a.tamanho, senha=a.senha,
    )
    print(f"Salvo em: {d}")
    return 0


def _cmd_numerar(a: argparse.Namespace) -> int:
    d = watermark.numerar_paginas(
        a.pdf, a.saida, formato=a.formato, tamanho=a.tamanho, senha=a.senha
    )
    print(f"Salvo em: {d}")
    return 0


def _cmd_meta(a: argparse.Namespace) -> int:
    if a.limpar:
        d = _metadata.limpar_metadados(a.pdf, a.saida, senha=a.senha)
        print(f"Metadados limpos; salvo em: {d}")
    elif a.set:
        campos = {}
        for item in a.set:
            chave, _, valor = item.partition("=")
            campos[chave.strip()] = valor
        d = _metadata.editar_metadados(a.pdf, a.saida, campos, senha=a.senha)
        print(f"Metadados atualizados; salvo em: {d}")
    else:
        info = _metadata.ler_metadados(a.pdf, senha=a.senha)
        for k, v in info.items():
            print(f"  {k:<14}: {v}")
    return 0


def _cmd_images_extract(a: argparse.Namespace) -> int:
    ger = attachments.extrair_imagens(a.pdf, a.saida, senha=a.senha)
    print(f"{len(ger)} imagem(ns) extraída(s) em: {a.saida}")
    return 0


def _cmd_attachments(a: argparse.Namespace) -> int:
    ger = attachments.extrair_anexos(a.pdf, a.saida, senha=a.senha)
    print(f"{len(ger)} anexo(s) extraído(s) em: {a.saida}")
    return 0


def _cmd_flatten(a: argparse.Namespace) -> int:
    d = attachments.achatar(a.pdf, a.saida, senha=a.senha)
    print(f"PDF achatado salvo em: {d}")
    return 0


# ──────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────

def _add_senha(p: argparse.ArgumentParser) -> None:
    p.add_argument("--senha", help="Senha do PDF de entrada, se cifrado.")


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="pdf-utils — utilidades locais e open-source para PDFs.",
    )
    parser.add_argument("--version", action="store_true", help="Mostra a versão.")
    sub = parser.add_subparsers(dest="comando", metavar="<comando>")

    # split
    p = sub.add_parser("split", help="Dividir PDF (por página, blocos ou intervalos).")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o")
    p.add_argument("--blocos", type=int, help="Dividir em blocos de N páginas.")
    p.add_argument("--intervalos", nargs="+", help="Ex.: 1-3 5,7 (um PDF por item).")
    p.add_argument("--sem-duplicados", action="store_true")
    _add_senha(p)
    p.set_defaults(func=_cmd_split)

    # merge
    p = sub.add_parser("merge", help="Juntar vários PDFs em um só.")
    p.add_argument("pdfs", nargs="+")
    p.add_argument("--saida", "-o", required=True)
    p.set_defaults(func=_cmd_merge)

    # rotate
    p = sub.add_parser("rotate", help="Rotacionar páginas (múltiplos de 90°).")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", required=True)
    p.add_argument("--graus", type=int, required=True)
    p.add_argument("--paginas", help="Intervalo (ex.: 1-3,5). Padrão: todas.")
    _add_senha(p)
    p.set_defaults(func=_cmd_rotate)

    # remove
    p = sub.add_parser("remove", help="Remover páginas por intervalo.")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", required=True)
    p.add_argument("--paginas", required=True, help="Ex.: 2,4-6")
    _add_senha(p)
    p.set_defaults(func=_cmd_remove)

    # reorder
    p = sub.add_parser("reorder", help="Reordenar/filtrar páginas.")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", required=True)
    p.add_argument("--ordem", required=True, help="Ex.: 3,1,2")
    _add_senha(p)
    p.set_defaults(func=_cmd_reorder)

    # compress
    p = sub.add_parser("compress", help="Comprimir/otimizar PDF.")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", required=True)
    p.add_argument("--nivel", choices=["leve", "medio", "forte"], default="medio")
    p.add_argument("--lossless", action="store_true", help="Forçar modo pikepdf.")
    _add_senha(p)
    p.set_defaults(func=_cmd_compress)

    # protect
    p = sub.add_parser("protect", help="Proteger PDF com senha (AES-256).")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", required=True)
    p.add_argument("--senha-usuario", required=True)
    p.add_argument("--senha-dono")
    p.add_argument("--senha-atual", help="Senha atual, se o PDF já for cifrado.")
    p.add_argument("--sem-impressao", action="store_true")
    p.add_argument("--sem-copia", action="store_true")
    p.add_argument("--permitir-modificacao", action="store_true")
    p.set_defaults(func=_cmd_protect)

    # unlock
    p = sub.add_parser("unlock", help="Remover senha (você precisa conhecê-la).")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", required=True)
    p.add_argument("--senha", required=True)
    p.set_defaults(func=_cmd_unlock)

    # recover
    p = sub.add_parser(
        "recover",
        help="Recuperar senha de um PDF SEU (força bruta/dicionário).",
    )
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", help="Salvar PDF sem senha ao encontrar.")
    p.add_argument("--mode", choices=["numeric", "wordlist", "alpha"], default="numeric")
    p.add_argument("--min", type=int, default=0)
    p.add_argument("--max", type=int, default=100000)
    p.add_argument("--width", type=int, default=0)
    p.add_argument("--wordlist")
    p.add_argument("--charset", default=string.digits)
    p.add_argument("--length", type=int, default=4)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--chunk", type=int, default=500)
    p.set_defaults(func=_cmd_recover)

    # text
    p = sub.add_parser("text", help="Extrair texto.")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", help="Arquivo .txt (senão imprime na tela).")
    p.add_argument("--paginas")
    _add_senha(p)
    p.set_defaults(func=_cmd_text)

    # tables
    p = sub.add_parser("tables", help="Extrair tabelas para CSV.")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", required=True)
    p.add_argument("--paginas")
    _add_senha(p)
    p.set_defaults(func=_cmd_tables)

    # to-images
    p = sub.add_parser("to-images", help="Renderizar páginas como imagens.")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", required=True)
    p.add_argument("--dpi", type=int, default=150)
    p.add_argument("--formato", choices=["png", "jpg", "jpeg"], default="png")
    p.add_argument("--paginas")
    _add_senha(p)
    p.set_defaults(func=_cmd_to_images)

    # from-images
    p = sub.add_parser("from-images", help="Criar PDF a partir de imagens.")
    p.add_argument("imagens", nargs="+")
    p.add_argument("--saida", "-o", required=True)
    p.set_defaults(func=_cmd_from_images)

    # ocr
    p = sub.add_parser("ocr", help="Tornar PDF pesquisável (OCR).")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", required=True)
    p.add_argument("--idioma", default="por")
    p.add_argument("--forcar", action="store_true")
    p.set_defaults(func=_cmd_ocr)

    # watermark
    p = sub.add_parser("watermark", help="Marca d'água de texto.")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", required=True)
    p.add_argument("--texto", required=True)
    p.add_argument("--opacidade", type=float, default=0.15)
    p.add_argument("--tamanho", type=int, default=48)
    _add_senha(p)
    p.set_defaults(func=_cmd_watermark)

    # numerar
    p = sub.add_parser("numerar", help="Numerar páginas no rodapé.")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", required=True)
    p.add_argument("--formato", default="{n} / {total}")
    p.add_argument("--tamanho", type=int, default=10)
    _add_senha(p)
    p.set_defaults(func=_cmd_numerar)

    # meta
    p = sub.add_parser("meta", help="Ver, editar ou limpar metadados.")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", help="Necessário para --set/--limpar.")
    p.add_argument("--set", nargs="+", metavar="CAMPO=VALOR")
    p.add_argument("--limpar", action="store_true")
    _add_senha(p)
    p.set_defaults(func=_cmd_meta)

    # extract-images
    p = sub.add_parser("extract-images", help="Extrair imagens embutidas.")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", required=True)
    _add_senha(p)
    p.set_defaults(func=_cmd_images_extract)

    # attachments
    p = sub.add_parser("attachments", help="Extrair anexos embutidos.")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", required=True)
    _add_senha(p)
    p.set_defaults(func=_cmd_attachments)

    # flatten
    p = sub.add_parser("flatten", help="Achatar formulários/anotações.")
    p.add_argument("pdf")
    p.add_argument("--saida", "-o", required=True)
    _add_senha(p)
    p.set_defaults(func=_cmd_flatten)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)

    if getattr(args, "version", False):
        from . import __version__

        print(f"{PROG} {__version__}")
        return 0
    if not getattr(args, "comando", None):
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except PdfUtilsError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except (FileNotFoundError, IsADirectoryError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrompido.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    import multiprocessing as mp

    mp.freeze_support()
    sys.exit(main())
