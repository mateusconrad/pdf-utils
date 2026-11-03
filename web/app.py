"""Backend web do pdf-utils (Flask).

Cada ferramenta é um endpoint em /api/<ferramenta>. O processamento acontece
em um diretório temporário por requisição; nada é mantido no servidor depois
da resposta. Projetado para uso LOCAL (127.0.0.1).
"""

from __future__ import annotations

import io
import sys
import tempfile
import zipfile
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

# Permite rodar como `python web/app.py` sem instalar o pacote.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pdfutils as pu  # noqa: E402
from pdfutils.exceptions import (  # noqa: E402
    MissingDependencyError,
    PasswordRequiredError,
    PdfUtilsError,
    WrongPasswordError,
)

TAMANHO_MAXIMO_MB = 200

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = TAMANHO_MAXIMO_MB * 1024 * 1024


# ──────────────────────────────────────────────
# Infra
# ──────────────────────────────────────────────

class ErroCliente(Exception):
    """Erro de validação de entrada (HTTP 400)."""


def _salvar_upload(campo: str, tmp: Path) -> Path:
    arquivo = request.files.get(campo)
    if arquivo is None or arquivo.filename == "":
        raise ErroCliente(f"Envie um arquivo no campo '{campo}'.")
    nome = secure_filename(arquivo.filename) or "entrada.pdf"
    destino = tmp / nome
    arquivo.save(destino)
    return destino


def _salvar_uploads(campo: str, tmp: Path) -> list[Path]:
    arquivos = request.files.getlist(campo)
    arquivos = [a for a in arquivos if a and a.filename]
    if not arquivos:
        raise ErroCliente(f"Envie ao menos um arquivo no campo '{campo}'.")
    caminhos = []
    for i, a in enumerate(arquivos):
        nome = secure_filename(a.filename) or f"arquivo_{i}"
        destino = tmp / f"{i:03d}_{nome}"
        a.save(destino)
        caminhos.append(destino)
    return caminhos


def _enviar_pdf(caminho: Path, nome_download: str):
    dados = caminho.read_bytes()
    return send_file(
        io.BytesIO(dados),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nome_download,
    )


def _enviar_zip(pasta: Path, nome_download: str):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(pasta.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(pasta))
    buf.seek(0)
    return send_file(
        buf, mimetype="application/zip",
        as_attachment=True, download_name=nome_download,
    )


def _campo(nome: str, padrao: str | None = None) -> str | None:
    v = request.form.get(nome)
    return v if v not in (None, "") else padrao


def _stem(p: Path) -> str:
    return p.stem or "documento"


# ──────────────────────────────────────────────
# Catálogo (para a UI montar os cards dinamicamente)
# ──────────────────────────────────────────────

CATALOGO = [
    {"id": "split", "nome": "Dividir", "grupo": "Organizar",
     "desc": "Separe em páginas, blocos de N páginas ou intervalos."},
    {"id": "merge", "nome": "Juntar", "grupo": "Organizar",
     "desc": "Combine vários PDFs em um único arquivo.", "multi": True},
    {"id": "rotate", "nome": "Rotacionar", "grupo": "Organizar",
     "desc": "Gire páginas em 90/180/270°."},
    {"id": "remove", "nome": "Remover páginas", "grupo": "Organizar",
     "desc": "Apague páginas por intervalo."},
    {"id": "reorder", "nome": "Reordenar", "grupo": "Organizar",
     "desc": "Reorganize a ordem das páginas."},
    {"id": "compress", "nome": "Comprimir", "grupo": "Otimizar",
     "desc": "Reduza o tamanho do arquivo."},
    {"id": "ocr", "nome": "OCR", "grupo": "Otimizar",
     "desc": "Torne um PDF escaneado pesquisável."},
    {"id": "protect", "nome": "Proteger", "grupo": "Segurança",
     "desc": "Adicione senha e criptografia AES-256."},
    {"id": "unlock", "nome": "Remover senha", "grupo": "Segurança",
     "desc": "Remova a senha (você precisa conhecê-la)."},
    {"id": "meta", "nome": "Metadados", "grupo": "Segurança",
     "desc": "Veja, edite ou limpe metadados e JavaScript."},
    {"id": "text", "nome": "Extrair texto", "grupo": "Extrair",
     "desc": "Exporte o texto do PDF."},
    {"id": "tables", "nome": "Extrair tabelas", "grupo": "Extrair",
     "desc": "Exporte tabelas para CSV."},
    {"id": "to-images", "nome": "PDF → imagens", "grupo": "Converter",
     "desc": "Renderize páginas como PNG/JPG."},
    {"id": "from-images", "nome": "Imagens → PDF", "grupo": "Converter",
     "desc": "Monte um PDF a partir de imagens.", "multi": True},
    {"id": "extract-images", "nome": "Extrair imagens", "grupo": "Extrair",
     "desc": "Extraia as imagens embutidas."},
    {"id": "watermark", "nome": "Marca d'água", "grupo": "Editar",
     "desc": "Aplique uma marca d'água de texto."},
    {"id": "numerar", "nome": "Numerar páginas", "grupo": "Editar",
     "desc": "Adicione numeração no rodapé."},
    {"id": "flatten", "nome": "Achatar", "grupo": "Editar",
     "desc": "Congele formulários e anotações."},
]


