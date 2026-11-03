# pdf-utils

Utilidades **locais** e **open-source** para trabalhar com PDFs — via linha de
comando ou interface web. Tudo roda na sua máquina: **nenhum arquivo é enviado
para a internet**.

Nasceu da união de dois projetos menores (um divisor de PDFs e um recuperador
de senhas) e cresceu para um canivete suíço de PDF.

## Funcionalidades

| # | Comando | O que faz |
|---|---------|-----------|
| 1 | `split` | Divide por página, em blocos de N páginas ou por intervalos |
| 2 | `merge` | Junta vários PDFs em um só |
| 3 | `rotate` | Rotaciona páginas (múltiplos de 90°) |
| 4 | `remove` | Remove páginas por intervalo |
| 5 | `reorder` | Reordena/filtra páginas |
| 6 | `compress` | Comprime/otimiza (Ghostscript ou lossless via pikepdf) |
| 7 | `protect` / `unlock` | Adiciona ou remove senha (AES-256) |
| 8 | `recover` | Recupera senha de um PDF **seu** (força bruta/dicionário) |
| 9 | `text` / `tables` | Extrai texto e tabelas (CSV) |
| 10 | `to-images` / `from-images` | Converte PDF↔imagens |
| 11 | `ocr` | Torna um PDF escaneado pesquisável |
| 12 | `watermark` / `numerar` | Marca d'água e numeração de páginas |
| 13 | `meta` | Vê, edita ou limpa metadados (e remove JavaScript) |
| 14 | `extract-images` / `attachments` | Extrai imagens e anexos embutidos |
| 15 | `flatten` | Achata formulários e anotações |

## Instalação

```bash
# Núcleo (split, merge, pages, compress, security, text)
pip install -e .

# Tudo (web, imagens, tabelas, marca d'água, OCR)
pip install -e ".[all]"
```

Dependências de sistema **opcionais**:
- **Ghostscript** (`gswin64c`/`gs` no PATH) — melhor compressão. Sem ele, a
  compressão usa o modo lossless do pikepdf.
- **Tesseract OCR** — necessário para o comando `ocr`.

Cada funcionalidade degrada graciosamente: se uma dependência faltar, o
comando correspondente informa exatamente o que instalar.

## Uso — CLI

```bash
pdfutils --help                      # lista todos os comandos
pdfutils split doc.pdf --blocos 10   # blocos de 10 páginas
pdfutils split doc.pdf --intervalos 1-3 8,10
pdfutils merge a.pdf b.pdf -o junto.pdf
pdfutils rotate doc.pdf -o r.pdf --graus 90 --paginas 1-3
pdfutils compress doc.pdf -o menor.pdf --nivel forte
pdfutils protect doc.pdf -o seguro.pdf --senha-usuario minhaSenha
pdfutils unlock seguro.pdf -o aberto.pdf --senha minhaSenha
pdfutils text doc.pdf -o texto.txt
pdfutils to-images doc.pdf -o imgs/ --dpi 200 --formato png
pdfutils ocr escaneado.pdf -o pesquisavel.pdf --idioma por
pdfutils watermark doc.pdf -o marca.pdf --texto "CONFIDENCIAL"
pdfutils meta doc.pdf                 # lê metadados
pdfutils meta doc.pdf -o m.pdf --set title="Relatório" author="Mateus"
```

## Uso — Web

```bash
pip install -e ".[all]"
python web/app.py
# abra http://127.0.0.1:5000
```

A interface mostra todas as ferramentas em cards, com arrastar-e-soltar.
O processamento ocorre em um diretório temporário por requisição e nada é
mantido no servidor após a resposta.

## Uso — como biblioteca

```python
import pdfutils as pu

pu.split.dividir_por_blocos("doc.pdf", "saida/", 5)
pu.merge.juntar(["a.pdf", "b.pdf"], "junto.pdf")
texto = pu.extract.extrair_texto("doc.pdf", paginas="1-3")
```

## Recuperação de senha — uso responsável

O comando `recover` destina-se a recuperar o acesso a PDFs **que você possui**
e cuja senha esqueceu. Não o utilize em arquivos de terceiros sem autorização.

## Testes

```bash
pip install pytest
python -m pytest
```

## Estrutura

```
pdfutils/        # pacote: um módulo por família de operações + cli.py
web/             # backend Flask (app.py) + static/ (UI)
tests/           # testes de fumaça
Pdf Splitter/    # projeto original (mantido para referência)
pdf Cracker/     # projeto original (mantido para referência)
```

## Licença

MIT — veja [LICENSE](LICENSE).
