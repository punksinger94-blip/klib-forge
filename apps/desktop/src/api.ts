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
  medchem?: {
    available: boolean;
    engine: string | null;
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

export type ProviderInfo = {
  provider: string;
  name: string;
  transport: "mock" | "openai" | "anthropic";
  default_base_url: string | null;
  api_key_env: string | null;
  local: boolean;
  api_key_required: boolean;
  base_url_required: boolean;
};

export type BuiltinExample = {
  id: string;
  name: string;
  description: string;
  domain: string;
  source_count: number;
  eval_count: number;
  requires_extra?: string;
};

export type MedChemCompound = {
  compound_id: string;
  name: string;
  smiles: string;
  canonical_smiles: string;
  inchikey: string;
  formula: string;
  molecular_weight: number;
  logp: number;
  hbd: number;
  hba: number;
  tpsa: number;
  rotatable_bonds: number;
  ring_count: number;
  scaffold_smiles: string;
  undefined_stereocenters: string[];
  structural_alerts: Array<{
    name: string;
    filter_set: string;
    scope: string;
    reference: string;
  }>;
  descriptor_methods: Record<string, string>;
  provenance?: {
    compound_id: string;
    source_refs: string[];
    original_smiles: string;
    canonical_smiles: string;
    inchikey: string;
    imported_at: string;
    compiled_at: string;
    standardized: boolean;
    standardization_method: string;
    identity_method: string;
    descriptor_methods: Record<string, string>;
    status: string;
  };
  status: string;
};

export type MedChemDiagnostic = {
  severity: "error" | "warning";
  code: string;
  record_id: string;
  field: string;
  message: string;
};

export type MedChemDuplicateIdentityGroup = {
  inchikey: string;
  compound_ids: string[];
  names: string[];
  sources: string[];
  records: Array<{
    compound_id: string;
    name: string;
    source_database: string;
    source_url: string | null;
    source_license: string | null;
    external_ids: Record<string, string>;
  }>;
  primary_compound_id: string;
  resolution: string;
  recommended_action: string;
};

export type MedChemSourceCatalogEntry = {
  name: string;
  scope: string;
  access: string;
  license: string;
  commercial_use: string;
  recommended_use: string;
  release_phase: string;
  release_scope: string;
  url: string;
  status: string;
};

export type MedChemStatus = {
  library_id: string;
  rdkit_available: boolean;
  imported_compounds: number;
  compiled_compounds: number;
  invalid_compounds: number;
  unique_scaffolds: number;
  compiled: boolean;
  evidence: {
    targets: number;
    test_environments: number;
    bioactivity_records: number;
    literature_records: number;
    linked_activities: number;
    orphan_activities: string[];
    uncited_activities: string[];
    missing_environments: string[];
    invalid_activity_records: string[];
    missing_compound_provenance: string[];
    ready: boolean;
  };
  report: null | {
    rdkit_version: string;
    valid_compounds: number;
    invalid_compounds: number;
    unique_scaffolds: number;
    duplicate_inchikeys: string[];
    duplicate_identity_groups: MedChemDuplicateIdentityGroup[];
    invalid_records: Array<{ compound_id: string; name: string; smiles: string; error: string }>;
    diagnostics: MedChemDiagnostic[];
    report_path: string;
  };
};

export type MedChemValidation = {
  total: number;
  valid: number;
  invalid: number;
  valid_compounds: Array<{
    compound_id: string;
    name: string;
    smiles: string;
    canonical_smiles: string;
  }>;
  invalid_compounds: Array<{
    compound_id: string;
    name: string;
    smiles: string;
    error: string;
  }>;
};

export type MedChemSimilarity = {
  compound_id: string;
  name: string;
  canonical_smiles: string;
  inchikey: string;
  scaffold_smiles: string;
  tanimoto: number;
  status: string;
};

export type MedChemSafety = {
  allowed: boolean;
  blocked_categories: string[];
  response: string;
};

export type MedChemTarget = {
  target_id: string;
  name: string;
  gene_symbol: string;
  organism: string;
  accession: string;
  description: string;
  status: string;
};

export type MedChemEnvironment = {
  environment_id: string;
  name: string;
  environment_type: string;
  lab_name: string;
  biosafety_level: string;
  temperature_c: string;
  ph: string;
  solvent: string;
  buffer: string;
  cell_line: string;
  organism: string;
  assay_platform: string;
  instrument: string;
  notes: string;
  status: string;
};

export type MedChemActivity = {
  activity_id: string;
  compound_id: string;
  target_id: string;
  assay_type: string;
  assay_format: string;
  environment_id: string;
  endpoint: string;
  relation: string;
  value: string;
  unit: string;
  value_number: number | null;
  value_nM: number | null;
  p_activity: number | null;
  normalized_unit: string;
  normalization_method: string;
  result: string;
  source_ids: string[];
  evidence_note: string;
  test_environment: Record<string, string>;
  diagnostics: MedChemDiagnostic[];
  status: string;
};

export type MedChemLiterature = {
  source_id: string;
  title: string;
  citation: string;
  url: string;
  year: string;
  evidence_summary: string;
  status: string;
};

export type MedChemResearch = {
  allowed: boolean;
  blocked_categories: string[];
  answer: string;
  compound: MedChemCompound | null;
  activities: MedChemActivity[];
  targets: MedChemTarget[];
  environments: MedChemEnvironment[];
  citations: Array<MedChemLiterature & { number: number }>;
};

export type MedChemEvidenceEval = {
  passed: number;
  total: number;
  score: number;
  status: string;
  checks: Array<{ name: string; passed: boolean; detail: string }>;
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
  builtinExamples: () => request<BuiltinExample[]>("/examples"),
  installExample: (id: string) =>
    request<{ created: boolean; library: LibraryDetail }>(
      `/examples/${id}/install`,
      { method: "POST" },
    ),
  medchemStatus: (id: string) =>
    request<MedChemStatus>(`/libraries/${id}/medchem/status`),
  medchemSources: () =>
    request<Record<string, MedChemSourceCatalogEntry>>("/medchem/sources"),
  medchemImport: (id: string, file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<{ imported: number; updated: number; total: number }>(
      `/libraries/${id}/medchem/import`,
      { method: "POST", body: data },
    );
  },
  medchemImportEvidence: (
    id: string,
    kind: "targets" | "environments" | "bioactivity" | "literature",
    file: File,
  ) => {
    const data = new FormData();
    data.append("file", file);
    return request<{ imported: number; updated: number; total: number }>(
      `/libraries/${id}/medchem/${kind}/import`,
      { method: "POST", body: data },
    );
  },
  medchemValidate: (id: string) =>
    request<MedChemValidation>(`/libraries/${id}/medchem/validate`),
  medchemCompile: (id: string) =>
    request<NonNullable<MedChemStatus["report"]>>(
      `/libraries/${id}/medchem/compile`,
      { method: "POST" },
    ),
  medchemCompounds: (id: string, query = "") =>
    request<MedChemCompound[]>(
      `/libraries/${id}/medchem/compounds${query ? `?query=${encodeURIComponent(query)}` : ""}`,
    ),
  medchemStructureUrl: (smiles: string, width = 280, height = 170) =>
    `${getApiBase()}/medchem/structure.svg?smiles=${encodeURIComponent(smiles)}&width=${width}&height=${height}`,
  medchemStructure3dUrl: (smiles: string) =>
    `${getApiBase()}/medchem/structure3d.sdf?smiles=${encodeURIComponent(smiles)}`,
  medchemTargets: (id: string) =>
    request<MedChemTarget[]>(`/libraries/${id}/medchem/targets`),
  medchemEnvironments: (id: string) =>
    request<MedChemEnvironment[]>(`/libraries/${id}/medchem/environments`),
  medchemActivities: (id: string) =>
    request<MedChemActivity[]>(`/libraries/${id}/medchem/bioactivity`),
  medchemLiterature: (id: string) =>
    request<MedChemLiterature[]>(`/libraries/${id}/medchem/literature`),
  medchemResearch: (id: string, question: string) =>
    request<MedChemResearch>(`/libraries/${id}/medchem/research`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
  medchemEvidenceEvals: (id: string) =>
    request<MedChemEvidenceEval>(`/libraries/${id}/medchem/evals`, {
      method: "POST",
    }),
  medchemSimilar: (id: string, smiles: string, topK = 10) =>
    request<MedChemSimilarity[]>(`/libraries/${id}/medchem/similar`, {
      method: "POST",
      body: JSON.stringify({ smiles, top_k: topK }),
    }),
  medchemSafety: (value: string) =>
    request<MedChemSafety>("/medchem/safety-check", {
      method: "POST",
      body: JSON.stringify({ request: value }),
    }),
  models: () => request<ProviderInfo[]>("/models"),
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