@app.get("/api/catalogo")
def catalogo():
    return jsonify(CATALOGO)


# ──────────────────────────────────────────────
# Endpoints de ferramentas
# ──────────────────────────────────────────────

@app.post("/api/split")
def api_split():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        senha = _campo("senha")
        saida = tmp / "out"
        modo = _campo("modo", "paginas")
        if modo == "blocos":
            pu.split.dividir_por_blocos(pdf, saida, int(_campo("tamanho", "2")), senha=senha)
        elif modo == "intervalos":
            specs = [s for s in (_campo("intervalos", "") or "").split() if s]
            pu.split.extrair_intervalos(pdf, saida, specs, senha=senha)
        else:
            pu.split.dividir_por_pagina(
                pdf, saida, senha=senha,
                ignorar_duplicados=_campo("sem_duplicados") == "on",
            )
        return _enviar_zip(saida, f"{_stem(pdf)}_dividido.zip")


@app.post("/api/merge")
def api_merge():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdfs = _salvar_uploads("arquivos", tmp)
        destino = tmp / "merged.pdf"
        pu.merge.juntar(pdfs, destino)
        return _enviar_pdf(destino, "combinado.pdf")


@app.post("/api/rotate")
def api_rotate():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        destino = tmp / "out.pdf"
        pu.pages.rotacionar(
            pdf, destino, int(_campo("graus", "90")),
            paginas=_campo("paginas"), senha=_campo("senha"),
        )
        return _enviar_pdf(destino, f"{_stem(pdf)}_rotacionado.pdf")


@app.post("/api/remove")
def api_remove():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        paginas = _campo("paginas")
        if not paginas:
            raise ErroCliente("Informe as páginas a remover (ex.: 2,4-6).")
        destino = tmp / "out.pdf"
        pu.pages.remover(pdf, destino, paginas, senha=_campo("senha"))
        return _enviar_pdf(destino, f"{_stem(pdf)}_sem_paginas.pdf")


@app.post("/api/reorder")
def api_reorder():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        ordem = _campo("ordem")
        if not ordem:
            raise ErroCliente("Informe a nova ordem (ex.: 3,1,2).")
        destino = tmp / "out.pdf"
        pu.pages.reordenar(pdf, destino, ordem, senha=_campo("senha"))
        return _enviar_pdf(destino, f"{_stem(pdf)}_reordenado.pdf")


@app.post("/api/compress")
def api_compress():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        destino = tmp / "out.pdf"
        r = pu.compress.comprimir(
            pdf, destino, nivel=_campo("nivel", "medio"), senha=_campo("senha")
        )
        resp = _enviar_pdf(destino, f"{_stem(pdf)}_comprimido.pdf")
        resp.headers["X-Reducao"] = f"{r['reducao'] * 100:.1f}"
        resp.headers["X-Engine"] = r["engine"]
        return resp


@app.post("/api/protect")
def api_protect():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        senha_usuario = _campo("senha_usuario")
        if not senha_usuario:
            raise ErroCliente("Informe a senha a aplicar.")
        destino = tmp / "out.pdf"
        pu.security.proteger(
            pdf, destino, senha_usuario,
            senha_atual=_campo("senha_atual"),
            permitir_impressao=_campo("sem_impressao") != "on",
            permitir_copia=_campo("sem_copia") != "on",
            permitir_modificacao=_campo("permitir_modificacao") == "on",
        )
        return _enviar_pdf(destino, f"{_stem(pdf)}_protegido.pdf")


@app.post("/api/unlock")
def api_unlock():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        senha = _campo("senha")
        if not senha:
            raise ErroCliente("Informe a senha atual do PDF.")
        destino = tmp / "out.pdf"
        pu.security.remover_senha(pdf, destino, senha)
        return _enviar_pdf(destino, f"{_stem(pdf)}_sem_senha.pdf")


