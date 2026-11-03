"use strict";

/* ───────────────────────────────────────────────────────────
   pdf-utils — frontend
   Vanilla JS, no dependencies. Fully offline.
   ─────────────────────────────────────────────────────────── */

// Ordem fixa dos grupos exigida pelo produto.
const ORDEM_GRUPOS = [
  "Organizar",
  "Otimizar",
  "Segurança",
  "Extrair",
  "Converter",
  "Editar",
];

// Ferramentas que aceitam uma senha opcional (PDF de entrada protegido).
const COM_SENHA = new Set([
  "split", "rotate", "remove", "reorder", "compress", "meta", "text",
  "tables", "to-images", "extract-images", "watermark", "numerar", "flatten",
]);

/*
 * Esquema de campos por ferramenta.
 * Tipos: text | number | select | checkbox | password
 * showWhen: { campo: valor } — exibe o campo só quando outro campo tem o valor.
 */
const CAMPOS = {
  split: [
    { name: "modo", label: "Modo de divisão", type: "select", default: "paginas", options: [
      ["paginas", "Uma página por arquivo"],
      ["blocos", "Blocos de N páginas"],
      ["intervalos", "Intervalos personalizados"],
    ]},
    { name: "tamanho", label: "Páginas por bloco", type: "number", default: "2", min: 1, showWhen: { modo: "blocos" } },
    { name: "intervalos", label: "Intervalos", type: "text", placeholder: "1-3 5,7", showWhen: { modo: "intervalos" },
      hint: "Separe por espaços. Ex.: 1-3 5,7" },
    { name: "sem_duplicados", label: "Ignorar páginas duplicadas", type: "checkbox", showWhen: { modo: "paginas" } },
  ],
  merge: [],
  rotate: [
    { name: "graus", label: "Rotação", type: "select", default: "90", options: [
      ["90", "90° (horário)"], ["180", "180°"], ["270", "270° (anti-horário)"],
    ]},
    { name: "paginas", label: "Páginas", type: "text", optional: true, placeholder: "1-3,5",
      hint: "Deixe vazio para girar todas." },
  ],
  remove: [
    { name: "paginas", label: "Páginas a remover", type: "text", required: true, placeholder: "2,4-6" },
  ],
  reorder: [
    { name: "ordem", label: "Nova ordem das páginas", type: "text", required: true, placeholder: "3,1,2",
      hint: "Liste os números na ordem desejada." },
  ],
  compress: [
    { name: "nivel", label: "Nível de compressão", type: "select", default: "medio", options: [
      ["leve", "Leve"], ["medio", "Médio"], ["forte", "Forte"],
    ]},
  ],
  ocr: [
    { name: "idioma", label: "Idioma", type: "text", default: "por",
      hint: "Código Tesseract. Ex.: por, eng, por+eng" },
    { name: "forcar", label: "Forçar OCR mesmo se já houver texto", type: "checkbox" },
  ],
  protect: [
    { name: "senha_usuario", label: "Senha a aplicar", type: "password", required: true },
    { name: "senha_atual", label: "Senha atual", type: "password", optional: true,
      hint: "Preencha apenas se o PDF já estiver protegido." },
    { name: "sem_impressao", label: "Bloquear impressão", type: "checkbox" },
    { name: "sem_copia", label: "Bloquear cópia de texto", type: "checkbox" },
    { name: "permitir_modificacao", label: "Permitir modificação", type: "checkbox" },
  ],
  unlock: [
    { name: "senha", label: "Senha atual do PDF", type: "password", required: true },
  ],
  meta: [
    { name: "acao", label: "Ação", type: "select", default: "ler", options: [
      ["ler", "Ler metadados"],
      ["editar", "Editar metadados"],
      ["limpar", "Limpar tudo (metadados + JavaScript)"],
    ]},
    { name: "title", label: "Título", type: "text", optional: true, showWhen: { acao: "editar" } },
    { name: "author", label: "Autor", type: "text", optional: true, showWhen: { acao: "editar" } },
    { name: "subject", label: "Assunto", type: "text", optional: true, showWhen: { acao: "editar" } },
    { name: "keywords", label: "Palavras-chave", type: "text", optional: true, showWhen: { acao: "editar" } },
  ],
  text: [
    { name: "paginas", label: "Páginas", type: "text", optional: true, placeholder: "1-3,5",
      hint: "Deixe vazio para extrair tudo." },
  ],
  tables: [
    { name: "paginas", label: "Páginas", type: "text", optional: true, placeholder: "1-3,5",
      hint: "Deixe vazio para procurar em todas." },
  ],
  "to-images": [
    { name: "dpi", label: "DPI", type: "number", default: "150", min: 1 },
    { name: "formato", label: "Formato", type: "select", default: "png", options: [
      ["png", "PNG"], ["jpg", "JPG"],
    ]},
    { name: "paginas", label: "Páginas", type: "text", optional: true, placeholder: "1-3,5",
      hint: "Deixe vazio para converter todas." },
  ],
  "from-images": [],
  "extract-images": [],
  watermark: [
    { name: "texto", label: "Texto da marca d'água", type: "text", required: true, placeholder: "CONFIDENCIAL" },
    { name: "opacidade", label: "Opacidade", type: "number", default: "0.15", min: 0, max: 1, step: "0.05",
      hint: "Entre 0 (invisível) e 1 (opaco)." },
    { name: "tamanho", label: "Tamanho da fonte", type: "number", default: "48", min: 1 },
  ],
  numerar: [
    { name: "formato", label: "Formato", type: "text", default: "{n} / {total}",
      hint: "Use {n} para a página atual e {total} para o total." },
  ],
  flatten: [],
};

