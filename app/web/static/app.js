"use strict";

// Ao abrir o HTML diretamente, as chamadas continuam apontando para a API local.
// Quando a interface vem do FastAPI, uma string vazia mantém o mesmo endereço e porta.
const API_BASE_URL = window.location.protocol === "file:" ? "http://localhost:8000" : "";

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
  "Posso despachar uma mala nesta viagem?",
  "Quanto posso gastar com hotel?",
  "Como peço o reembolso?",
  "Posso usar aplicativo de transporte?",
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
  sessionContext: document.querySelector("#session-context"),
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
  traceContext: document.querySelector("#trace-context"),
  traceGrid: document.querySelector("#trace-grid"),
  executionMetrics: document.querySelector("#execution-metrics"),
  topKPanel: document.querySelector("#top-k-panel"),
  topKList: document.querySelector("#top-k-list"),
  improvementList: document.querySelector("#improvement-list"),
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
    return await fetch(`${API_BASE_URL}${path}`, { ...options, headers, signal: controller.signal });
  } finally {
    window.clearTimeout(timeout);
  }
}

async function checkOperations() {
  const dot = elements.systemStatus.querySelector(".status-dot");
  const label = elements.systemStatus.querySelector("span:last-child");
  dot.className = "status-dot checking";
  label.textContent = "Verificando API e dependências";
  try {
    const response = await api("/ready", {}, 4000);
    const data = await response.json();
    if (response.ok) {
      dot.className = "status-dot";
      label.textContent = "API disponível";
    } else {
      const unavailable = Object.entries(data.dependencies || {}).filter(([, ready]) => !ready).map(([name]) => name).join(" e ");
      dot.className = "status-dot down";
      label.textContent = `Dependências indisponíveis: ${unavailable || "verifique a API"}`;
    }
  } catch {
    dot.className = "status-dot down";
    label.textContent = "API indisponível";
  }
}

function trackInteraction(event) {
  if (!state.token) return;
  api("/v1/telemetry", { method: "POST", body: JSON.stringify({ event }) }, 5000).catch(() => {});
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
    if (!response.ok) throw new Error("Não foi possível acessar este perfil agora.");
    const data = await response.json();
    state.token = data.access_token;
    state.identity = identity;
    state.context = data.context;
    showWorkspace();
    trackInteraction("login_completed");
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
  elements.sessionContext.textContent = state.context.tenant_id;
  setHidden(elements.loginView, true);
  setHidden(elements.workspace, false);
  setHidden(elements.logoutButton, false);
  elements.question.focus();
}

function logout() {
  trackInteraction("logout_completed");
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
  const steps = ["Entendendo sua dúvida...", "Procurando nos documentos da empresa...", "Conferindo as informações encontradas...", "Preparando uma resposta clara..."];
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
  trackInteraction("question_submitted");
  try {
    const response = await api("/v1/ask", { method: "POST", body: JSON.stringify({ question }) });
    const data = await response.json();
    if (!response.ok) {
      handleApiError(response.status, data.detail);
      return;
    }
    renderResponse(data);
  } catch (error) {
    // Registra a causa no console para investigar falhas sem expor detalhes técnicos ao viajante.
    console.error("Falha ao buscar ou exibir a resposta", error);
    if (error.name === "AbortError") {
      showState("warning", "A resposta está demorando mais que o normal", "Aguarde alguns segundos e tente novamente. O assistente pode estar iniciando.");
    } else {
      showState("error", "Não conseguimos conectar ao assistente", "Confira se os serviços estão ligados e tente novamente.");
    }
  } finally {
    stopLoading(loadingInterval);
  }
}

function handleApiError(status, detail) {
  if (status === 400) {
    showState("warning", "Não podemos responder a esse pedido", detail || "Tente escrever apenas uma dúvida sobre viagens ou despesas da empresa.");
  } else if (status === 401) {
    showState("error", "Sessão expirada", "Escolha novamente uma empresa fictícia para continuar.");
    window.setTimeout(logout, 1600);
  } else if (status === 503) {
    showState("error", "Assistente temporariamente indisponível", "Aguarde um momento e tente novamente. Se o problema continuar, procure o suporte.");
    checkOperations();
  } else {
    showState("error", "Não conseguimos concluir a busca", detail || "Tente escrever a pergunta de outra forma.");
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
  trackInteraction("answer_displayed");
  if (data.generation.status === "no_evidence" || !(data.sources || []).length) {
    showState("info", "Não encontramos essa informação", "Tente dar mais detalhes ou procure a equipe responsável por viagens da sua empresa.");
  } else if (data.generation.status === "degraded") {
    showState("warning", "Precisa de uma confirmação", "Encontramos uma regra relacionada, mas o assistente não conseguiu interpretá-la com segurança. Confira a fonte ou fale com a equipe responsável.");
  }
  elements.responseCard.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderConfidence(confidence) {
  const labels = { high: "Boa correspondência", medium: "Correspondência parcial", low: "Confira com sua empresa" };
  elements.confidenceBadge.textContent = labels[confidence] || "Correspondência não informada";
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
    meta.textContent = `${source.section} · versão ${source.version.replace("v", "")}`;
    content.append(title, meta);
    const score = document.createElement("span");
    score.className = "source-score";
    score.textContent = `${Math.round(Number(source.score) * 100)}% relevante`;
    card.append(accent, content, score);
    elements.sourcesList.append(card);
  });
}

