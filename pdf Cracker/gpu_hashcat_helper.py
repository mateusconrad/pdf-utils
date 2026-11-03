#!/usr/bin/env python3
"""
GPU PDF Cracker — Hashcat Helper
=================================
Extrai o hash do PDF e monta o comando hashcat otimizado para GPU.

Requisitos:
    pip install pikepdf
    Hashcat instalado: https://hashcat.net/hashcat/
    (Opcional) pdf2john: https://github.com/openwall/john

Uso:
    python gpu_hashcat_helper.py arquivo.pdf --attack numeric --digits 5
    python gpu_hashcat_helper.py arquivo.pdf --attack wordlist rockyou.txt
    python gpu_hashcat_helper.py arquivo.pdf --attack mask "?d?d?d?l?l"
"""

import sys
import os
import subprocess
import argparse
import struct
import re


# ──────────────────────────────────────────────
# Detecta versão do PDF e modo hashcat
# ──────────────────────────────────────────────

def detect_pdf_version(pdf_path: str) -> str:
    with open(pdf_path, 'rb') as f:
        header = f.read(8).decode('latin-1')
    m = re.search(r'%PDF-(\d+\.\d+)', header)
    return m.group(1) if m else '1.4'


def get_hashcat_mode(pdf_version: str) -> tuple[int, str]:
    """
    Retorna (modo_hashcat, descrição).
    PDF < 1.4  → RC4 40-bit  → -m 10400
    PDF 1.4–1.6→ RC4 128-bit → -m 10500
    PDF 1.7+   → AES-256     → -m 10700
    """
    major, minor = map(int, pdf_version.split('.'))
    if major == 1 and minor <= 3:
        return 10400, "RC4 40-bit (PDF ≤ 1.3)"
    elif major == 1 and minor <= 6:
        return 10500, "RC4 128-bit (PDF 1.4–1.6)"
    else:
        return 10700, "AES-256 (PDF 1.7+)"


# ──────────────────────────────────────────────
# Extrai hash via pdf2john (se disponível)
# ──────────────────────────────────────────────

def extract_hash_pdf2john(pdf_path: str) -> str | None:
    """Tenta extrair o hash usando pdf2john.py (do pacote John the Ripper)."""
    for cmd in ['pdf2john', 'pdf2john.py', 'python pdf2john.py']:
        try:
            result = subprocess.run(
                f'{cmd} "{pdf_path}"', shell=True,
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and '$pdf$' in result.stdout:
                # Remove prefixo "filename:" que pdf2john adiciona
                line = result.stdout.strip()
                if ':' in line:
                    line = line.split(':', 1)[1]
                return line
        except Exception:
            continue
    return None


# ──────────────────────────────────────────────
# Monta e exibe comandos hashcat
# ──────────────────────────────────────────────

def build_hashcat_commands(hash_file: str, mode: int, attack: str,
                           digits: int = 5, wordlist: str = None,
                           mask: str = None) -> list[str]:
    cmds = []

    if attack == 'numeric':
        # Máscara numérica com N dígitos
        digit_mask = '?d' * digits
        cmds.append(
            f"hashcat -a 3 -m {mode} {hash_file} {digit_mask} "
            f"--increment --increment-min 1"
        )
        # Com otimizações de GPU
        cmds.append(
            f"hashcat -a 3 -m {mode} {hash_file} {digit_mask} "
            f"-w 4 -O --gpu-loops 1024"
        )

    elif attack == 'wordlist' and wordlist:
        # Ataque por dicionário
        cmds.append(f"hashcat -a 0 -m {mode} {hash_file} {wordlist}")
        # Com regras best64
        cmds.append(
            f"hashcat -a 0 -m {mode} {hash_file} {wordlist} "
            f"-r rules/best64.rule"
        )

    elif attack == 'mask' and mask:
        # Máscara customizada
        cmds.append(f"hashcat -a 3 -m {mode} {hash_file} {mask}")

    elif attack == 'combo':
        # Combinação: wordlist + máscara
        if wordlist:
            cmds.append(
                f"hashcat -a 6 -m {mode} {hash_file} {wordlist} ?d?d?d?d"
            )

    return cmds


def print_banner():
    print("""
╔══════════════════════════════════════════════════╗
║         GPU PDF Cracker — Hashcat Helper          ║
╚══════════════════════════════════════════════════╝
""")


def main():
    parser = argparse.ArgumentParser(
        description='Hashcat helper para GPU — PDF password cracking')

    parser.add_argument('pdf', help='Caminho do PDF protegido')
    parser.add_argument('--attack',
                        choices=['numeric', 'wordlist', 'mask', 'combo'],
                        default='numeric', help='Tipo de ataque')
    parser.add_argument('--digits', type=int, default=5,
                        help='[numeric] Número de dígitos')
    parser.add_argument('--wordlist', type=str,
                        help='[wordlist/combo] Caminho da wordlist')
    parser.add_argument('--mask', type=str,
                        help='[mask] Máscara hashcat ex: ?d?d?d?l?l')
    parser.add_argument('--hash-file', type=str, default='pdf_hash.txt',
                        help='Arquivo para salvar o hash extraído')
    parser.add_argument('--run', action='store_true',
                        help='Executar hashcat automaticamente')
    args = parser.parse_args()

    print_banner()

    if not os.path.exists(args.pdf):
        print(f"[ERRO] Arquivo não encontrado: {args.pdf}")
        sys.exit(1)

    # Detecta versão e modo hashcat
    version = detect_pdf_version(args.pdf)
    mode, desc = get_hashcat_mode(version)
    print(f"  PDF versão : {version}")
    print(f"  Algoritmo  : {desc}")
    print(f"  Modo (-m)  : {mode}\n")

    # Tenta extrair hash
    print("  Extraindo hash do PDF...")
    pdf_hash = extract_hash_pdf2john(args.pdf)

    if pdf_hash:
        with open(args.hash_file, 'w') as f:
            f.write(pdf_hash + '\n')
        print(f"  ✅ Hash salvo em: {args.hash_file}")
        print(f"  Hash: {pdf_hash[:60]}...\n")
    else:
        print("  ⚠️  pdf2john não encontrado.")
        print("  Instale John the Ripper ou baixe pdf2john.py:")
        print("  https://github.com/openwall/john/blob/bleeding-jumbo/run/pdf2john.pl\n")
        print(f"  Execute manualmente: pdf2john {args.pdf} > {args.hash_file}\n")

    # Monta comandos
    hash_target = args.hash_file if pdf_hash else f'<hash_extraido>'
    cmds = build_hashcat_commands(
        hash_target, mode, args.attack,
        digits=args.digits,
        wordlist=args.wordlist,
        mask=args.mask
    )

    print("  ─── Comandos Hashcat ────────────────────────────")
    for i, cmd in enumerate(cmds, 1):
        print(f"\n  [{i}] {cmd}")

    print("\n  ─── Dicas de performance ────────────────────────")
    print("  -w 4        → Workload máximo (mais rápido, GPU 100%)")
    print("  -O          → Otimiza kernels (habilita quando possível)")
    print("  --force     → Ignora avisos (use com cautela)")
    print("  --status    → Mostra progresso a cada 10s")
    print("  --runtime N → Para após N segundos")
    print()

    print("  ─── Benchmark GPU ───────────────────────────────")
    print(f"  hashcat -b -m {mode}\n")

    if args.run and pdf_hash and cmds:
        print("  Executando hashcat...")
        os.system(cmds[0])


if __name__ == '__main__':
    main()