// Mensagens amigáveis por código de status.
const ERRO_STATUS = {
  401: "Senha necessária ou incorreta.",
  413: "Arquivo grande demais.",
  422: "Não foi possível processar o PDF.",
  501: "Dependência ausente no servidor.",
};

// ─────────────── Estado ───────────────

let catalogo = [];
let ferramentaAtual = null;
let arquivos = []; // File[]
let ultimoFoco = null; // elemento que abriu o modal
let defsAtuais = []; // definições de campos do modal aberto

// ─────────────── Helpers DOM ───────────────

const $ = (sel, raiz = document) => raiz.querySelector(sel);

function el(tag, attrs = {}, filhos = []) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k === "html") n.innerHTML = v;
    else if (k === "dataset") Object.assign(n.dataset, v);
    else if (v !== null && v !== undefined && v !== false) n.setAttribute(k, v);
  }
  for (const f of [].concat(filhos)) {
    if (f) n.append(f.nodeType ? f : document.createTextNode(f));
  }
  return n;
}

function formatarTamanho(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(0)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

// ─────────────── Catálogo ───────────────

async function carregarCatalogo() {
  try {
    const resp = await fetch("/api/catalogo");
    if (!resp.ok) throw new Error("status " + resp.status);
    catalogo = await resp.json();
    $("#carregando-catalogo").hidden = true;
    $("#ferramentas").setAttribute("aria-busy", "false");
    renderCatalogo("");
  } catch (e) {
    $("#carregando-catalogo").hidden = true;
    $("#ferramentas").setAttribute("aria-busy", "false");
    $("#erro-catalogo").hidden = false;
  }
}

function renderCatalogo(filtro) {
  const grade = $("#grade");
  grade.innerHTML = "";
  const termo = filtro.trim().toLowerCase();

  const correspondem = catalogo.filter((f) => {
    if (!termo) return true;
    return (
      f.nome.toLowerCase().includes(termo) ||
      (f.desc || "").toLowerCase().includes(termo)
    );
  });

  $("#vazio").hidden = correspondem.length > 0;

  let indiceGlobal = 0;
  for (const grupo of ORDEM_GRUPOS) {
    const doGrupo = correspondem.filter((f) => f.grupo === grupo);
    if (doGrupo.length === 0) continue;

    const secao = el("section", { class: "grupo" });
    secao.append(el("h2", { class: "grupo__titulo", text: grupo }));
    const cards = el("div", { class: "cards" });

    for (const f of doGrupo) {
      const card = el("button", {
        class: "card",
        type: "button",
        "aria-label": `${f.nome}: ${f.desc}`,
      });
      // Stagger (curto) via delay inline.
      card.style.animationDelay = `${Math.min(indiceGlobal, 10) * 40}ms`;
      indiceGlobal++;

      const topo = el("div", { class: "card__topo" }, [
        el("span", { class: "card__nome", text: f.nome }),
      ]);
      if (f.multi) {
        topo.append(el("span", { class: "card__multi", text: "vários" }));
      }
      card.append(topo);
      card.append(el("p", { class: "card__desc", text: f.desc }));
      card.addEventListener("click", () => abrirModal(f, card));
      cards.append(card);
    }

    secao.append(cards);
    grade.append(secao);
  }
}

// ─────────────── Modal ───────────────

function abrirModal(ferramenta, origem) {
  ferramentaAtual = ferramenta;
  arquivos = [];
  ultimoFoco = origem || document.activeElement;

  $("#modal-titulo").textContent = ferramenta.nome;
  $("#modal-desc").textContent = ferramenta.desc;

  // Dropzone
  const multi = !!ferramenta.multi;
  const input = $("#file-input");
  input.multiple = multi;
  input.accept = ferramenta.id === "from-images"
    ? "image/*"
    : "application/pdf,.pdf";
  $("#dropzone-label").textContent = ferramenta.id === "from-images"
    ? (multi ? "Arraste imagens aqui" : "Arraste uma imagem aqui")
    : (multi ? "Arraste PDFs aqui" : "Arraste um PDF aqui");

  renderArquivos();
  construirCampos(ferramenta);
  limparResultado();
  atualizarBotao();

  const backdrop = $("#modal-backdrop");
  backdrop.hidden = false;
  document.body.style.overflow = "hidden";
  // força reflow para a transição de entrada
  requestAnimationFrame(() => backdrop.setAttribute("data-open", ""));

  // Foco inicial no dropzone.
  requestAnimationFrame(() => $("#dropzone").focus());
}

function fecharModal() {
  const backdrop = $("#modal-backdrop");
  if (backdrop.hidden) return;
  backdrop.removeAttribute("data-open");
  document.body.style.overflow = "";

  const esconder = () => {
    backdrop.hidden = true;
    backdrop.removeEventListener("transitionend", esconder);
  };
  // fallback caso transição esteja desativada (reduced motion)
  backdrop.addEventListener("transitionend", esconder);
  setTimeout(esconder, 400);

  ferramentaAtual = null;
  arquivos = [];
  if (ultimoFoco && ultimoFoco.focus) ultimoFoco.focus();
}

function construirCampos(ferramenta) {
  const cont = $("#campos");
  cont.innerHTML = "";

  const defs = (CAMPOS[ferramenta.id] || []).slice();
  if (COM_SENHA.has(ferramenta.id)) {
    defs.push({
      name: "senha",
      label: "Senha",
      type: "password",
      optional: true,
      hint: "Preencha somente se o PDF estiver protegido.",
    });
  }

  defsAtuais = defs;
  for (const def of defs) {
    cont.append(construirCampo(def));
  }
  aplicarCondicionais();
}

// Mostra/esconde campos conforme a regra showWhen do modal atual.
function aplicarCondicionais() {
  const cont = $("#campos");
  for (const def of defsAtuais) {
    if (!def.showWhen) continue;
    const wrapper = cont.querySelector(`[data-campo="${def.name}"]`);
    if (!wrapper) continue;
    const visivel = Object.entries(def.showWhen).every(([k, v]) => {
      const ctrl = cont.querySelector(`[name="${k}"]`);
      return ctrl && ctrl.value === v;
    });
    wrapper.classList.toggle("campo--oculto", !visivel);
  }
}

function construirCampo(def) {
  const id = `campo-${def.name}`;

  if (def.type === "checkbox") {
    const label = el("label", { class: "check", "data-campo": def.name });
    const input = el("input", { type: "checkbox", id, name: def.name, value: "on" });
    label.append(input, el("span", { text: def.label }));
    return label;
  }

  const wrapper = el("div", { class: "campo", "data-campo": def.name });
  const label = el("label", { class: "campo__label", for: id });
  label.append(document.createTextNode(def.label + " "));
  if (def.optional) label.append(el("span", { class: "opt", text: "(opcional)" }));
  wrapper.append(label);

  let control;
  if (def.type === "select") {
    control = el("select", { class: "select", id, name: def.name });
    for (const [valor, texto] of def.options) {
      const opt = el("option", { value: valor, text: texto });
      if (valor === def.default) opt.selected = true;
      control.append(opt);
    }
  } else {
    const tipo = def.type === "password" ? "password"
      : def.type === "number" ? "number"
      : "text";
    control = el("input", {
      class: "input",
      type: tipo,
      id,
      name: def.name,
      placeholder: def.placeholder || "",
    });
    if (def.default !== undefined) control.value = def.default;
    if (def.min !== undefined) control.min = def.min;
    if (def.max !== undefined) control.max = def.max;
    if (def.step !== undefined) control.step = def.step;
  }
  wrapper.append(control);

  if (def.hint) wrapper.append(el("p", { class: "campo__hint", text: def.hint }));
  return wrapper;
}

// ─────────────── Arquivos / dropzone ───────────────

function adicionarArquivos(lista) {
  const novos = Array.from(lista);
  if (!novos.length) return;
  if (ferramentaAtual && ferramentaAtual.multi) {
    arquivos = arquivos.concat(novos);
  } else {
    arquivos = [novos[0]];
  }
  renderArquivos();
  atualizarBotao();
  limparResultado();
}

function removerArquivo(i) {
  arquivos.splice(i, 1);
  renderArquivos();
  atualizarBotao();
}

function renderArquivos() {
  const ul = $("#lista-arquivos");
  ul.innerHTML = "";
  arquivos.forEach((f, i) => {
    const li = el("li", { class: "arquivo" });
    li.append(el("span", { class: "arquivo__nome", text: f.name, title: f.name }));
    li.append(el("span", { class: "arquivo__tam", text: formatarTamanho(f.size) }));
    const rm = el("button", {
      class: "arquivo__rm",
      type: "button",
      "aria-label": `Remover ${f.name}`,
      html: "<svg viewBox='0 0 24 24' width='16' height='16'><path d='M6 6l12 12M18 6L6 18' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round'/></svg>",
    });
    rm.addEventListener("click", () => removerArquivo(i));
    li.append(rm);
    ul.append(li);
  });
}

function atualizarBotao() {
  $("#submeter").disabled = arquivos.length === 0;
}

// ─────────────── Resultado ───────────────

function limparResultado() {
  const r = $("#resultado");
  r.hidden = true;
  r.innerHTML = "";
  r.className = "resultado";
}

function mostrarErro(mensagem) {
  const r = $("#resultado");
  r.className = "resultado resultado--erro";
  r.hidden = false;
  r.innerHTML = "";
  r.append(el("div", { class: "resultado__titulo" }, [
    el("span", { html: "<svg viewBox='0 0 24 24' width='18' height='18'><circle cx='12' cy='12' r='9' fill='none' stroke='currentColor' stroke-width='2'/><path d='M12 7v6M12 16.5v.5' stroke='currentColor' stroke-width='2' stroke-linecap='round'/></svg>" }),
    "Erro",
  ]));
  r.append(el("p", { class: "resultado__msg", text: mensagem }));
}

function baseResultadoOk(titulo) {
  const r = $("#resultado");
  r.className = "resultado resultado--ok";
  r.hidden = false;
  r.innerHTML = "";
  r.append(el("div", { class: "resultado__titulo" }, [
    el("span", { html: "<svg viewBox='0 0 24 24' width='18' height='18'><path d='M20 6L9 17l-5-5' fill='none' stroke='currentColor' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'/></svg>" }),
    titulo,
  ]));
  return r;
}

// ─────────────── Submit ───────────────

function nomeDownload(cabecalho, padrao) {
  if (!cabecalho) return padrao;
  // filename*=UTF-8''... tem prioridade
  const estrela = /filename\*=(?:UTF-8'')?([^;]+)/i.exec(cabecalho);
  if (estrela) {
    try { return decodeURIComponent(estrela[1].replace(/["']/g, "").trim()); }
    catch { /* ignora */ }
  }
  const simples = /filename="?([^";]+)"?/i.exec(cabecalho);
  if (simples) return simples[1].trim();
  return padrao;
}

async function processar(e) {
  e.preventDefault();
  if (!ferramentaAtual || arquivos.length === 0) return;

  const btn = $("#submeter");
  const ferramenta = ferramentaAtual;

  const fd = new FormData();
  const campoArquivo = ferramenta.multi ? "arquivos" : "arquivo";
  if (ferramenta.multi) {
    for (const f of arquivos) fd.append(campoArquivo, f);
  } else {
    fd.append(campoArquivo, arquivos[0]);
  }

  // Campos do formulário.
  const form = $("#modal-form");
  for (const control of form.querySelectorAll("[name]")) {
    if (control.type === "checkbox") {
      if (control.checked) fd.append(control.name, "on");
    } else if (control.value !== "") {
      // ignora campos ocultos por showWhen
      const wrapper = control.closest("[data-campo]");
      if (wrapper && wrapper.classList.contains("campo--oculto")) continue;
      fd.append(control.name, control.value);
    }
  }

  btn.classList.add("is-loading");
  btn.disabled = true;
  $("#submeter .btn__label").textContent = "Processando…";
  limparResultado();

  try {
    const resp = await fetch(`/api/${ferramenta.id}`, { method: "POST", body: fd });
    const tipo = resp.headers.get("Content-Type") || "";

    if (!resp.ok) {
      let msg = ERRO_STATUS[resp.status] || `Erro ${resp.status}.`;
      if (tipo.includes("application/json")) {
        try {
          const dados = await resp.json();
          if (dados && dados.erro) msg = dados.erro;
        } catch { /* mantém msg padrão */ }
      }
      mostrarErro(msg);
      return;
    }

    if (tipo.includes("application/json")) {
      const dados = await resp.json();
      renderJsonSucesso(ferramenta, dados);
      return;
    }

    // Arquivo (PDF ou ZIP) → download.
    const blob = await resp.blob();
    const padrao = tipo.includes("zip")
      ? `${ferramenta.id}.zip`
      : `${ferramenta.id}.pdf`;
    const nome = nomeDownload(resp.headers.get("Content-Disposition"), padrao);
    const url = URL.createObjectURL(blob);

    // dispara download automático
    const a = document.createElement("a");
    a.href = url;
    a.download = nome;
    document.body.append(a);
    a.click();
    a.remove();

    renderDownloadSucesso(ferramenta, resp, blob, url, nome);
  } catch (err) {
    mostrarErro("Não foi possível conectar ao servidor. Verifique se ele está em execução.");
  } finally {
    btn.classList.remove("is-loading");
    btn.disabled = arquivos.length === 0;
    $("#submeter .btn__label").textContent = "Processar";
  }
}

function renderDownloadSucesso(ferramenta, resp, blob, url, nome) {
  const r = baseResultadoOk("Pronto!");
  r.append(el("p", { class: "resultado__msg", text: `Arquivo gerado (${formatarTamanho(blob.size)}). O download deve ter começado automaticamente.` }));

  // Compressão: mostrar X-Reducao / X-Engine.
  const reducao = resp.headers.get("X-Reducao");
  const engine = resp.headers.get("X-Engine");
  if (reducao || engine) {
    const meta = el("div", { class: "resultado__meta" });
    if (reducao) meta.append(el("span", { class: "chip", text: `Redução: ${reducao}%` }));
    if (engine) meta.append(el("span", { class: "chip", text: `Motor: ${engine}` }));
    r.append(meta);
  }

  const acoes = el("div", { class: "resultado__acoes" });
  const link = el("a", { class: "btn btn--link", href: url, download: nome, text: "Baixar novamente" });
  acoes.append(link);
  r.append(acoes);
}

function renderJsonSucesso(ferramenta, dados) {
  if (ferramenta.id === "text") {
    const r = baseResultadoOk("Texto extraído");
    r.append(el("p", { class: "resultado__msg", text: `${dados.caracteres} caractere(s).` }));
    const box = el("div", { class: "texto-box", text: dados.texto || "(sem texto)" });
    r.append(box);
    const acoes = el("div", { class: "resultado__acoes" });
    const copiar = el("button", { class: "btn btn--link", type: "button", text: "Copiar" });
    copiar.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(dados.texto || "");
        copiar.textContent = "Copiado!";
        setTimeout(() => (copiar.textContent = "Copiar"), 1600);
      } catch {
        copiar.textContent = "Falha ao copiar";
        setTimeout(() => (copiar.textContent = "Copiar"), 1600);
      }
    });
    acoes.append(copiar);
    r.append(acoes);
    return;
  }

  // meta "ler" → key/value
  const r = baseResultadoOk("Metadados");
  const chaves = Object.keys(dados);
  if (chaves.length === 0) {
    r.append(el("p", { class: "resultado__msg", text: "Nenhum metadado encontrado." }));
    return;
  }
  const kv = el("div", { class: "kv" });
  // info (_prefixo) por último
  const normais = chaves.filter((k) => !k.startsWith("_"));
  const infos = chaves.filter((k) => k.startsWith("_"));
  for (const k of normais.concat(infos)) {
    const row = el("div", { class: "kv__row" + (k.startsWith("_") ? " kv__row--info" : "") });
    const rotulo = k.startsWith("_") ? k.slice(1) : k;
    row.append(el("span", { class: "kv__k", text: rotulo }));
    row.append(el("span", { class: "kv__v", text: String(dados[k]) }));
    kv.append(row);
  }
  r.append(kv);
}