@app.post("/api/meta")
def api_meta():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        senha = _campo("senha")
        acao = _campo("acao", "ler")
        if acao == "ler":
            return jsonify(pu.metadata.ler_metadados(pdf, senha=senha))
        destino = tmp / "out.pdf"
        if acao == "limpar":
            pu.metadata.limpar_metadados(pdf, destino, senha=senha)
        else:  # editar
            campos = {
                k: request.form.get(k, "")
                for k in ("title", "author", "subject", "keywords")
                if request.form.get(k)
            }
            pu.metadata.editar_metadados(pdf, destino, campos, senha=senha)
        return _enviar_pdf(destino, f"{_stem(pdf)}_metadados.pdf")


@app.post("/api/text")
def api_text():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        texto = pu.extract.extrair_texto(
            pdf, paginas=_campo("paginas"), senha=_campo("senha")
        )
        return jsonify({"texto": texto, "caracteres": len(texto)})


@app.post("/api/tables")
def api_tables():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        saida = tmp / "out"
        ger = pu.extract.extrair_tabelas(
            pdf, saida, paginas=_campo("paginas"), senha=_campo("senha")
        )
        if not ger:
            raise ErroCliente("Nenhuma tabela detectada no PDF.")
        return _enviar_zip(saida, f"{_stem(pdf)}_tabelas.zip")


@app.post("/api/to-images")
def api_to_images():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        saida = tmp / "out"
        pu.images.pdf_para_imagens(
            pdf, saida, dpi=int(_campo("dpi", "150")),
            formato=_campo("formato", "png"),
            paginas=_campo("paginas"), senha=_campo("senha"),
        )
        return _enviar_zip(saida, f"{_stem(pdf)}_imagens.zip")


@app.post("/api/from-images")
def api_from_images():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        imgs = _salvar_uploads("arquivos", tmp)
        destino = tmp / "out.pdf"
        pu.images.imagens_para_pdf(imgs, destino)
        return _enviar_pdf(destino, "imagens.pdf")


@app.post("/api/extract-images")
def api_extract_images():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        saida = tmp / "out"
        ger = pu.attachments.extrair_imagens(pdf, saida, senha=_campo("senha"))
        if not ger:
            raise ErroCliente("Nenhuma imagem embutida encontrada.")
        return _enviar_zip(saida, f"{_stem(pdf)}_imagens_embutidas.zip")


@app.post("/api/ocr")
def api_ocr():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        destino = tmp / "out.pdf"
        pu.ocr.ocr(
            pdf, destino, idioma=_campo("idioma", "por"),
            forcar=_campo("forcar") == "on",
        )
        return _enviar_pdf(destino, f"{_stem(pdf)}_ocr.pdf")


@app.post("/api/watermark")
def api_watermark():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        texto = _campo("texto")
        if not texto:
            raise ErroCliente("Informe o texto da marca d'água.")
        destino = tmp / "out.pdf"
        pu.watermark.marca_dagua_texto(
            pdf, destino, texto,
            opacidade=float(_campo("opacidade", "0.15")),
            tamanho=int(_campo("tamanho", "48")),
            senha=_campo("senha"),
        )
        return _enviar_pdf(destino, f"{_stem(pdf)}_marca.pdf")


@app.post("/api/numerar")
def api_numerar():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        destino = tmp / "out.pdf"
        pu.watermark.numerar_paginas(
            pdf, destino, formato=_campo("formato", "{n} / {total}"),
            senha=_campo("senha"),
        )
        return _enviar_pdf(destino, f"{_stem(pdf)}_numerado.pdf")


@app.post("/api/flatten")
def api_flatten():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pdf = _salvar_upload("arquivo", tmp)
        destino = tmp / "out.pdf"
        pu.attachments.achatar(pdf, destino, senha=_campo("senha"))
        return _enviar_pdf(destino, f"{_stem(pdf)}_achatado.pdf")


# ──────────────────────────────────────────────
# Index + erros
# ──────────────────────────────────────────────

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.errorhandler(ErroCliente)
def _erro_cliente(exc):
    return jsonify({"erro": str(exc)}), 400


@app.errorhandler(WrongPasswordError)
@app.errorhandler(PasswordRequiredError)
def _erro_senha(exc):
    return jsonify({"erro": str(exc)}), 401


@app.errorhandler(MissingDependencyError)
def _erro_dep(exc):
    return jsonify({"erro": str(exc)}), 501


@app.errorhandler(PdfUtilsError)
def _erro_pdf(exc):
    return jsonify({"erro": str(exc)}), 422


@app.errorhandler(413)
def _erro_grande(_):
    return jsonify({"erro": f"Arquivo acima de {TAMANHO_MAXIMO_MB} MB."}), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
