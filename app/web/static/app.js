"use strict";

// Credenciais públicas e sintéticas usadas somente na demonstração local.
const identities = {
  aurora: {
    company: "Aurora Tecnologia",
    username: "aurora.demo",
    password: "Aurora#2026",
    initials: "AT",
    className: "aurora",
  },
  brisa: {
    company: "Brisa Sistemas",
    username: "brisa.demo",
    password: "Brisa#2026",
    initials: "BS",
    className: "brisa",
  },
};

const exampleQuestions = [
  "Qual é o limite diário de alimentação em viagem nacional?",
  "Em quanto tempo devo solicitar o reembolso?",
  "Qual é o limite permitido para hotel?",
];

const state = { token: null, identity: null, context: null, requestId: null };
const elements = {
  loginView: document.querySelector("#login-view"),
  workspace: document.querySelector("#workspace"),
  loginError: document.querySelector("#login-error"),
  logoutButton: document.querySelector("#logout-button"),
  systemStatus: document.querySelector("#system-status"),
  sessionIcon: document.querySelector("#session-icon"),
  sessionCompany: document.querySelector("#session-company"),
  sessionTenant: document.querySelector("#session-tenant"),
  askForm: document.querySelector("#ask-form"),
  askButton: document.querySelector("#ask-button"),
  question: document.querySelector("#question"),
  characterCount: document.querySelector("#character-count"),
  examples: document.querySelector("#examples"),
  loadingCard: document.querySelector("#loading-card"),
  loadingStep: document.querySelector("#loading-step"),
  stateCard: document.querySelector("#state-card"),
  stateIcon: document.querySelector("#state-icon"),
  stateTitle: document.querySelector("#state-title"),
  stateMessage: document.querySelector("#state-message"),
  responseCard: document.querySelector("#response-card"),
  answerText: document.querySelector("#answer-text"),
  confidenceBadge: document.querySelector("#confidence-badge"),
  sourcesSection: document.querySelector("#sources-section"),
  sourcesList: document.querySelector("#sources-list"),
  sourceCount: document.querySelector("#source-count"),
  traceSummary: document.querySelector("#trace-summary"),
  traceGrid: document.querySelector("#trace-grid"),
  requestId: document.querySelector("#request-id"),
  copyRequest: document.querySelector("#copy-request"),
  feedbackRow: document.querySelector("#feedback-row"),
  feedbackConfirmation: document.querySelector("#feedback-confirmation"),
};

function setHidden(element, hidden) {
  element.classList.toggle("hidden", hidden);
}

async function api(path, options = {}, timeoutMs = 70000) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  try {
    return await fetch(path, { ...options, headers, signal: controller.signal });
  } finally {
    window.clearTimeout(timeout);
  }
}

async function checkOperations() {
  const dot = elements.systemStatus.querySelector(".status-dot");
  const label = elements.systemStatus.querySelector("span:last-child");
  dot.className = "status-dot checking";
  label.textContent = "Verificando serviços";
  try {
    const response = await api("/ready", {}, 4000);
    const data = await response.json();
    if (response.ok) {
      dot.className = "status-dot";
      label.textContent = "Ollama e Qdrant prontos";
    } else {
      const unavailable = Object.entries(data.dependencies || {}).filter(([, ready]) => !ready).map(([name]) => name).join(" e ");
      dot.className = "status-dot down";
      label.textContent = `${unavailable || "Serviço"} indisponível`;
    }
  } catch {
    dot.className = "status-dot down";
    label.textContent = "API indisponível";
  }
}

async function login(identityKey) {
  const identity = identities[identityKey];
  document.querySelectorAll(".identity-card").forEach((button) => { button.disabled = true; });
  setHidden(elements.loginError, true);
  try {
    const response = await api("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username: identity.username, password: identity.password }),
    }, 10000);
    if (!response.ok) throw new Error("Não foi possível autenticar a identidade sintética.");
    const data = await response.json();
    state.token = data.access_token;
    state.identity = identity;
    state.context = data.context;
    showWorkspace();
  } catch (error) {
    elements.loginError.textContent = error.message || "Falha ao acessar a API.";
    setHidden(elements.loginError, false);
  } finally {
    document.querySelectorAll(".identity-card").forEach((button) => { button.disabled = false; });
  }
}