// ─────────────── Foco / teclado no modal ───────────────

function tratarTeclado(e) {
  const backdrop = $("#modal-backdrop");
  if (backdrop.hidden) return;

  if (e.key === "Escape") {
    e.preventDefault();
    fecharModal();
    return;
  }

  if (e.key === "Tab") {
    const foco = $("#modal").querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    const visiveis = Array.from(foco).filter((n) => n.offsetParent !== null || n === document.activeElement);
    if (visiveis.length === 0) return;
    const primeiro = visiveis[0];
    const ultimo = visiveis[visiveis.length - 1];
    if (e.shiftKey && document.activeElement === primeiro) {
      e.preventDefault();
      ultimo.focus();
    } else if (!e.shiftKey && document.activeElement === ultimo) {
      e.preventDefault();
      primeiro.focus();
    }
  }
}

// ─────────────── Inicialização ───────────────

function init() {
  carregarCatalogo();

  $("#busca").addEventListener("input", (e) => renderCatalogo(e.target.value));

  $("#fechar-modal").addEventListener("click", fecharModal);
  $("#modal-backdrop").addEventListener("mousedown", (e) => {
    if (e.target === $("#modal-backdrop")) fecharModal();
  });
  $("#modal-form").addEventListener("submit", processar);
  $("#campos").addEventListener("change", aplicarCondicionais);
  document.addEventListener("keydown", tratarTeclado);

  // Dropzone
  const dz = $("#dropzone");
  const input = $("#file-input");
  dz.addEventListener("click", () => input.click());
  dz.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      input.click();
    }
  });
  input.addEventListener("change", () => {
    adicionarArquivos(input.files);
    input.value = ""; // permite re-selecionar o mesmo arquivo
  });

  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => {
      e.preventDefault();
      dz.classList.add("is-dragover");
    })
  );
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => {
      e.preventDefault();
      if (ev === "dragleave" && dz.contains(e.relatedTarget)) return;
      dz.classList.remove("is-dragover");
    })
  );
  dz.addEventListener("drop", (e) => {
    if (e.dataTransfer && e.dataTransfer.files.length) {
      adicionarArquivos(e.dataTransfer.files);
    }
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
