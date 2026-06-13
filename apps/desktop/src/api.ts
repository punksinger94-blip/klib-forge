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
    retrieval_policy: {
      top_k: number;
      require_citations: boolean;
      use_hybrid_search: boolean;
      vector_adapter: "local" | "chroma" | "qdrant";
      qdrant_url?: string;
      qdrant_collection?: string;
    };
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
  metadata_json?: string;
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

export type Capabilities = {
  version: string;
  vector_adapters: {
    local: boolean;
    chroma: boolean;
    qdrant: boolean;
  };
};

export type Suggestion = {
  id: string;
  kind: "glossary" | "rule" | "example" | "eval";
  title: string;
  payload: Record<string, unknown>;
  reason: string;
  confidence: number;
};

export type ModelProfile = {
  id: string;
  name: string;
  provider: string;
  model: string;
  base_url: string | null;
  api_key_env: string | null;
  options: Record<string, unknown>;
};

export type ModelRun = {
  id: string;
  provider: string;
  model: string;
  input: string;
  output: string;
  prompt: string;
  retrieved_context: SearchResult[];
  latency_ms: number;
  created_at: string;
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
  capabilities: () => request<Capabilities>("/capabilities"),
  libraries: () => request<Library[]>("/libraries"),
  library: (id: string) => request<LibraryDetail>(`/libraries/${id}`),
  updateLibrary: (id: string, data: Record<string, unknown>) =>
    request<LibraryDetail["manifest"]>(`/libraries/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteLibrary: (id: string, removeFiles = true) =>
    request<void>(`/libraries/${id}?remove_files=${removeFiles}`, { method: "DELETE" }),
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
  updateSource: (id: string, sourceId: string, data: { title?: string; trust_level?: string }) =>
    request<Source>(`/libraries/${id}/sources/${sourceId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteSource: (id: string, sourceId: string) =>
    request<void>(`/libraries/${id}/sources/${sourceId}`, { method: "DELETE" }),
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
  deleteGlossary: (id: string, entryId: string) =>
    request<void>(`/libraries/${id}/glossary/${entryId}`, { method: "DELETE" }),
  rules: (id: string) =>
    request<Array<{ id: string; title: string; body: string; priority: number }>>(
      `/libraries/${id}/rules`,
    ),
  addRule: (id: string, data: { title: string; body: string; priority: number }) =>
    request(`/libraries/${id}/rules`, { method: "POST", body: JSON.stringify(data) }),
  updateRule: (id: string, ruleId: string, data: { title: string; body: string; priority: number }) =>
    request(`/libraries/${id}/rules/${ruleId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  deleteRule: (id: string, ruleId: string) =>
    request<void>(`/libraries/${id}/rules/${ruleId}`, { method: "DELETE" }),
  examples: (id: string) =>
    request<Array<{ id: string; input: string; output: string; task: string; mode: string }>>(
      `/libraries/${id}/examples`,
    ),
  addExample: (
    id: string,
    data: { input: string; output: string; task: string; mode: string },
  ) => request(`/libraries/${id}/examples`, { method: "POST", body: JSON.stringify(data) }),
  updateExample: (id: string, exampleId: string, data: Record<string, unknown>) =>
    request(`/libraries/${id}/examples/${exampleId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteExample: (id: string, exampleId: string) =>
    request<void>(`/libraries/${id}/examples/${exampleId}`, { method: "DELETE" }),
  evals: (id: string) =>
    request<Array<{ id: string; name: string; task: string; input: string; checks: Record<string, unknown> }>>(
      `/libraries/${id}/evals`,
    ),
  saveEval: (id: string, data: Record<string, unknown>) =>
    request(`/libraries/${id}/evals`, { method: "POST", body: JSON.stringify(data) }),
  deleteEval: (id: string, evalId: string) =>
    request<void>(`/libraries/${id}/evals/${evalId}`, { method: "DELETE" }),
  ask: (
    id: string,
    data: { input: string; provider: string; model: string; mode?: string; base_url?: string },
  ) =>
    request<AskResult>(`/libraries/${id}/ask`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  correct: (
    id: string,
    data: {
      input: string;
      bad_output: string;
      corrected_output: string;
      lesson: string;
      create_eval: boolean;
    },
  ) => request(`/libraries/${id}/correct`, {
    method: "POST",
    body: JSON.stringify(data),
  }),
  evaluate: (id: string, data: { provider: string; model: string; base_url?: string }) =>
    request<Array<{ eval_id: string; score: number; output: string }>>(
      `/libraries/${id}/eval`,
      { method: "POST", body: JSON.stringify(data) },
    ),
  arena: (
    id: string,
    models: Array<{ name: string; provider: string; model: string; base_url?: string }>,
  ) => request<{ models: Array<{ name: string; average: number; results: unknown[] }> }>(
    `/libraries/${id}/arena`,
    { method: "POST", body: JSON.stringify({ models }) },
  ),
  suggestions: (id: string) => request<Suggestion[]>(`/libraries/${id}/suggestions`),
  applySuggestion: (id: string, suggestion: Suggestion) =>
    request(`/libraries/${id}/suggestions/apply`, {
      method: "POST",
      body: JSON.stringify({ kind: suggestion.kind, payload: suggestion.payload }),
    }),
  corrections: (id: string) =>
    request<Array<Record<string, string>>>(`/libraries/${id}/corrections`),
  reviewCorrection: (id: string, correctionId: string, status: string) =>
    request(`/libraries/${id}/corrections/${correctionId}/review`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
  runs: (id: string) => request<ModelRun[]>(`/libraries/${id}/runs`),
  trust: (id: string) =>
    request<Array<{ source_id: string; title: string; trust_level: string; risk_score: number; findings: Array<{ severity: string; message: string; excerpt: string }> }>>(
      `/libraries/${id}/trust`,
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
  importLibrary: (file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<LibraryDetail["manifest"]>("/libraries/import", {
      method: "POST",
      body: data,
    });
  },
  profiles: () => request<ModelProfile[]>("/model-profiles"),
  saveProfile: (profile: Omit<ModelProfile, "id"> & { id?: string }) =>
    request<ModelProfile>("/model-profiles", {
      method: "POST",
      body: JSON.stringify(profile),
    }),
  deleteProfile: (id: string) =>
    request<void>(`/model-profiles/${id}`, { method: "DELETE" }),
};