function showWorkspace() {
  elements.sessionIcon.textContent = state.identity.initials;
  elements.sessionIcon.className = `identity-icon ${state.identity.className}`;
  elements.sessionCompany.textContent = state.identity.company;
  elements.sessionTenant.textContent = state.context.tenant_id;
  setHidden(elements.loginView, true);
  setHidden(elements.workspace, false);
  setHidden(elements.logoutButton, false);
  elements.question.focus();
}

function logout() {
  state.token = null;
  state.identity = null;
  state.context = null;
  state.requestId = null;
  elements.question.value = "";
  updateCharacterCount();
  setHidden(elements.workspace, true);
  setHidden(elements.logoutButton, true);
  setHidden(elements.responseCard, true);
  setHidden(elements.stateCard, true);
  setHidden(elements.loginView, false);
}

function showState(kind, title, message) {
  const icons = { warning: "!", error: "×", info: "i" };
  elements.stateCard.className = `state-card ${kind}`;
  elements.stateIcon.textContent = icons[kind] || "i";
  elements.stateTitle.textContent = title;
  elements.stateMessage.textContent = message;
  setHidden(elements.stateCard, false);
}

function hideState() {
  setHidden(elements.stateCard, true);
}

function startLoading() {
  const steps = ["Gerando o vetor da pergunta...", "Buscando políticas autorizadas...", "Reordenando as melhores fontes...", "Gerando uma resposta fundamentada..."];
  let index = 0;
  elements.loadingStep.textContent = steps[0];
  setHidden(elements.loadingCard, false);
  elements.askButton.disabled = true;
  return window.setInterval(() => {
    index = Math.min(index + 1, steps.length - 1);
    elements.loadingStep.textContent = steps[index];
  }, 1800);
}

function stopLoading(interval) {
  window.clearInterval(interval);
  setHidden(elements.loadingCard, true);
  elements.askButton.disabled = false;
}

async function askQuestion(event) {
  event.preventDefault();
  const question = elements.question.value.trim();
  if (question.length < 3 || !state.token) return;
  hideState();
  setHidden(elements.responseCard, true);
  setHidden(elements.feedbackConfirmation, true);
  const loadingInterval = startLoading();
  try {
    const response = await api("/v1/ask", { method: "POST", body: JSON.stringify({ question }) });
    const data = await response.json();
    if (!response.ok) {
      handleApiError(response.status, data.detail);
      return;
    }
    renderResponse(data);
  } catch (error) {
    if (error.name === "AbortError") {
      showState("warning", "A consulta excedeu o tempo esperado", "O Ollama pode estar carregando o modelo. Aguarde alguns segundos e tente novamente.");
    } else {
      showState("error", "Não foi possível acessar a API", "Verifique se a aplicação está em execução e tente novamente.");
    }
  } finally {
    stopLoading(loadingInterval);
  }
}

function handleApiError(status, detail) {
  if (status === 400) {
    showState("warning", "Pergunta bloqueada por segurança", detail || "A pergunta contém uma instrução não permitida.");
  } else if (status === 401) {
    showState("error", "Sessão expirada", "Escolha novamente uma empresa fictícia para continuar.");
    window.setTimeout(logout, 1600);
  } else if (status === 503) {
    showState("error", "Serviço temporariamente indisponível", detail || "Ollama ou Qdrant não respondeu. Consulte o estado operacional no topo.");
    checkOperations();
  } else {
    showState("error", "A consulta não pôde ser concluída", detail || "Revise a pergunta e tente novamente.");
  }
}

