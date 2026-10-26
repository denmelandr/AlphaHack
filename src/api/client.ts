const BASE = (import.meta as any).env?.VITE_API_URL || "/api";

export function getToken(): string | null {
  return sessionStorage.getItem("alfa-api-token");
}
export function setToken(t: string) {
  sessionStorage.setItem("alfa-api-token", t);
}
export function clearToken() {
  sessionStorage.removeItem("alfa-api-token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (options.body instanceof FormData) delete headers["Content-Type"];
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let res: Response;
  try { res = await fetch(`${BASE}${path}`, { ...options, headers, signal: options.signal ?? AbortSignal.timeout(30000) }); }
  catch { throw new Error('Сервер недоступен. Проверьте запуск бэкенда и повторите запрос.'); }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    if (res.status === 401) { clearToken(); window.dispatchEvent(new Event('alfa-session-expired')); }
    const detail = body.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: any) => d.msg).join('; ') : `Ошибка ${res.status}`);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (payload: any) => request<{ access_token: string }>('/auth/register', { method: 'POST', body: JSON.stringify(payload) }),
  company: () => request<any>('/auth/company'),
  me: () => request<any>("/auth/me"),
  products: () => request<any[]>("/products"),
  applications: () => request<any[]>("/applications"),
  application: (id: number) => request<any>(`/applications/${id}`),
  createApplication: (payload: any) =>
    request<any>("/applications", { method: "POST", body: JSON.stringify(payload) }),
  updateApplication: (id: number, payload: any) =>
    request<any>(`/applications/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  documents: (id: number) => request<any[]>(`/applications/${id}/documents`),
  uploadFile: (id: number, doc_type: string, file: File) => { const body = new FormData(); body.append('doc_type',doc_type); body.append('file',file); return request<any[]>(`/applications/${id}/documents/file`,{method:'POST',body}); },
  downloadFile: async (id: number, type: string, filename: string) => { const response = await fetch(`${BASE}/applications/${id}/documents/${type}/file`, {headers:{Authorization:`Bearer ${getToken()}`}}); if(!response.ok)throw new Error('Не удалось скачать файл'); const url = URL.createObjectURL(await response.blob()); const a=document.createElement('a');a.href=url;a.download=filename;a.click();URL.revokeObjectURL(url); },
  uploadDoc: (id: number, doc_type: string, filename: string) =>
    request<any[]>(`/applications/${id}/documents`, {
      method: "POST",
      body: JSON.stringify({ doc_type, filename }),
    }),
  deleteDoc: (id: number, doc_type: string) =>
    request<any[]>(`/applications/${id}/documents/${doc_type}`, { method: "DELETE" }),
  readiness: (id: number) => request<any>(`/applications/${id}/readiness`),
  calc: (payload: any) =>
    request<any>("/calc", { method: "POST", body: JSON.stringify(payload) }),
  recommend: (answers: any) =>
    request<any>("/recommend", { method: "POST", body: JSON.stringify({ answers }) }),
  policies: () => request<any[]>("/policies"),
  activePolicy: () => request<any>("/policies/active"),
  policyAudit: () => request<any[]>("/policies/audit"),
  policySimulate: (yaml_text: string, limit = 50) =>
    request<any>("/policies/simulate", {
      method: "POST",
      body: JSON.stringify({ yaml_text, limit }),
    }),
  createPolicy: (name: string, yaml_text: string) =>
    request<any>("/policies", { method: "POST", body: JSON.stringify({ name, yaml_text }) }),
  activatePolicy: (version: number) =>
    request<any>(`/policies/${version}/activate`, { method: "POST" }),
  earlyWarnings: () => request<any[]>("/portfolio/early-warnings"),
  portfolioMetrics: () => request<any>("/portfolio/metrics"),
  submit: (id: number) =>
    request<any>(`/applications/${id}/submit`, { method: "POST" }),
  accept: (id: number) =>
    request<any>(`/applications/${id}/accept`, { method: "POST" }),
  resubmit: (id: number) =>
    request<any>(`/applications/${id}/resubmit`, { method: "POST" }),
  saveConditions: (id: number, payload: any) => request<any>(`/applications/${id}/conditions`, { method: 'POST', body: JSON.stringify(payload) }),
  collaboration: (id: number) => request<any>(`/applications/${id}/collaboration`),
  updateCollaboration: (id: number, payload: any) => request<any>(`/applications/${id}/collaboration`, { method: 'POST', body: JSON.stringify(payload) }),
  simulate: (id: number, payload: any) =>
    request<any>(`/applications/${id}/simulate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  requestReview: (id: number, comment = "") =>
    request<any>(`/applications/${id}/review`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    }),
  copilot: (id: number) => request<any>(`/applications/${id}/copilot`),
  servicing: (id: number) => request<any>(`/applications/${id}/servicing`),
  applyServicing: (id: number, action: string) =>
    request<any>(`/applications/${id}/servicing/apply`, {
      method: "POST",
      body: JSON.stringify({ action }),
    }),
  servicingForecast: (id: number, payload: any) =>
    request<any>(`/applications/${id}/servicing/forecast`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  offers: (id: number) => request<any>(`/applications/${id}/offers`),
  configureAutopilot: (id: number, payload: any) =>
    request<any>(`/applications/${id}/servicing/autopilot`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  runAutopilot: (id: number) =>
    request<any>(`/applications/${id}/servicing/autopilot/run`, { method: "POST" }),
  transition: (id: number, event: string, comment = "") =>
    request<any>(`/applications/${id}/transition`, {
      method: "POST",
      body: JSON.stringify({ event, comment }),
    }),
};
