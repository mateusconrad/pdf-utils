"""
PDF Password Cracker — CPU Multiprocessing (Windows/Linux/Mac)
==============================================================
Requisitos:
    pip install pikepdf tqdm

Uso:
    python pdf_cracker.py arquivo.pdf --mode numeric --min 0 --max 99999
    python pdf_cracker.py arquivo.pdf --mode wordlist --wordlist rockyou.txt
    python pdf_cracker.py arquivo.pdf --mode alpha --length 4
    python pdf_cracker.py arquivo.pdf --mode alpha --charset "0123456789abcdef" --length 5
"""

import pikepdf
import multiprocessing as mp
import itertools
import string
import argparse
import time
import sys
import os
from datetime import timedelta
from tqdm import tqdm


# ──────────────────────────────────────────────
# Globais de sinalização (inicializadas no worker)
# ──────────────────────────────────────────────

_stop_event = None
_counter    = None
_lock       = None


def init_worker(stop_event, counter, lock):
    """Inicializa globais em cada processo filho."""
    global _stop_event, _counter, _lock
    _stop_event = stop_event
    _counter    = counter
    _lock       = lock


# ──────────────────────────────────────────────
# Worker: testa um lote de senhas
# ──────────────────────────────────────────────

def worker(args):
    """Recebe (pdf_path, [senhas]) e retorna a senha correta ou None."""
    pdf_path, passwords = args

    for pwd in passwords:
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


# ──────────────────────────────────────────────
# Geradores de senhas
# ──────────────────────────────────────────────

def gen_numeric(start, end, width):
    for n in range(start, end):
        yield str(n).zfill(width)


def gen_alpha(charset, length):
    for combo in itertools.product(charset, repeat=length):
        yield ''.join(combo)


def gen_wordlist(path):
    with open(path, 'r', errors='ignore') as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                yield stripped


# ──────────────────────────────────────────────
# Divide iterável em lotes
# ──────────────────────────────────────────────

def chunked(iterable, size, stop_event):
    chunk = []
    for item in iterable:
        if stop_event.is_set():
            break
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk and not stop_event.is_set():
        yield chunk


# ──────────────────────────────────────────────
# Salva PDF decriptado
# ──────────────────────────────────────────────

def save_decrypted(pdf_path, password):
    out_path = f"decrypted_{os.path.basename(pdf_path)}"
    try:
        with pikepdf.open(pdf_path, password=password) as pdf:
            pdf.save(out_path)
        print(f"  Salvo em        : {out_path}")
    except Exception as e:
        print(f"  [AVISO] Nao foi possivel salvar: {e}")


# ──────────────────────────────────────────────
# Funcao principal de ataque
# ──────────────────────────────────────────────

def crack_pdf(pdf_path, generator, total=None, n_workers=None, chunk_size=500):

    if not os.path.exists(pdf_path):
        print(f"\n[ERRO] Arquivo nao encontrado: {pdf_path}")
        sys.exit(1)

    n_workers = n_workers or mp.cpu_count()

    # ✅ Objetos compartilhados criados AQUI (dentro de __main__)
    stop_event = mp.Event()
    counter    = mp.Value('i', 0)
    lock       = mp.Lock()

    print(f"\n{'='*55}")
    print(f"  Arquivo   : {pdf_path}")
    print(f"  Workers   : {n_workers}  (CPUs: {mp.cpu_count()})")
    print(f"  Chunk     : {chunk_size} senhas/lote")
    if total:
        print(f"  Total est.: {total:,} combinacoes")
    print(f"{'='*55}\n")

    start  = time.time()
    result = None

    with mp.Pool(
        processes=n_workers,
        initializer=init_worker,
        initargs=(stop_event, counter, lock)
    ) as pool:

        tasks = (
            (pdf_path, chunk)
            for chunk in chunked(generator, chunk_size, stop_event)
        )

        with tqdm(total=total, desc="Testando", unit=" pwd",
                  dynamic_ncols=True, colour='cyan') as pbar:

            last = 0
            for res in pool.imap_unordered(worker, tasks, chunksize=1):
                current = counter.value
                pbar.update(current - last)
                last = current

                if res is not None:
                    result = res
                    stop_event.set()
                    pool.terminate()
                    break

                if stop_event.is_set():
                    pool.terminate()
                    break

    elapsed = time.time() - start
    tested  = counter.value
    speed   = tested / elapsed if elapsed > 0 else 0

    print(f"\n{'='*55}")
    if result:
        print(f"  SENHA ENCONTRADA : {result}")
        save_decrypted(pdf_path, result)
    else:
        print("  Senha nao encontrada no espaco buscado.")

    print(f"  Testadas   : {tested:,}")
    print(f"  Tempo      : {timedelta(seconds=int(elapsed))}")
    print(f"  Velocidade : {speed:,.0f} senhas/s")
    print(f"{'='*55}\n")
    return result


# ──────────────────────────────────────────────
# ✅ TUDO dentro de if __name__ == '__main__'
#    Obrigatorio no Windows (spawn, nao fork)
# ──────────────────────────────────────────────

if __name__ == '__main__':
    mp.freeze_support()

    parser = argparse.ArgumentParser(
        description='PDF Password Cracker — multiprocessing')

    parser.add_argument('pdf',
        help='Caminho do PDF protegido')
    parser.add_argument('--mode',
        choices=['numeric', 'wordlist', 'alpha'],
        default='numeric',
        help='Modo de ataque (padrao: numeric)')
    parser.add_argument('--min', type=int, default=0,
        help='[numeric] Valor minimo (padrao: 0)')
    parser.add_argument('--max', type=int, default=99999,
        help='[numeric] Valor maximo exclusive (padrao: 99999)')
    parser.add_argument('--width', type=int, default=0,
        help='[numeric] Zero-padding; 0 = tamanho do max (padrao: 0)')
    parser.add_argument('--wordlist', type=str,
        help='[wordlist] Caminho do arquivo de senhas')
    parser.add_argument('--charset', type=str,
        default=string.digits,
        help='[alpha] Caracteres a combinar (padrao: digitos)')
    parser.add_argument('--length', type=int, default=4,
        help='[alpha] Comprimento fixo das combinacoes (padrao: 4)')
    parser.add_argument('--workers', type=int, default=None,
        help='Processos paralelos (padrao: todos os CPUs)')
    parser.add_argument('--chunk', type=int, default=500,
        help='Senhas por lote enviado a cada worker (padrao: 500)')

    args = parser.parse_args()

    if args.mode == 'numeric':
        width = args.width or len(str(args.max))
        total = args.max - args.min
        gen   = gen_numeric(args.min, args.max, width)
        crack_pdf(args.pdf, gen, total=total,
                  n_workers=args.workers, chunk_size=args.chunk)

    elif args.mode == 'wordlist':
        if not args.wordlist or not os.path.exists(args.wordlist):
            print("[ERRO] Informe --wordlist <arquivo> valido.")
            sys.exit(1)
        with open(args.wordlist, errors='ignore') as f:
            total = sum(1 for _ in f)
        gen = gen_wordlist(args.wordlist)
        crack_pdf(args.pdf, gen, total=total,
                  n_workers=args.workers, chunk_size=args.chunk)

    elif args.mode == 'alpha':
        total = len(args.charset) ** args.length
        gen   = gen_alpha(args.charset, args.length)
        crack_pdf(args.pdf, gen, total=total,
                  n_workers=args.workers, chunk_size=args.chunk)