function renderResponse(data) {
  state.requestId = data.request_id;
  elements.answerText.textContent = data.answer;
  renderConfidence(data.confidence);
  renderSources(data.sources || []);
  renderTrace(data);
  setHidden(elements.feedbackRow, false);
  setHidden(elements.responseCard, false);
  if (data.generation.status === "no_evidence" || !(data.sources || []).length) {
    showState("info", "Nenhuma evidência suficiente foi encontrada", "O assistente recusou responder sem apoio nas políticas autorizadas.");
  } else if (data.generation.status === "degraded") {
    showState("warning", "Resposta em modo degradado", "A geração falhou, então a melhor fonte foi apresentada sem inventar uma resposta.");
  }
  elements.responseCard.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderConfidence(confidence) {
  const labels = { high: "Confiança alta", medium: "Confiança média", low: "Confiança baixa" };
  elements.confidenceBadge.textContent = labels[confidence] || "Confiança não informada";
  elements.confidenceBadge.className = `confidence ${confidence}`;
}

function renderSources(sources) {
  elements.sourcesList.replaceChildren();
  elements.sourceCount.textContent = `${sources.length} ${sources.length === 1 ? "fonte" : "fontes"}`;
  setHidden(elements.sourcesSection, sources.length === 0);
  sources.forEach((source) => {
    const card = document.createElement("article");
    card.className = "source-card";
    const accent = document.createElement("span");
    accent.className = "source-accent";
    const content = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = source.title;
    const meta = document.createElement("span");
    meta.className = "source-meta";
    meta.textContent = `${source.section} · ${source.version} · ${source.chunk_id}`;
    content.append(title, meta);
    const score = document.createElement("span");
    score.className = "source-score";
    score.textContent = `score ${Number(source.score).toFixed(3)}`;
    card.append(accent, content, score);
    elements.sourcesList.append(card);
  });
}

function renderTrace(data) {
  elements.traceGrid.replaceChildren();
  const timings = data.trace?.timings_ms || { total: data.latency_ms };
  const preferred = ["ollama_embedding", "retrieval", "reranking", "ollama_generation", "total"];
  const labels = { ollama_embedding: "Embedding", retrieval: "Retrieval", reranking: "Re-ranking", ollama_generation: "Ollama", total: "Total" };
  preferred.filter((name) => timings[name] !== undefined).forEach((name) => {
    const item = document.createElement("div");
    item.className = "trace-item";
    const label = document.createElement("span");
    label.textContent = labels[name];
    const value = document.createElement("strong");
    value.textContent = `${Number(timings[name]).toFixed(1)} ms`;
    item.append(label, value);
    elements.traceGrid.append(item);
  });
  elements.traceSummary.textContent = `${data.generation.model} · ${data.generation.prompt_version}`;
  elements.requestId.textContent = data.request_id;
}

async function sendFeedback(rating) {
  if (!state.requestId) return;
  elements.feedbackRow.querySelectorAll("button").forEach((button) => { button.disabled = true; });
  try {
    const response = await api("/v1/feedback", { method: "POST", body: JSON.stringify({ request_id: state.requestId, rating }) }, 10000);
    if (!response.ok) throw new Error();
    elements.feedbackConfirmation.textContent = rating === "positive" ? "Obrigado. A resposta foi marcada como útil." : "Obrigado. A resposta foi marcada para revisão.";
    setHidden(elements.feedbackConfirmation, false);
    setHidden(elements.feedbackRow, true);
  } catch {
    showState("error", "Feedback não enviado", "A resposta continua disponível. Tente avaliar novamente.");
    elements.feedbackRow.querySelectorAll("button").forEach((button) => { button.disabled = false; });
  }
}

function updateCharacterCount() {
  elements.characterCount.textContent = `${elements.question.value.length.toLocaleString("pt-BR")} / 2.000`;
}

function buildExamples() {
  exampleQuestions.forEach((question) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = question;
    button.addEventListener("click", () => { elements.question.value = question; updateCharacterCount(); elements.question.focus(); });
    elements.examples.append(button);
  });
}

document.querySelectorAll(".identity-card").forEach((button) => button.addEventListener("click", () => login(button.dataset.identity)));
elements.logoutButton.addEventListener("click", logout);
elements.askForm.addEventListener("submit", askQuestion);
elements.question.addEventListener("input", updateCharacterCount);
elements.feedbackRow.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => sendFeedback(button.dataset.rating)));
elements.copyRequest.addEventListener("click", async () => {
  await navigator.clipboard.writeText(state.requestId || "");
  elements.copyRequest.textContent = "Copiado";
  window.setTimeout(() => { elements.copyRequest.textContent = "Copiar"; }, 1200);
});

buildExamples();
checkOperations();
window.setInterval(checkOperations, 30000);
