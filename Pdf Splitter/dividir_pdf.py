"""Divide um arquivo PDF em vários PDFs, um por página."""

import argparse
import hashlib
import sys
from pathlib import Path

from pypdf import PageObject, PdfReader, PdfWriter
from pypdf.errors import PdfReadError


def validar_arquivo_pdf(caminho_pdf: Path) -> None:
    """Valida se o caminho aponta para um arquivo PDF existente."""
    if not caminho_pdf.exists():
        raise FileNotFoundError(
            f"Arquivo nao encontrado: {caminho_pdf}"
        )

    if not caminho_pdf.is_file():
        raise ValueError(
            f"O caminho informado nao e um arquivo: {caminho_pdf}"
        )

    if caminho_pdf.suffix.lower() != ".pdf":
        raise ValueError(
            f"O arquivo informado nao possui extensao .pdf: {caminho_pdf.name}"
        )


def criar_pasta_saida(caminho_saida: Path) -> None:
    """Cria a pasta de saida, caso ainda nao exista."""
    try:
        caminho_saida.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        raise PermissionError(
            f"Sem permissao para criar a pasta de saida: {caminho_saida}"
        ) from exc


def fingerprint_pagina(pagina: PageObject) -> str:
    """Gera uma assinatura SHA-256 do conteudo da pagina.

    Combina o texto extraido com os bytes do content stream para detectar
    duplicatas tanto em paginas com texto quanto em paginas baseadas em imagem.
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
        # Se nao for possivel ler o stream, ficamos so com o texto.
        pass

    return h.hexdigest()


def dividir_pdf(
    caminho_pdf: Path,
    caminho_saida: Path,
    ignorar_duplicados: bool = False,
) -> list[Path]:
    """Divide o PDF em uma pagina por arquivo e retorna a lista de arquivos gerados.

    Quando ``ignorar_duplicados`` for True, paginas com mesmo conteudo de uma
    pagina ja gerada sao puladas.
    """
    try:
        leitor = PdfReader(str(caminho_pdf))
    except PdfReadError as exc:
        raise PdfReadError(
            f"O arquivo PDF parece estar invalido ou corrompido: {caminho_pdf.name}"
        ) from exc

    total_paginas = len(leitor.pages)
    if total_paginas == 0:
        raise ValueError("O PDF informado nao possui paginas.")

    print(f"Total de paginas encontradas: {total_paginas}")

    # Padroniza o numero de digitos do nome do arquivo (minimo 3).
    largura = max(3, len(str(total_paginas)))
    arquivos_gerados: list[Path] = []
    hashes_vistos: set[str] = set()
    duplicadas = 0
    indice_saida = 0

    for indice_original, pagina in enumerate(leitor.pages, start=1):
        if ignorar_duplicados:
            assinatura = fingerprint_pagina(pagina)
            if assinatura in hashes_vistos:
                duplicadas += 1
                print(f"Ignorada (duplicada): pagina {indice_original}")
                continue
            hashes_vistos.add(assinatura)

        indice_saida += 1
        escritor = PdfWriter()
        escritor.add_page(pagina)

        nome_arquivo = f"pagina_{indice_saida:0{largura}d}.pdf"
        destino = caminho_saida / nome_arquivo

        try:
            with destino.open("wb") as saida:
                escritor.write(saida)
        except PermissionError as exc:
            raise PermissionError(
                f"Sem permissao para escrever o arquivo: {destino}"
            ) from exc

        arquivos_gerados.append(destino)
        print(f"Gerado: {destino.name}")

    if ignorar_duplicados and duplicadas:
        print(f"Paginas duplicadas ignoradas: {duplicadas}")

    return arquivos_gerados


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Divide um arquivo PDF em varios PDFs, um por pagina.",
    )
    parser.add_argument(
        "arquivo",
        type=Path,
        help="Caminho do arquivo PDF de entrada.",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=None,
        help="Pasta onde os PDFs gerados serao salvos (opcional).",
    )
    parser.add_argument(
        "--sem-duplicados",
        action="store_true",
        help="Ignora paginas com conteudo identico a alguma ja processada.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    caminho_pdf: Path = args.arquivo.expanduser().resolve()

    # Quando nenhuma pasta de saida e informada, usa "<nome_do_pdf>_paginas"
    # ao lado do PDF original.
    if args.saida is None:
        caminho_saida = caminho_pdf.with_name(f"{caminho_pdf.stem}_paginas")
    else:
        caminho_saida = args.saida.expanduser().resolve()

    try:
        validar_arquivo_pdf(caminho_pdf)
        criar_pasta_saida(caminho_saida)
        dividir_pdf(
            caminho_pdf,
            caminho_saida,
            ignorar_duplicados=args.sem_duplicados,
        )
    except (FileNotFoundError, ValueError, PermissionError, PdfReadError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - salvaguarda final
        print(f"Erro inesperado: {exc}", file=sys.stderr)
        return 1

    print(f"Processo concluido. Arquivos salvos em: {caminho_saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
