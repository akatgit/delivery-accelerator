// API client for the ASDA backend (ARCHITECTURE_v2.0.md section 10.1).
// Every function here maps 1:1 to one endpoint in that section's table.

const BASE = "/api/sessions";

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: options.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // response wasn't JSON; fall back to statusText
    }
    throw new Error(`${response.status} ${detail}`);
  }
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();
  return response;
}

// --- Sessions ---

export function createSession(projectName, projectDescription) {
  return request(BASE, {
    method: "POST",
    body: JSON.stringify({ project_name: projectName, project_description: projectDescription }),
  });
}

export function listSessions() {
  return request(BASE);
}

export function getSession(sessionId) {
  return request(`${BASE}/${sessionId}`);
}

// --- Documents & standards ---

export function uploadDocument(sessionId, documentType, file) {
  const form = new FormData();
  form.append("document_type", documentType);
  form.append("file", file);
  return request(`${BASE}/${sessionId}/documents`, { method: "POST", body: form });
}

export function uploadStandard(sessionId, file) {
  const form = new FormData();
  form.append("file", file);
  return request(`${BASE}/${sessionId}/standards`, { method: "POST", body: form });
}

export function reuseStandards(sessionId, sourceId) {
  return request(`${BASE}/${sessionId}/standards/reuse/${sourceId}`, { method: "POST" });
}

export function getStandardsCoverage(sessionId) {
  return request(`${BASE}/${sessionId}/standards/coverage`);
}

export function getConflicts(sessionId) {
  return request(`${BASE}/${sessionId}/standards/conflicts`);
}

export function resolveConflicts(sessionId, resolutions) {
  return request(`${BASE}/${sessionId}/standards/conflicts/resolve`, {
    method: "POST",
    body: JSON.stringify({ resolutions }),
  });
}

// --- Pipeline ---

export function startPipeline(sessionId) {
  return request(`${BASE}/${sessionId}/start`, { method: "POST" });
}

export function getStatus(sessionId) {
  return request(`${BASE}/${sessionId}/status`);
}

export function getExtraction(sessionId) {
  return request(`${BASE}/${sessionId}/extraction`);
}

export function confirmExtraction(sessionId, confirmed = true) {
  return request(`${BASE}/${sessionId}/extraction/confirm`, {
    method: "POST",
    body: JSON.stringify({ confirmed }),
  });
}

export function getReview(sessionId) {
  return request(`${BASE}/${sessionId}/review`);
}

export function getReviewQuality(sessionId) {
  return request(`${BASE}/${sessionId}/review/quality`);
}

export function approve(sessionId, decision, extra = {}) {
  return request(`${BASE}/${sessionId}/approve`, {
    method: "POST",
    body: JSON.stringify({ decision, overrides: [], contradiction_resolutions: [], justification: null, ...extra }),
  });
}

export function reupload(sessionId, documents) {
  return request(`${BASE}/${sessionId}/reupload`, {
    method: "POST",
    body: JSON.stringify({ documents }),
  });
}

export function retryDomain(sessionId, domain) {
  return request(`${BASE}/${sessionId}/retry/${domain}`, { method: "POST" });
}

export function getArtifacts(sessionId) {
  return request(`${BASE}/${sessionId}/artifacts`);
}

export function getScaffolding(sessionId) {
  return request(`${BASE}/${sessionId}/scaffolding`);
}

export function getScaffoldingDownloadUrl(sessionId) {
  return `${BASE}/${sessionId}/scaffolding?download=true`;
}

export function getDecisionLog(sessionId) {
  return request(`${BASE}/${sessionId}/decision-log`);
}

export function getTrace(sessionId) {
  return request(`${BASE}/${sessionId}/trace`);
}

// --- WebSocket ---

export function streamUrl(sessionId) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${BASE}/${sessionId}/stream`;
}
