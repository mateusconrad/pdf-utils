"""Recuperação de senha paralela (multiprocessing) para PDFs próprios.

Portado do projeto original 'pdf Cracker'. Usar apenas em arquivos que você
possui e cujo acesso legítimo perdeu.
"""

from __future__ import annotations

import multiprocessing as mp
import time
from datetime import timedelta
from typing import Iterable, Iterator

import pikepdf

_stop_event = None
_counter = None
_lock = None


def _init_worker(stop_event, counter, lock):
    global _stop_event, _counter, _lock
    _stop_event, _counter, _lock = stop_event, counter, lock


def _worker(args):
    pdf_path, senhas = args
    for pwd in senhas:
        if _stop_event.is_set():
            return None
        try:
            with pikepdf.open(pdf_path, password=pwd):
                _stop_event.set()
                return pwd
        except pikepdf.PasswordError:
            pass
        except Exception:
            pass
        with _lock:
            _counter.value += 1
    return None


def _chunked(iteravel: Iterable[str], tamanho: int, stop_event) -> Iterator[list[str]]:
    lote: list[str] = []
    for item in iteravel:
        if stop_event.is_set():
            break
        lote.append(item)
        if len(lote) == tamanho:
            yield lote
            lote = []
    if lote and not stop_event.is_set():
        yield lote


def recuperar_paralelo(
    pdf_path: str,
    gerador: Iterable[str],
    *,
    total: int | None = None,
    n_workers: int | None = None,
    chunk_size: int = 500,
    quiet: bool = False,
) -> str | None:
    """Testa senhas em paralelo; retorna a 1ª que abrir o PDF, ou None."""
    n_workers = n_workers or mp.cpu_count()
    stop_event = mp.Event()
    counter = mp.Value("i", 0)
    lock = mp.Lock()

    try:
        from tqdm import tqdm  # noqa: PLC0415
    except ImportError:
        tqdm = None

    inicio = time.time()
    resultado = None

    with mp.Pool(
        processes=n_workers,
        initializer=_init_worker,
        initargs=(stop_event, counter, lock),
    ) as pool:
        tarefas = (
            (pdf_path, lote) for lote in _chunked(gerador, chunk_size, stop_event)
        )
        barra = (
            tqdm(total=total, desc="Testando", unit=" pwd", dynamic_ncols=True)
            if (tqdm and not quiet)
            else None
        )
        ultimo = 0
        for res in pool.imap_unordered(_worker, tarefas, chunksize=1):
            atual = counter.value
            if barra:
                barra.update(atual - ultimo)
            ultimo = atual
            if res is not None:
                resultado = res
                stop_event.set()
                pool.terminate()
                break
            if stop_event.is_set():
                pool.terminate()
                break
        if barra:
            barra.close()

    if not quiet:
        decorrido = time.time() - inicio
        testadas = counter.value
        vel = testadas / decorrido if decorrido else 0
        print(f"  Testadas   : {testadas:,}")
        print(f"  Tempo      : {timedelta(seconds=int(decorrido))}")
        print(f"  Velocidade : {vel:,.0f} senhas/s")
    return resultado
