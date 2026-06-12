import { invoke, isTauri } from "@tauri-apps/api/core";

export type Library = {
  id: string;
  name: string;
  description: string;
  domain: string;
  version: string;
  path: string;
  updated_at: string;
};

export type LibraryDetail = {
  manifest: {
    id: string;
    name: string;
    description: string;
    domain: string;
    version: string;
    default_mode: string;
    retrieval_policy: { top_k: number; require_citations: boolean };
    model_policy: {
      default_provider: string;
      default_model: string;
      allow_online_models: boolean;
    };
  };
  path: string;
  source_count: number;
  glossary_count: number;
  rule_count: number;
  eval_count: number;
};

export type Source = {
  id: string;
  title: string;
  type: string;
  trust_level: string;
  path: string;
};

export type SearchResult = {
  chunk_id: string;
  source_title: string;
  text: string;
  score: number;
};

export type AskResult = {
  output: string;
  provider: string;
  model: string;
  latency_ms: number;
  retrieved_context: SearchResult[];
  prompt_preview: string;
};

const defaultBase = "http://127.0.0.1:8000";
let apiBase = localStorage.getItem("klib-api-base") || defaultBase;

export type RuntimeInfo = {
  baseUrl: string;
  managed: boolean;
  backendPid: number | null;
  startupError: string | null;
};

export function getApiBase(): string {
  return apiBase;
}

export function setApiBase(value: string, persist = true): void {
  apiBase = value.replace(/\/+$/, "");
  if (persist) {
    localStorage.setItem("klib-api-base", apiBase);
  }
}

export async function initializeRuntime(): Promise<RuntimeInfo | null> {
  if (!isTauri()) return null;
  const runtime = await invoke<RuntimeInfo>("runtime_info");
  setApiBase(runtime.baseUrl, false);
  return runtime;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData) && init?.body) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${getApiBase()}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || `Request failed with ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),
  libraries: () => request<Library[]>("/libraries"),
  library: (id: string) => request<LibraryDetail>(`/libraries/${id}`),
  createLibrary: (data: { name: string; id?: string; domain: string; description: string }) =>
    request<{ manifest: LibraryDetail["manifest"]; path: string }>("/libraries", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  installExample: () =>
    request<{ created: boolean; library: LibraryDetail }>(
      "/examples/arabic-technical-translation/install",
      { method: "POST" },
    ),
  sources: (id: string) => request<Source[]>(`/libraries/${id}/sources`),
  uploadSource: (id: string, file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<Source[]>(`/libraries/${id}/sources`, { method: "POST", body: data });
  },
  compile: (id: string) =>
    request<{ sources: number; chunks: number; keywords: string[]; snapshot_id: string }>(
      `/libraries/${id}/compile`,
      { method: "POST" },
    ),
  glossary: (id: string) =>
    request<Array<{ id: string; source_term: string; target_term: string; notes: string }>>(
      `/libraries/${id}/glossary`,
    ),
  addGlossary: (id: string, data: { source_term: string; target_term: string; notes: string }) =>
    request(`/libraries/${id}/glossary`, { method: "POST", body: JSON.stringify(data) }),
  rules: (id: string) =>
    request<Array<{ id: string; title: string; body: string; priority: number }>>(
      `/libraries/${id}/rules`,
    ),
  addRule: (id: string, data: { title: string; body: string; priority: number }) =>
    request(`/libraries/${id}/rules`, { method: "POST", body: JSON.stringify(data) }),
  ask: (
    id: string,
    data: { input: string; provider: string; model: string; mode?: string; base_url?: string },
  ) =>
    request<AskResult>(`/libraries/${id}/ask`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  evaluate: (id: string, data: { provider: string; model: string; base_url?: string }) =>
    request<Array<{ eval_id: string; score: number; output: string }>>(
      `/libraries/${id}/eval`,
      { method: "POST", body: JSON.stringify(data) },
    ),
  diff: (id: string) =>
    request<Record<string, string | string[] | null>>(`/libraries/${id}/diff`, {
      method: "POST",
    }),
  exportLibrary: async (id: string) => {
    const response = await fetch(`${getApiBase()}/libraries/${id}/export`, {
      method: "POST",
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(body.detail || `Export failed with ${response.status}`);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/i);
    const filename = match?.[1] || `${id}.klib`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    return filename;
  },
};
