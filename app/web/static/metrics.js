"use strict";

// O painel lê o endpoint de exposição do Prometheus e organiza os dados por categoria.
const API_BASE_URL = window.location.protocol === "file:" ? "http://localhost:8000" : "";
const REFRESH_INTERVAL_MS = 5000;

const elements = {
  status: document.querySelector("#live-status"),
  refreshButton: document.querySelector("#refresh-button"),
  lastUpdated: document.querySelector("#last-updated"),
  error: document.querySelector("#dash-error"),
  kpiGrid: document.querySelector("#kpi-grid"),
  latencyList: document.querySelector("#latency-list"),
  statusBars: document.querySelector("#status-bars"),
  confidenceBars: document.querySelector("#confidence-bars"),
  indicatorGrid: document.querySelector("#indicator-grid"),
  eventGrid: document.querySelector("#event-grid"),
  sessionList: document.querySelector("#session-list"),
  responseHistory: document.querySelector("#response-history"),
};

const latencyOrder = ["http_total", "ollama_embedding", "retrieval", "reranking", "ollama_generation", "total"];
const latencyLabels = {
  http_total: "HTTP geral",
  ollama_embedding: "Embedding",
  retrieval: "Retrieval",
  reranking: "Re-ranking",
  ollama_generation: "Geração LLM",
  total: "Resposta end-to-end",
};

const statusConfig = [
  { key: "answers_status_generated_total", label: "Geradas pelo modelo", tone: "good" },
  { key: "answers_status_degraded_total", label: "Fallback controlado", tone: "warn" },
  { key: "answers_status_no_evidence_total", label: "Sem evidência", tone: "danger" },
];

const confidenceConfig = [
  { key: "answers_confidence_high_total", label: "Confiança alta", tone: "good" },
  { key: "answers_confidence_medium_total", label: "Confiança média", tone: "warn" },
  { key: "answers_confidence_low_total", label: "Confiança baixa", tone: "danger" },
];

const indicatorConfig = [
  { key: "retrieval_top1_score", label: "Top-1 score", note: "primeiro chunk após o re-ranking" },
  { key: "retrieval_top1_evidence_eligible", label: "Top-1 elegível", note: "acima do limiar de evidência" },
  { key: "sources_per_answer", label: "Fontes por resposta", note: "média por resposta" },
  { key: "estimated_output_tokens", label: "Tokens por resposta", note: "estimativa por palavras" },
  { key: "estimated_local_cost_usd", label: "Custo por resposta", note: "Ollama executado localmente" },
];

const eventLabels = {
  login_completed: "Logins",
  logout_completed: "Logouts",
  question_submitted: "Perguntas enviadas",
  answer_displayed: "Respostas exibidas",
  quick_question_selected: "Exemplos usados",
  feedback_positive: "Feedback positivo",
  feedback_negative: "Feedback negativo",
  request_id_copied: "Protocolos copiados",
};

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function setHidden(element, hidden) {
  element.classList.toggle("hidden", hidden);
}

function setStatus(state, label) {
  const dot = elements.status.querySelector(".status-dot");
  dot.className = `status-dot ${state}`;
  elements.status.querySelector("span:last-child").textContent = label;
}