function renderTrace(data) {
  elements.traceGrid.replaceChildren();
  const timings = data.trace?.timings_ms || { total: data.latency_ms };
  const preferred = ["ollama_embedding", "retrieval", "reranking", "ollama_generation", "total"];
  const labels = {
    ollama_embedding: "Embedding",
    retrieval: "Retrieval híbrido",
    reranking: "Re-ranking",
    ollama_generation: "LLM",
    total: "End-to-end",
  };
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
  renderExecutionMetrics(data.trace || {});
  renderTopK(data.trace?.documents || []);
  renderImprovementSuggestions(data.trace?.improvement_suggestions || []);
  const sourceCount = (data.sources || []).length;
  elements.traceContext.textContent = sourceCount
    ? `Consultamos ${sourceCount} ${sourceCount === 1 ? "fonte autorizada" : "fontes autorizadas"} da sua empresa e conferimos a relevância antes de responder.`
    : "Não encontramos uma fonte autorizada suficiente para responder com segurança.";
  elements.traceSummary.textContent = `${Number(timings.total || data.latency_ms).toFixed(0)} ms`;
  elements.requestId.textContent = data.request_id;
}

function renderExecutionMetrics(trace) {
  const top1 = trace.documents?.[0]?.score || 0;
  const metrics = [
    ["Custo estimado", `US$ ${Number(trace.estimated_local_cost_usd || 0).toFixed(4)}`, "Ollama local"],
    ["Tokens de saída", String(trace.estimated_output_tokens || 0), "estimativa por palavras"],
    ["Top-1 score", top1.toFixed(4), "primeiro chunk após o re-ranking"],
  ];
  elements.executionMetrics.replaceChildren();
  metrics.forEach(([label, value, description]) => {
    const item = document.createElement("div");
    item.className = "execution-metric";
    const metricLabel = document.createElement("span");
    metricLabel.textContent = label;
    const metricValue = document.createElement("strong");
    metricValue.textContent = value;
    const metricDescription = document.createElement("small");
    metricDescription.textContent = description;
    item.append(metricLabel, metricValue, metricDescription);
    elements.executionMetrics.append(item);
  });
}

function renderTopK(chunks) {
  elements.topKList.replaceChildren();
  setHidden(elements.topKPanel, chunks.length === 0);
  chunks.forEach((chunk, index) => {
    const item = document.createElement("div");
    item.className = "top-k-item";
    const identifier = document.createElement("code");
    identifier.textContent = `#${index + 1} · ${chunk.document_id} · ${chunk.chunk_id}`;
    const metadata = document.createElement("span");
    metadata.textContent = `${chunk.section || "Seção não informada"} · ${chunk.version}`;
    const score = document.createElement("strong");
    score.textContent = chunk.score.toFixed(4);
    item.append(identifier, metadata, score);
    elements.topKList.append(item);
  });
}

function renderImprovementSuggestions(suggestions) {
  elements.improvementList.replaceChildren();
  const items = suggestions.length
    ? suggestions
    : ["Monitorar feedback e métricas do golden dataset antes da próxima alteração."];
  items.forEach((suggestion) => {
    const item = document.createElement("li");
    item.textContent = suggestion;
    elements.improvementList.append(item);
  });
}

async function sendFeedback(rating) {
  if (!state.requestId) return;
  elements.feedbackRow.querySelectorAll("button").forEach((button) => { button.disabled = true; });
  try {
    const response = await api("/v1/feedback", { method: "POST", body: JSON.stringify({ request_id: state.requestId, rating }) }, 10000);
    if (!response.ok) throw new Error();
    elements.feedbackConfirmation.textContent = rating === "positive" ? "Obrigado pela avaliação!" : "Obrigado. Vamos usar sua avaliação para melhorar.";
    setHidden(elements.feedbackConfirmation, false);
    setHidden(elements.feedbackRow, true);
    trackInteraction(rating === "positive" ? "feedback_positive" : "feedback_negative");
  } catch {
    showState("error", "Não foi possível enviar sua avaliação", "A resposta continua disponível. Tente novamente em alguns instantes.");
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
    button.addEventListener("click", () => { elements.question.value = question; updateCharacterCount(); elements.question.focus(); trackInteraction("quick_question_selected"); });
    elements.examples.append(button);
  });
}

document.querySelectorAll(".identity-card").forEach((button) => button.addEventListener("click", () => login(button.dataset.identity)));
elements.logoutButton.addEventListener("click", logout);
elements.askForm.addEventListener("submit", askQuestion);
elements.question.addEventListener("input", updateCharacterCount);
elements.feedbackRow.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => sendFeedback(button.dataset.rating)));
elements.copyRequest.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(state.requestId || "");
    trackInteraction("request_id_copied");
    elements.copyRequest.textContent = "Copiado";
    window.setTimeout(() => { elements.copyRequest.textContent = "Copiar"; }, 1200);
  } catch (error) {
    console.error("Falha ao copiar request_id", error);
    elements.copyRequest.textContent = "Não foi possível copiar";
    window.setTimeout(() => { elements.copyRequest.textContent = "Copiar"; }, 1600);
  }
});

buildExamples();
if (API_BASE_URL) {
  const swaggerLink = document.querySelector("#swagger-link");
  if (swaggerLink) swaggerLink.href = `${API_BASE_URL}/docs`;
  const metricsLink = document.querySelector("#metrics-link");
  if (metricsLink) metricsLink.href = `${API_BASE_URL}/metrics/ui`;
}
checkOperations();
window.setInterval(checkOperations, 30000);
