"""Interface web para dividir PDFs em paginas individuais."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from werkzeug.utils import secure_filename

from dividir_pdf import fingerprint_pagina

# 50 MB de limite para upload, ajustavel conforme necessario.
TAMANHO_MAXIMO_MB = 50

app = Flask(__name__)
app.secret_key = "troque-esta-chave-em-producao"
app.config["MAX_CONTENT_LENGTH"] = TAMANHO_MAXIMO_MB * 1024 * 1024


def _dividir_em_zip(
    arquivo_bytes: bytes,
    ignorar_duplicados: bool,
) -> tuple[bytes, int, int]:
    """Divide o PDF em memoria e devolve um ZIP em bytes.

    Retorna uma tupla (zip_bytes, paginas_geradas, paginas_duplicadas).
    """
    try:
        leitor = PdfReader(io.BytesIO(arquivo_bytes))
    except PdfReadError as exc:
        raise ValueError(
            "O arquivo enviado parece estar invalido ou corrompido."
        ) from exc

    total_paginas = len(leitor.pages)
    if total_paginas == 0:
        raise ValueError("O PDF enviado nao possui paginas.")

    largura = max(3, len(str(total_paginas)))
    buffer_zip = io.BytesIO()
    hashes_vistos: set[str] = set()
    geradas = 0
    duplicadas = 0

    with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for pagina in leitor.pages:
            if ignorar_duplicados:
                assinatura = fingerprint_pagina(pagina)
                if assinatura in hashes_vistos:
                    duplicadas += 1
                    continue
                hashes_vistos.add(assinatura)

            geradas += 1
            escritor = PdfWriter()
            escritor.add_page(pagina)

            buffer_pdf = io.BytesIO()
            escritor.write(buffer_pdf)
            zf.writestr(
                f"pagina_{geradas:0{largura}d}.pdf",
                buffer_pdf.getvalue(),
            )

    buffer_zip.seek(0)
    return buffer_zip.getvalue(), geradas, duplicadas


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", tamanho_maximo_mb=TAMANHO_MAXIMO_MB)


@app.route("/dividir", methods=["POST"])
def dividir():
    arquivo = request.files.get("arquivo")
    ignorar_duplicados = request.form.get("ignorar_duplicados") == "on"

    if arquivo is None or arquivo.filename == "":
        flash("Selecione um arquivo PDF para enviar.", "erro")
        return redirect(url_for("index"))

    nome_seguro = secure_filename(arquivo.filename)
    if not nome_seguro.lower().endswith(".pdf"):
        flash("O arquivo precisa ter extensao .pdf.", "erro")
        return redirect(url_for("index"))

    try:
        conteudo = arquivo.read()
        zip_bytes, geradas, duplicadas = _dividir_em_zip(
            conteudo,
            ignorar_duplicados=ignorar_duplicados,
        )
    except ValueError as exc:
        flash(str(exc), "erro")
        return redirect(url_for("index"))
    except Exception:
        flash("Falha inesperada ao processar o PDF.", "erro")
        return redirect(url_for("index"))

    nome_base = Path(nome_seguro).stem or "documento"
    nome_zip = f"{nome_base}_paginas.zip"

    resposta = send_file(
        io.BytesIO(zip_bytes),
        mimetype="application/zip",
        as_attachment=True,
        download_name=nome_zip,
    )
    resposta.headers["X-Paginas-Geradas"] = str(geradas)
    resposta.headers["X-Paginas-Duplicadas"] = str(duplicadas)
    return resposta


@app.errorhandler(413)
def arquivo_grande_demais(_):
    flash(
        f"Arquivo maior que o limite de {TAMANHO_MAXIMO_MB} MB.",
        "erro",
    )
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