function formatNumber(value) {
  return Number(value).toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

function formatDecimal(value, digits = 3) {
  return Number(value).toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function formatMs(value) {
  const number = Number(value);
  if (number >= 1000) return `${formatDecimal(number / 1000, 1)} s`;
  return `${formatDecimal(number, 1)} ms`;
}

function parseMetrics(text) {
  const metrics = {};
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const separator = line.indexOf(" ");
    if (separator === -1) continue;
    metrics[line.slice(0, separator)] = parseFloat(line.slice(separator + 1));
  }
  return metrics;
}

function classify(metrics) {
  const counters = {};
  const latencies = {};
  const indicators = {};
  for (const name of Object.keys(metrics)) {
    const latencyMatch = name.match(/^(.+)_ms_(average|count|total)$/);
    if (latencyMatch) {
      const component = latencyMatch[1];
      latencies[component] = latencies[component] || {};
      latencies[component][latencyMatch[2]] = metrics[name];
      continue;
    }
    const indicatorMatch = name.match(/^(.+)_(average|count|total)$/);
    if (indicatorMatch) {
      const indicator = indicatorMatch[1];
      indicators[indicator] = indicators[indicator] || {};
      indicators[indicator][indicatorMatch[2]] = metrics[name];
      continue;
    }
    counters[name] = metrics[name];
  }
  return { counters, latencies, indicators };
}

function renderKpis(counters) {
  elements.kpiGrid.replaceChildren();
  const value = (key) => counters[key] || 0;
  const requests = value("requests_total");
  const errorRate = requests ? (value("errors_total") / requests) * 100 : 0;
  const cards = [
    { key: "requests_total", label: "Requisições", sub: "recebidas pela API", tone: "" },
    { key: "answers_total", label: "Respostas", sub: "entregues ao usuário", tone: "good" },
    { key: "errors_total", label: "Erros", sub: "status ≥ 400", tone: errorRate > 0 ? "danger" : "good" },
    { key: "fallbacks_total", label: "Fallbacks", sub: "respostas controladas", tone: value("fallbacks_total") > 0 ? "warn" : "good" },
    { key: "retries_total", label: "Retries", sub: "tentativas extras", tone: value("retries_total") > 0 ? "warn" : "good" },
  ];
  cards.forEach((item) => {
    const card = makeElement("article", `kpi-card ${item.tone}`.trim());
    card.append(
      makeElement("span", "kpi-label", item.label),
      makeElement("strong", "kpi-value", formatNumber(value(item.key))),
      makeElement("span", "kpi-sub", item.sub),
    );
    elements.kpiGrid.append(card);
  });
  const rate = makeElement("article", `kpi-card ${errorRate > 0 ? "danger" : "good"}`);
  rate.append(
    makeElement("span", "kpi-label", "Taxa de erro"),
    makeElement("strong", "kpi-value", `${formatDecimal(errorRate, 1)}%`),
    makeElement("span", "kpi-sub", "erros por requisição"),
  );
  elements.kpiGrid.append(rate);
}

function renderLatencies(latencies) {
  elements.latencyList.replaceChildren();
  const available = latencyOrder.filter((name) => latencies[name]);
  if (!available.length) {
    elements.latencyList.append(makeElement("p", "empty-note", "Nenhuma etapa medida ainda."));
    return;
  }
  const maxAverage = Math.max(...available.map((name) => latencies[name].average));
  available.forEach((name) => {
    const data = latencies[name];
    const row = makeElement("div", "latency-row");
    const nameBox = makeElement("div");
    nameBox.append(
      makeElement("span", "latency-name", latencyLabels[name] || name),
      makeElement("span", "latency-count", `${formatNumber(data.count)} ${data.count === 1 ? "medição" : "medições"}`),
    );
    const track = makeElement("div", "latency-track");
    const fill = makeElement("div", "latency-fill");
    fill.style.width = `${Math.max(2, (data.average / maxAverage) * 100)}%`;
    track.append(fill);
    row.append(nameBox, track, makeElement("strong", "latency-value", formatMs(data.average)));
    elements.latencyList.append(row);
  });
}

function renderBars(container, config, counters) {
  container.replaceChildren();
  const total = config.reduce((sum, item) => sum + (counters[item.key] || 0), 0);
  config.forEach((item) => {
    const count = counters[item.key] || 0;
    const row = makeElement("div", `quality-row ${item.tone}`);
    const labelBox = makeElement("div");
    labelBox.append(
      makeElement("span", "quality-label", item.label),
      makeElement("span", "latency-count", formatNumber(count)),
    );
    const track = makeElement("div", "quality-track");
    const fill = makeElement("div", "quality-fill");
    fill.style.width = total ? `${Math.max(2, (count / total) * 100)}%` : "0%";
    track.append(fill);
    const share = total ? `${formatDecimal((count / total) * 100, 1)}%` : "—";
    row.append(labelBox, track, makeElement("strong", "quality-value", share));
    container.append(row);
  });
}

function renderIndicators(indicators) {
  elements.indicatorGrid.replaceChildren();
  const present = indicatorConfig.filter((item) => indicators[item.key]);
  if (!present.length) {
    elements.indicatorGrid.append(makeElement("p", "empty-note", "Nenhum indicador medido ainda."));
    return;
  }
  present.forEach((item) => {
    const data = indicators[item.key];
    const value = item.key.endsWith("_score")
      ? formatDecimal(data.average, 4)
      : item.key.endsWith("_eligible")
        ? `${formatDecimal(data.average * 100, 1)}%`
        : item.key.endsWith("_usd")
          ? `US$ ${formatDecimal(data.average, 4)}`
          : item.key.endsWith("_tokens")
            ? formatNumber(data.average)
            : formatDecimal(data.average, 2);
    const card = makeElement("article", "indicator-card");
    card.append(
      makeElement("span", "indicator-label", item.label),
      makeElement("strong", "indicator-value", value),
      makeElement("span", "indicator-note", `${item.note} · ${formatNumber(data.count)} ${data.count === 1 ? "medição" : "medições"}`),
    );
    elements.indicatorGrid.append(card);
  });
}

function renderEvents(counters) {
  elements.eventGrid.replaceChildren();
  const events = Object.keys(counters)
    .filter((name) => name.startsWith("user_event_"))
    .map((name) => ({
      key: name.replace(/^user_event_/, "").replace(/_total$/, ""),
      value: counters[name],
    }))
    .sort((a, b) => b.value - a.value);
  if (!events.length) {
    elements.eventGrid.append(makeElement("p", "empty-note", "Nenhum evento registrado ainda."));
    return;
  }
  events.forEach((event) => {
    const card = makeElement("article", "event-card");
    card.append(
      makeElement("span", null, eventLabels[event.key] || event.key),
      makeElement("strong", null, formatNumber(event.value)),
    );
    elements.eventGrid.append(card);
  });
}

function renderHistory(sessions, responses) {
  elements.sessionList.replaceChildren();
  elements.responseHistory.replaceChildren();
  if (!sessions.length) {
    elements.sessionList.append(makeElement("p", "empty-note", "Nenhuma sessão registrada ainda."));
  } else {
    sessions.forEach((session, index) => {
      const button = makeElement("button", `session-card ${index === 0 ? "selected" : ""}`.trim());
      button.type = "button";
      button.dataset.sessionId = session.session_id;
      button.append(
        makeElement("strong", null, session.tenant_id),
        makeElement("span", null, `${formatNumber(session.responses)} respostas · ${formatMs(session.average_latency_ms)} média`),
        makeElement("small", null, new Date(session.last_activity).toLocaleString("pt-BR")),
      );
      button.addEventListener("click", () => {
        document.querySelectorAll(".session-card").forEach((item) => item.classList.remove("selected"));
        button.classList.add("selected");
        renderResponseRows(responses.filter((item) => item.session_id === session.session_id));
      });
      elements.sessionList.append(button);
    });
  }
  renderResponseRows(sessions.length ? responses.filter((item) => item.session_id === sessions[0].session_id) : responses);
}

function renderResponseRows(responses) {
  elements.responseHistory.replaceChildren();
  if (!responses.length) {
    elements.responseHistory.append(makeElement("p", "empty-note", "Nenhuma resposta registrada nesta sessão."));
    return;
  }
  responses.forEach((item) => {
    const row = makeElement("article", "response-history-row");
    const title = makeElement("div", "response-history-main");
    title.append(
      makeElement("strong", null, item.request_id),
      makeElement("span", null, new Date(item.created_at).toLocaleString("pt-BR")),
    );
    const metrics = makeElement("div", "response-history-metrics");
    metrics.append(
      makeElement("b", null, formatMs(item.latency_ms)),
      makeElement("span", null, `${item.sources_count} fontes`),
      makeElement("span", null, `${item.output_tokens} tokens`),
      makeElement("span", `history-status ${item.status}`, item.status),
    );
    row.append(title, metrics);
    elements.responseHistory.append(row);
  });
}

function renderAll(counters, latencies, indicators) {
  renderKpis(counters);
  renderLatencies(latencies);
  renderBars(elements.statusBars, statusConfig, counters);
  renderBars(elements.confidenceBars, confidenceConfig, counters);
  renderIndicators(indicators);
  renderEvents(counters);
  elements.lastUpdated.textContent = `atualizado às ${new Date().toLocaleTimeString("pt-BR")}`;
}

async function loadMetrics() {
  const results = await Promise.allSettled([
    fetch(`${API_BASE_URL}/metrics`),
    fetch(`${API_BASE_URL}/observability/sessions`),
    fetch(`${API_BASE_URL}/observability/responses`),
  ]);
  const [metricsResult, sessionsResult, responsesResult] = results;
  const metricsOk = metricsResult.status === "fulfilled" && metricsResult.value.ok;
  const historyOk = sessionsResult.status === "fulfilled" && sessionsResult.value.ok
    && responsesResult.status === "fulfilled" && responsesResult.value.ok;
  if (metricsOk) {
    const text = await metricsResult.value.text();
    const { counters, latencies, indicators } = classify(parseMetrics(text));
    renderAll(counters, latencies, indicators);
  }
  if (historyOk) {
    renderHistory(await sessionsResult.value.json(), await responsesResult.value.json());
  }
  if (metricsOk && historyOk) {
    setHidden(elements.error, true);
    setStatus("", "Ao vivo");
  } else if (metricsOk || historyOk) {
    setStatus("checking", "Dados parciais");
    elements.error.textContent = metricsOk
      ? "As métricas atuais estão disponíveis, mas o histórico não pôde ser atualizado."
      : "O histórico está disponível, mas as métricas atuais não puderam ser atualizadas.";
    setHidden(elements.error, false);
  } else {
    setStatus("down", "API indisponível");
    elements.error.textContent = "Não foi possível carregar a observabilidade agora. Confira se a API está ligada e tente novamente.";
    setHidden(elements.error, false);
  }
}

elements.refreshButton.addEventListener("click", loadMetrics);
loadMetrics();
window.setInterval(loadMetrics, REFRESH_INTERVAL_MS);
