"""Segurança: proteger com senha, remover senha e recuperação de senha.

A recuperação de senha destina-se a arquivos que você possui e cujo acesso
perdeu (ex.: PDF antigo com senha esquecida). Testa senhas candidatas até
abrir o arquivo.
"""

from __future__ import annotations

import itertools
import string
from pathlib import Path
from typing import Callable, Iterable, Iterator

import pikepdf

from ._common import PathLike, validar_pdf
from .exceptions import WrongPasswordError


# ──────────────────────────────────────────────
# Proteger / remover senha
# ──────────────────────────────────────────────

def proteger(
    caminho: PathLike,
    saida: PathLike,
    senha_usuario: str,
    *,
    senha_dono: str | None = None,
    senha_atual: str | None = None,
    permitir_impressao: bool = True,
    permitir_copia: bool = True,
    permitir_modificacao: bool = False,
) -> Path:
    """Cifra o PDF com AES-256 e as permissões indicadas."""
    origem = validar_pdf(caminho)
    destino = Path(saida).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)

    permissoes = pikepdf.Permissions(
        extract=permitir_copia,
        modify_annotation=permitir_modificacao,
        modify_assembly=permitir_modificacao,
        modify_form=permitir_modificacao,
        modify_other=permitir_modificacao,
        print_lowres=permitir_impressao,
        print_highres=permitir_impressao,
    )
    with pikepdf.open(str(origem), password=senha_atual or "") as pdf:
        pdf.save(
            str(destino),
            encryption=pikepdf.Encryption(
                user=senha_usuario,
                owner=senha_dono or senha_usuario,
                aes=True,
                R=6,  # AES-256
                allow=permissoes,
            ),
        )
    return destino


def remover_senha(
    caminho: PathLike,
    saida: PathLike,
    senha: str,
) -> Path:
    """Remove a criptografia de um PDF cuja senha você conhece."""
    origem = validar_pdf(caminho)
    destino = Path(saida).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        with pikepdf.open(str(origem), password=senha) as pdf:
            pdf.save(str(destino))
    except pikepdf.PasswordError as exc:
        raise WrongPasswordError("Senha incorreta para o PDF.") from exc
    return destino


# ──────────────────────────────────────────────
# Recuperação de senha (arquivos próprios)
# ──────────────────────────────────────────────

def _testar(origem: str, senha: str) -> bool:
    try:
        with pikepdf.open(origem, password=senha):
            return True
    except pikepdf.PasswordError:
        return False
    except Exception:
        return False


def gerar_numerico(inicio: int, fim: int, largura: int) -> Iterator[str]:
    for n in range(inicio, fim):
        yield str(n).zfill(largura)


def gerar_alfabeto(charset: str, comprimento: int) -> Iterator[str]:
    for combo in itertools.product(charset, repeat=comprimento):
        yield "".join(combo)


def gerar_wordlist(caminho: PathLike) -> Iterator[str]:
    with open(caminho, "r", errors="ignore") as fh:
        for linha in fh:
            s = linha.strip()
            if s:
                yield s


def recuperar_senha(
    caminho: PathLike,
    candidatas: Iterable[str],
    *,
    on_progress: Callable[[int, str], None] | None = None,
    limite: int | None = None,
) -> str | None:
    """Tenta cada senha de ``candidatas`` em ordem; retorna a 1ª que abrir.

    ``on_progress(n_testadas, senha_atual)`` é chamado periodicamente.
    Para uso legítimo em PDFs próprios. Execução single-process (o CLI oferece
    o modo multiprocessing para grandes espaços de busca).
    """
    origem = str(validar_pdf(caminho))
    testadas = 0
    for senha in candidatas:
        if limite is not None and testadas >= limite:
            break
        testadas += 1
        if on_progress and testadas % 200 == 0:
            on_progress(testadas, senha)
        if _testar(origem, senha):
            return senha
    return None


def charset_padrao() -> str:
    return string.digits
