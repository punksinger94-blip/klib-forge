import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  AskResult,
  Capabilities,
  getApiBase,
  initializeRuntime,
  Library,
  LibraryDetail,
  ModelProfile,
  ModelRun,
  SearchResult,
  setApiBase,
  Source,
  Suggestion,
} from "./api";

type View =
  | "overview"
  | "sources"
  | "glossary"
  | "rules"
  | "examples"
  | "suggestions"
  | "corrections"
  | "chat"
  | "evals"
  | "history"
  | "diff"
  | "settings";

const navigation: Array<{ id: View; label: string; eyebrow: string }> = [
  { id: "overview", label: "Dashboard", eyebrow: "01" },
  { id: "sources", label: "Sources", eyebrow: "02" },
  { id: "glossary", label: "Glossary", eyebrow: "03" },
  { id: "rules", label: "Rules", eyebrow: "04" },
  { id: "examples", label: "Examples", eyebrow: "05" },
  { id: "suggestions", label: "Suggestions", eyebrow: "06" },
  { id: "corrections", label: "Corrections", eyebrow: "07" },
  { id: "chat", label: "Playground", eyebrow: "08" },
  { id: "evals", label: "Eval Arena", eyebrow: "09" },
  { id: "history", label: "Run History", eyebrow: "10" },
  { id: "diff", label: "Knowledge Diff", eyebrow: "11" },
  { id: "settings", label: "Settings", eyebrow: "12" },
];

function App() {
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<LibraryDetail | null>(null);
  const [view, setView] = useState<View>("overview");
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("Connect the local API to begin.");
  const [context, setContext] = useState<SearchResult[]>([]);
  const booted = useRef(false);

  const refresh = useCallback(async () => {
    try {
      await api.health();
      setConnected(true);
      const items = await api.libraries();
      setLibraries(items);
      const nextId = selectedId || items[0]?.id || "";
      setSelectedId(nextId);
      if (nextId) setDetail(await api.library(nextId));
      else setDetail(null);
      setNotice(items.length ? "Workspace synchronized." : "Create your first K-LIB.");
    } catch (error) {
      setConnected(false);
      setNotice(error instanceof Error ? error.message : "API connection failed.");
    }
  }, [selectedId]);

  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    void (async () => {
      try {
        const runtime = await initializeRuntime();
        if (runtime?.startupError) {
          setNotice(runtime.startupError);
        } else if (runtime?.managed) {
          setNotice(`Managed local runtime started on ${runtime.baseUrl}.`);
        }
      } catch (error) {
        setNotice(error instanceof Error ? error.message : "Desktop runtime discovery failed.");
      }
      await refresh();
    })();
  }, [refresh]);

  useEffect(() => {
    if (!selectedId) return;
    api.library(selectedId).then(setDetail).catch(() => setDetail(null));
  }, [selectedId]);

  async function run(task: () => Promise<void>) {
    setBusy(true);
    try {
      await task();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Operation failed.");
    } finally {
      setBusy(false);
    }
  }

  const selected = useMemo(
    () => libraries.find((library) => library.id === selectedId),
    [libraries, selectedId],
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">K</div>
          <div>
            <strong>K-LIB Forge</strong>
            <span>Knowledge compiler</span>
          </div>
        </div>

        <div className="library-picker">
          <label>ACTIVE PACKAGE</label>
          <select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
            {!libraries.length && <option value="">No libraries</option>}
            {libraries.map((library) => (
              <option key={library.id} value={library.id}>
                {library.name}
              </option>
            ))}
          </select>
        </div>

        <nav>
          {navigation.map((item) => (
            <button
              className={view === item.id ? "nav-item active" : "nav-item"}
              key={item.id}
              onClick={() => setView(item.id)}
            >
              <span>{item.eyebrow}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-status">
          <span className={connected ? "status-dot online" : "status-dot"} />
          <div>
            <strong>{connected ? "Local runtime online" : "Runtime offline"}</strong>
            <span>API {getApiBase()}</span>
          </div>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <span className="kicker">{selected?.domain || "LOCAL WORKSPACE"}</span>
            <h1>{navigation.find((item) => item.id === view)?.label}</h1>
          </div>
          <div className="topbar-actions">
            {detail && <span className="version-chip">v{detail.manifest.version}</span>}
            <button className="button ghost" onClick={() => void refresh()} disabled={busy}>
              Refresh
            </button>
          </div>
        </header>

        <div className="notice">
          <span>{busy ? "Working..." : notice}</span>
          <span>{detail?.manifest.id || "No package selected"}</span>
        </div>

        <section className="workspace">
          {view === "overview" && (
            <Overview
              detail={detail}
              libraries={libraries}
              run={run}
              refresh={refresh}
              select={setSelectedId}
              setNotice={setNotice}
            />
          )}
          {view === "sources" && selectedId && (
            <Sources
              id={selectedId}
              run={run}
              setNotice={setNotice}
              refresh={refresh}
            />
          )}
          {view === "glossary" && selectedId && (
            <Glossary id={selectedId} run={run} setNotice={setNotice} />
          )}
          {view === "rules" && selectedId && (
            <Rules id={selectedId} run={run} setNotice={setNotice} />
          )}
          {view === "examples" && selectedId && (
            <Examples id={selectedId} run={run} setNotice={setNotice} />
          )}
          {view === "suggestions" && selectedId && (
            <Suggestions id={selectedId} run={run} setNotice={setNotice} />
          )}
          {view === "corrections" && selectedId && (
            <Corrections id={selectedId} run={run} setNotice={setNotice} />
          )}
          {view === "chat" && selectedId && detail && (
            <Playground
              id={selectedId}
              detail={detail}
              run={run}
              context={context}
              setContext={setContext}
              setNotice={setNotice}
            />
          )}
          {view === "evals" && selectedId && detail && (
            <Evals id={selectedId} detail={detail} run={run} setNotice={setNotice} />
          )}
          {view === "history" && selectedId && (
            <History id={selectedId} />
          )}
          {view === "diff" && selectedId && (
            <KnowledgeDiff id={selectedId} run={run} setNotice={setNotice} />
          )}
          {view === "settings" && (
            <Settings
              detail={detail}
              refresh={refresh}
              setNotice={setNotice}
              run={run}
            />
          )}
          {!selectedId && view !== "overview" && (
            <EmptyState
              title="No K-LIB selected"
              body="Create a package from the Dashboard before using this workspace."
            />
          )}
        </section>
      </main>
    </div>
  );
}

function Overview({
  detail,
  libraries,
  run,
  refresh,
  select,
  setNotice,
}: {
  detail: LibraryDetail | null;
  libraries: Library[];
  run: (task: () => Promise<void>) => Promise<void>;
  refresh: () => Promise<void>;
  select: (id: string) => void;
  setNotice: (value: string) => void;
}) {
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("general");
  const [description, setDescription] = useState("");

  function create(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      const result = await api.createLibrary({ name, domain, description });
      setName("");
      setDescription("");
      await refresh();
      select(result.manifest.id);
      setNotice(`Created ${result.manifest.name}.`);
    });
  }

  function installExample() {
    void run(async () => {
      const result = await api.installExample();
      await refresh();
      select(result.library.manifest.id);
      setNotice(
        result.created
          ? "Installed and compiled the Arabic Technical Translation demo."
          : "The demo library is already installed.",
      );
    });
  }

  function exportPackage() {
    if (!detail) return;
    void run(async () => {
      const filename = await api.exportLibrary(detail.manifest.id);
      setNotice(`Exported ${filename}.`);
    });
  }

  function importPackage(file: File | undefined) {
    if (!file) return;
    void run(async () => {
      const manifest = await api.importLibrary(file);
      await refresh();
      select(manifest.id);
      setNotice(`Imported ${manifest.name}.`);
    });
  }

  function deletePackage() {
    if (!detail || !window.confirm(`Delete ${detail.manifest.name} and its local files?`)) return;
    void run(async () => {
      await api.deleteLibrary(detail.manifest.id);
      select("");
      await refresh();
      setNotice("Package deleted.");
    });
  }

  return (
    <div className="dashboard-grid">
      <div className="hero-panel">
        <div>
          <span className="kicker">PORTABLE AI KNOWLEDGE</span>
          <h2>Compile knowledge like software.</h2>
          <p>
            Build sources, rules, examples, corrections, and evals into a transparent package
            that runs with local or online models.
          </p>
          {!libraries.length && (
            <div className="hero-actions">
              <button className="button primary" onClick={installExample}>
                Install ready-to-run demo
              </button>
              <span>No model download required</span>
            </div>
          )}
        </div>
        <div className="pipeline">
          {["SOURCE", "COMPILE", "TEST", "PACKAGE"].map((step, index) => (
            <div key={step}>
              <span>0{index + 1}</span>
              <strong>{step}</strong>
            </div>
          ))}
        </div>
      </div>

      <form className="panel create-panel" onSubmit={create}>
        <div className="panel-heading">
          <div>
            <span className="kicker">NEW PACKAGE</span>
            <h3>Create K-LIB</h3>
          </div>
        </div>
        <label>
          Name
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label>
          Domain
          <input value={domain} onChange={(event) => setDomain(event.target.value)} />
        </label>
        <label>
          Description
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <button className="button primary" type="submit">
          Create package
        </button>
      </form>

      <div className="metrics">
        <Metric label="Registered libraries" value={libraries.length} />
        <Metric label="Sources" value={detail?.source_count ?? 0} />
        <Metric label="Glossary terms" value={detail?.glossary_count ?? 0} />
        <Metric label="Regression evals" value={detail?.eval_count ?? 0} />
      </div>

      <div className="panel package-card">
        <div className="panel-heading">
          <div>
            <span className="kicker">ACTIVE MANIFEST</span>
            <h3>{detail?.manifest.name || "No package selected"}</h3>
          </div>
          {detail && (
            <div className="package-actions">
              <span className="domain-tag">{detail.manifest.domain}</span>
              <button className="button secondary" onClick={exportPackage}>
                Export .klib
              </button>
              <label className="button secondary file-button">
                Import .klib
                <input
                  type="file"
                  accept=".klib"
                  onChange={(event) => importPackage(event.target.files?.[0])}
                />
              </label>
              <button className="button danger" onClick={deletePackage}>
                Delete
              </button>
            </div>
          )}
        </div>
        {detail ? (
          <>
            <p>{detail.manifest.description || "No package description yet."}</p>
            <dl>
              <div><dt>Provider</dt><dd>{detail.manifest.model_policy.default_provider}</dd></div>
              <div><dt>Model</dt><dd>{detail.manifest.model_policy.default_model}</dd></div>
              <div><dt>Retrieval</dt><dd>Top {detail.manifest.retrieval_policy.top_k}</dd></div>
              <div><dt>Citations</dt><dd>{detail.manifest.retrieval_policy.require_citations ? "Required" : "Optional"}</dd></div>
            </dl>
          </>
        ) : (
          <p>Create a K-LIB to initialize its strict package structure and manifest.</p>
        )}
      </div>
    </div>
  );
}

function Sources({
  id,
  run,
  setNotice,
  refresh,
}: {
  id: string;
  run: (task: () => Promise<void>) => Promise<void>;
  setNotice: (value: string) => void;
  refresh: () => Promise<void>;
}) {
  const [sources, setSources] = useState<Source[]>([]);
  const [trust, setTrust] = useState<Array<{ source_id: string; risk_score: number }>>([]);
  const [compileInfo, setCompileInfo] = useState<{ chunks: number; keywords: string[] } | null>(null);

  const load = useCallback(async () => {
    const [nextSources, nextTrust] = await Promise.all([api.sources(id), api.trust(id)]);
    setSources(nextSources);
    setTrust(nextTrust);
  }, [id]);
  useEffect(() => void load(), [load]);

  function upload(file: File | undefined) {
    if (!file) return;
    void run(async () => {
      await api.uploadSource(id, file);
      await load();
      await refresh();
      setNotice(`Added ${file.name}. Compile to refresh the index.`);
    });
  }

  function compile() {
    void run(async () => {
      const result = await api.compile(id);
      setCompileInfo(result);
      setNotice(`Compiled ${result.sources} sources into ${result.chunks} chunks.`);
    });
  }

  function remove(source: Source) {
    if (!window.confirm(`Remove ${source.title}?`)) return;
    void run(async () => {
      await api.deleteSource(id, source.id);
      await load();
      await refresh();
      setNotice(`Removed ${source.title}.`);
    });
  }

  function setTrustLevel(source: Source, trustLevel: string) {
    void run(async () => {
      await api.updateSource(id, source.id, { trust_level: trustLevel });
      await load();
      setNotice(`Marked ${source.title} as ${trustLevel}.`);
    });
  }

  return (
    <div className="two-column">
      <div className="panel">
        <div className="panel-heading">
          <div><span className="kicker">INGESTION</span><h3>Source manager</h3></div>
          <label className="button secondary file-button">
            Add source
            <input
              type="file"
              accept=".txt,.md,.markdown,.pdf,.json,.jsonl"
              onChange={(event) => upload(event.target.files?.[0])}
            />
          </label>
        </div>
        <div className="table">
          <div className="table-row source-table table-head"><span>Source</span><span>Type</span><span>Trust</span><span>Actions</span></div>
          {sources.map((source) => (
            <div className="table-row source-table" key={source.id}>
              <span><strong>{source.title}</strong><small>{source.path}</small></span>
              <span>{source.type.toUpperCase()}</span>
              <span className="trust">
                {source.trust_level} · risk {trust.find((item) => item.source_id === source.id)?.risk_score ?? 0}
              </span>
              <span className="row-actions">
                <select
                  value={source.trust_level}
                  onChange={(event) => setTrustLevel(source, event.target.value)}
                >
                  <option value="trusted">trusted</option>
                  <option value="user_added">user_added</option>
                  <option value="flagged">flagged</option>
                  <option value="blocked">blocked</option>
                </select>
                <button className="button danger compact" onClick={() => remove(source)}>Remove</button>
              </span>
            </div>
          ))}
          {!sources.length && <EmptyState title="No sources" body="Add TXT, Markdown, PDF, JSON, or JSONL files." />}
        </div>
      </div>
      <div className="panel compiler-panel">
        <span className="kicker">KNOWLEDGE COMPILER</span>
        <h3>Build the retrieval index</h3>
        <p>Clean source text, create overlapping chunks, extract keywords, and snapshot the package state.</p>
        <button className="button primary" onClick={compile}>Compile K-LIB</button>
        {compileInfo && (
          <div className="compile-output">
            <strong>{compileInfo.chunks} chunks generated</strong>
            <div className="tag-list">
              {compileInfo.keywords.slice(0, 12).map((keyword) => <span key={keyword}>{keyword}</span>)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Glossary({
  id,
  run,
  setNotice,
}: {
  id: string;
  run: (task: () => Promise<void>) => Promise<void>;
  setNotice: (value: string) => void;
}) {
  const [items, setItems] = useState<Array<{ id: string; source_term: string; target_term: string; notes: string }>>([]);
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [notes, setNotes] = useState("");
  const load = useCallback(() => api.glossary(id).then(setItems), [id]);
  useEffect(() => void load(), [load]);

  function submit(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      await api.addGlossary(id, { source_term: source, target_term: target, notes });
      setSource(""); setTarget(""); setNotes("");
      await load();
      setNotice("Glossary term saved.");
    });
  }

  function remove(entryId: string) {
    void run(async () => {
      await api.deleteGlossary(id, entryId);
      await load();
      setNotice("Glossary term deleted.");
    });
  }

  return (
    <div className="two-column">
      <form className="panel editor-form" onSubmit={submit}>
        <span className="kicker">TERM MAPPING</span><h3>Add glossary entry</h3>
        <label>Source term<input value={source} onChange={(event) => setSource(event.target.value)} required /></label>
        <label>Preferred term<input value={target} onChange={(event) => setTarget(event.target.value)} required /></label>
        <label>Notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
        <button className="button primary">Save term</button>
      </form>
      <div className="panel">
        <div className="panel-heading"><div><span className="kicker">PACKAGE MEMORY</span><h3>{items.length} terms</h3></div></div>
        <div className="card-list">
          {items.map((item) => (
            <article key={item.id}>
              <strong>{item.source_term}</strong><span className="mapping">=&gt;</span><strong>{item.target_term}</strong>
              <p>{item.notes}</p>
              <button className="button danger compact" onClick={() => remove(item.id)}>Delete</button>
            </article>
          ))}
          {!items.length && <EmptyState title="Glossary is empty" body="Preferred terms are injected before retrieved context." />}
        </div>
      </div>
    </div>
  );
}

function Rules({
  id,
  run,
  setNotice,
}: {
  id: string;
  run: (task: () => Promise<void>) => Promise<void>;
  setNotice: (value: string) => void;
}) {
  const [items, setItems] = useState<Array<{ id: string; title: string; body: string; priority: number }>>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState(5);
  const [editing, setEditing] = useState("");
  const load = useCallback(() => api.rules(id).then(setItems), [id]);
  useEffect(() => void load(), [load]);

  function submit(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      if (editing) await api.updateRule(id, editing, { title, body, priority });
      else await api.addRule(id, { title, body, priority });
      setTitle(""); setBody(""); setPriority(5);
      setEditing("");
      await load();
      setNotice("Rule added to the prompt layer.");
    });
  }

  function edit(item: { id: string; title: string; body: string; priority: number }) {
    setEditing(item.id);
    setTitle(item.title);
    setBody(item.body);
    setPriority(item.priority);
  }

  function remove(ruleId: string) {
    void run(async () => {
      await api.deleteRule(id, ruleId);
      await load();
      setNotice("Rule deleted.");
    });
  }

  return (
    <div className="two-column">
      <form className="panel editor-form" onSubmit={submit}>
        <span className="kicker">BEHAVIOR POLICY</span><h3>Add rule</h3>
        <label>Title<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <label>Instruction<textarea value={body} onChange={(event) => setBody(event.target.value)} required /></label>
        <label>Priority<input type="range" min="1" max="10" value={priority} onChange={(event) => setPriority(Number(event.target.value))} /><span>{priority}</span></label>
        <button className="button primary">{editing ? "Update rule" : "Save rule"}</button>
      </form>
      <div className="panel">
        <div className="card-list rule-list">
          {items.map((item) => (
            <article key={item.id}>
              <span className="priority">P{item.priority}</span><strong>{item.title}</strong><p>{item.body}</p>
              <div className="row-actions">
                <button className="button compact" onClick={() => edit(item)}>Edit</button>
                <button className="button danger compact" onClick={() => remove(item.id)}>Delete</button>
              </div>
            </article>
          ))}
          {!items.length && <EmptyState title="No custom rules" body="Rules are layered ahead of examples and retrieved context." />}
        </div>
      </div>
    </div>
  );
}

function Examples({
  id,
  run,
  setNotice,
}: {
  id: string;
  run: (task: () => Promise<void>) => Promise<void>;
  setNotice: (value: string) => void;
}) {
  const [items, setItems] = useState<Array<{ id: string; input: string; output: string; task: string; mode: string }>>([]);
  const [input, setInput] = useState("");
  const [output, setOutput] = useState("");
  const [task, setTask] = useState("");
  const [mode, setMode] = useState("");
  const [editing, setEditing] = useState("");
  const load = useCallback(() => api.examples(id).then(setItems), [id]);
  useEffect(() => void load(), [load]);

  function submit(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      const data = { input, output, task, mode };
      if (editing) await api.updateExample(id, editing, data);
      else await api.addExample(id, data);
      setInput(""); setOutput(""); setTask(""); setMode(""); setEditing("");
      await load();
      setNotice("Example saved.");
    });
  }

  function edit(item: { id: string; input: string; output: string; task: string; mode: string }) {
    setEditing(item.id); setInput(item.input); setOutput(item.output);
    setTask(item.task); setMode(item.mode);
  }

  function remove(exampleId: string) {
    void run(async () => {
      await api.deleteExample(id, exampleId);
      await load();
      setNotice("Example deleted.");
    });
  }

  return (
    <div className="two-column">
      <form className="panel editor-form" onSubmit={submit}>
        <span className="kicker">FEW-SHOT BEHAVIOR</span><h3>{editing ? "Edit example" : "Add example"}</h3>
        <label>Input<textarea value={input} onChange={(event) => setInput(event.target.value)} required /></label>
        <label>Expected output<textarea value={output} onChange={(event) => setOutput(event.target.value)} required /></label>
        <label>Task<input value={task} onChange={(event) => setTask(event.target.value)} /></label>
        <label>Mode<input value={mode} onChange={(event) => setMode(event.target.value)} /></label>
        <button className="button primary">Save example</button>
      </form>
      <div className="panel card-list">
        {items.map((item) => (
          <article key={item.id}>
            <strong>{item.input}</strong><p>{item.output}</p>
            <div className="row-actions">
              <button className="button compact" onClick={() => edit(item)}>Edit</button>
              <button className="button danger compact" onClick={() => remove(item.id)}>Delete</button>
            </div>
          </article>
        ))}
        {!items.length && <EmptyState title="No examples" body="Examples shape package-specific output behavior." />}
      </div>
    </div>
  );
}

function Suggestions({
  id,
  run,
  setNotice,
}: {
  id: string;
  run: (task: () => Promise<void>) => Promise<void>;
  setNotice: (value: string) => void;
}) {
  const [items, setItems] = useState<Suggestion[]>([]);
  const load = useCallback(() => api.suggestions(id).then(setItems), [id]);
  useEffect(() => void load(), [load]);

  function apply(item: Suggestion) {
    void run(async () => {
      await api.applySuggestion(id, item);
      setItems((current) => current.filter((value) => value.id !== item.id));
      setNotice(`Applied ${item.kind} suggestion.`);
    });
  }

  return (
    <div className="panel">
      <div className="panel-heading">
        <div><span className="kicker">KNOWLEDGE ASSISTANT</span><h3>Review suggested package assets</h3></div>
        <button className="button secondary" onClick={() => void load()}>Regenerate</button>
      </div>
      <div className="card-list suggestion-grid">
        {items.map((item) => (
          <article key={item.id}>
            <span className="domain-tag">{item.kind} · {(item.confidence * 100).toFixed(0)}%</span>
            <h3>{item.title}</h3><p>{item.reason}</p>
            <pre>{JSON.stringify(item.payload, null, 2)}</pre>
            <button className="button primary" onClick={() => apply(item)}>Apply suggestion</button>
          </article>
        ))}
        {!items.length && <EmptyState title="No suggestions" body="Add and compile sources, then regenerate package suggestions." />}
      </div>
    </div>
  );
}

function Corrections({
  id,
  run,
  setNotice,
}: {
  id: string;
  run: (task: () => Promise<void>) => Promise<void>;
  setNotice: (value: string) => void;
}) {
  const [items, setItems] = useState<Array<Record<string, string>>>([]);
  const load = useCallback(() => api.corrections(id).then(setItems), [id]);
  useEffect(() => void load(), [load]);

  function review(correctionId: string, status: string) {
    void run(async () => {
      await api.reviewCorrection(id, correctionId, status);
      await load();
      setNotice(`Correction ${status}.`);
    });
  }

  return (
    <div className="panel">
      <div className="panel-heading"><div><span className="kicker">REVIEW QUEUE</span><h3>Corrections</h3></div></div>
      <div className="card-list">
        {items.map((item) => (
          <article key={item.id}>
            <span className={`status-chip ${item.status || "pending"}`}>{item.status || "pending"}</span>
            <strong>{item.input}</strong>
            <p><b>Rejected answer:</b> {item.bad_output}</p>
            <p><b>Corrected answer:</b> {item.corrected_output}</p>
            <p>{item.lesson}</p>
            <div className="row-actions">
              <button className="button primary compact" onClick={() => review(item.id, "approved")}>Approve</button>
              <button className="button danger compact" onClick={() => review(item.id, "rejected")}>Reject</button>
              <button className="button compact" onClick={() => review(item.id, "pending")}>Reopen</button>
            </div>
          </article>
        ))}
        {!items.length && <EmptyState title="No corrections" body="Corrections created from model feedback appear here for review." />}
      </div>
    </div>
  );
}

function History({ id }: { id: string }) {
  const [runs, setRuns] = useState<ModelRun[]>([]);
  const [selected, setSelected] = useState<ModelRun | null>(null);
  useEffect(() => void api.runs(id).then((items) => {
    setRuns(items);
    setSelected(items[0] || null);
  }), [id]);

  return (
    <div className="history-grid">
      <div className="panel card-list">
        {runs.map((run) => (
          <button className="history-item" key={run.id} onClick={() => setSelected(run)}>
            <strong>{run.provider}/{run.model}</strong>
            <span>{run.latency_ms} ms · {new Date(run.created_at).toLocaleString()}</span>
            <p>{run.input}</p>
          </button>
        ))}
        {!runs.length && <EmptyState title="No runs yet" body="Playground and eval requests are recorded locally." />}
      </div>
      <div className="panel inspector">
        {selected ? (
          <>
            <span className="kicker">PROMPT INSPECTOR</span><h3>{selected.input}</h3>
            <h4>Assembled prompt</h4><pre>{selected.prompt}</pre>
            <h4>Output</h4><pre>{selected.output}</pre>
          </>
        ) : <EmptyState title="Select a run" body="Inspect the complete prompt and model output." />}
      </div>
    </div>
  );
}

function Playground({
  id,
  detail,
  run,
  context,
  setContext,
  setNotice,
}: {
  id: string;
  detail: LibraryDetail;
  run: (task: () => Promise<void>) => Promise<void>;
  context: SearchResult[];
  setContext: (value: SearchResult[]) => void;
  setNotice: (value: string) => void;
}) {
  const [input, setInput] = useState("");
  const [provider, setProvider] = useState(detail.manifest.model_policy.default_provider);
  const [model, setModel] = useState(detail.manifest.model_policy.default_model);
  const [baseUrl, setBaseUrl] = useState("");
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [result, setResult] = useState<AskResult | null>(null);
  const [corrected, setCorrected] = useState("");
  const [lesson, setLesson] = useState("");
  useEffect(() => void api.profiles().then(setProfiles), []);

  function submit(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      const response = await api.ask(id, { input, provider, model, mode: detail.manifest.default_mode, base_url: baseUrl || undefined });
      setResult(response);
      setContext(response.retrieved_context);
      setNotice(`${response.provider}/${response.model} completed in ${response.latency_ms} ms.`);
    });
  }

  function saveCorrection() {
    if (!result || !corrected) return;
    void run(async () => {
      await api.correct(id, {
        input,
        bad_output: result.output,
        corrected_output: corrected,
        lesson,
        create_eval: true,
      });
      setCorrected(""); setLesson("");
      setNotice("Correction queued for review and a regression eval was created.");
    });
  }

  return (
    <div className="playground">
      <div className="panel chat-panel">
        <div className="model-bar">
          <label>Profile<select defaultValue="" onChange={(event) => {
            const profile = profiles.find((item) => item.id === event.target.value);
            if (profile) { setProvider(profile.provider); setModel(profile.model); setBaseUrl(profile.base_url || ""); }
          }}><option value="">Custom</option>{profiles.map((profile) => <option value={profile.id} key={profile.id}>{profile.name}</option>)}</select></label>
          <label>Provider<select value={provider} onChange={(event) => setProvider(event.target.value)}><option>ollama</option><option>lmstudio</option><option>nvidia</option><option>openai</option><option>mock</option></select></label>
          <label>Model<input value={model} onChange={(event) => setModel(event.target.value)} /></label>
          <label>Base URL<input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="Provider default" /></label>
        </div>
        <div className="answer">
          {result ? <><span className="kicker">MODEL OUTPUT</span><pre>{result.output}</pre>
            <div className="correction-box">
              <h4>Correct this answer</h4>
              <textarea value={corrected} onChange={(event) => setCorrected(event.target.value)} placeholder="Reviewed correct output" />
              <input value={lesson} onChange={(event) => setLesson(event.target.value)} placeholder="Lesson for future runs" />
              <button className="button secondary" onClick={saveCorrection} disabled={!corrected}>Queue correction</button>
            </div>
          </> : <EmptyState title="Ask with this K-LIB" body="The prompt is assembled from policy, glossary, rules, examples, and retrieved evidence." />}
        </div>
        <form className="prompt-box" onSubmit={submit}>
          <textarea placeholder="Ask, translate, review, or explain..." value={input} onChange={(event) => setInput(event.target.value)} required />
          <button className="button primary">Run</button>
        </form>
      </div>
      <aside className="panel context-panel">
        <span className="kicker">RETRIEVED CONTEXT</span>
        <h3>{context.length} evidence chunks</h3>
        <div className="context-list">
          {context.map((item, index) => (
            <article key={item.chunk_id}><header><span>[{index + 1}] {item.source_title}</span><strong>{item.score.toFixed(2)}</strong></header><p>{item.text}</p></article>
          ))}
          {!context.length && <p className="muted">Context appears here after a run.</p>}
        </div>
      </aside>
    </div>
  );
}

function Evals({
  id,
  detail,
  run,
  setNotice,
}: {
  id: string;
  detail: LibraryDetail;
  run: (task: () => Promise<void>) => Promise<void>;
  setNotice: (value: string) => void;
}) {
  const [provider, setProvider] = useState(detail.manifest.model_policy.default_provider);
  const [model, setModel] = useState(detail.manifest.model_policy.default_model);
  const [secondProvider, setSecondProvider] = useState("mock");
  const [secondModel, setSecondModel] = useState("offline-demo");
  const [results, setResults] = useState<Array<{ eval_id: string; score: number; output: string }>>([]);
  const [arena, setArena] = useState<Array<{ name: string; average: number }>>([]);
  const [evals, setEvals] = useState<Array<{ id: string; name: string; task: string; input: string; checks: Record<string, unknown> }>>([]);
  const [evalName, setEvalName] = useState("");
  const [evalInput, setEvalInput] = useState("");
  const [mustInclude, setMustInclude] = useState("");
  const loadEvals = useCallback(() => api.evals(id).then(setEvals), [id]);
  useEffect(() => void loadEvals(), [loadEvals]);

  function evaluate() {
    void run(async () => {
      const next = await api.evaluate(id, { provider, model });
      setResults(next);
      const average = next.reduce((sum, item) => sum + item.score, 0) / Math.max(next.length, 1);
      setNotice(`Eval run complete. Average score: ${average.toFixed(1)}.`);
    });
  }

  function compare() {
    void run(async () => {
      const response = await api.arena(id, [
        { name: `${provider}/${model}`, provider, model },
        { name: `${secondProvider}/${secondModel}`, provider: secondProvider, model: secondModel },
      ]);
      setArena(response.models);
      setNotice("Multi-model arena completed.");
    });
  }

  function addEval(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      await api.saveEval(id, {
        name: evalName,
        task: detail.manifest.default_mode,
        input: evalInput,
        checks: {
          must_include: mustInclude.split(",").map((item) => item.trim()).filter(Boolean),
          citation_required: detail.manifest.retrieval_policy.require_citations,
        },
      });
      setEvalName(""); setEvalInput(""); setMustInclude("");
      await loadEvals();
      setNotice("Eval saved.");
    });
  }

  function removeEval(evalId: string) {
    void run(async () => {
      await api.deleteEval(id, evalId);
      await loadEvals();
      setNotice("Eval deleted.");
    });
  }

  return (
    <div className="panel eval-panel">
      <div className="panel-heading">
        <div><span className="kicker">REGRESSION TESTING</span><h3>Eval Arena</h3></div>
        <div className="inline-controls"><select value={provider} onChange={(event) => setProvider(event.target.value)}><option>ollama</option><option>lmstudio</option><option>nvidia</option><option>openai</option><option>mock</option></select><input value={model} onChange={(event) => setModel(event.target.value)} /><button className="button primary" onClick={evaluate}>Run evals</button></div>
      </div>
      <div className="arena-controls">
        <select value={secondProvider} onChange={(event) => setSecondProvider(event.target.value)}><option>mock</option><option>ollama</option><option>lmstudio</option><option>nvidia</option><option>openai</option></select>
        <input value={secondModel} onChange={(event) => setSecondModel(event.target.value)} />
        <button className="button secondary" onClick={compare}>Compare two models</button>
        {arena.map((item, index) => <span className="score-pill" key={`${item.name}-${index}`}>{item.name}: {item.average.toFixed(1)}</span>)}
      </div>
      <div className="score-grid">
        {results.map((result) => (
          <article key={result.eval_id}><div className="score">{result.score.toFixed(0)}</div><div><strong>{result.eval_id}</strong><p>{result.output}</p></div></article>
        ))}
        {!results.length && <EmptyState title={`${evals.length} evals ready`} body="Corrections can become deterministic regression checks." />}
      </div>
      <div className="eval-editor-grid">
        <form className="editor-form" onSubmit={addEval}>
          <h3>Add deterministic eval</h3>
          <label>Name<input value={evalName} onChange={(event) => setEvalName(event.target.value)} /></label>
          <label>Question<textarea value={evalInput} onChange={(event) => setEvalInput(event.target.value)} required /></label>
          <label>Required phrases, comma-separated<input value={mustInclude} onChange={(event) => setMustInclude(event.target.value)} /></label>
          <button className="button primary">Save eval</button>
        </form>
        <div className="card-list">
          {evals.map((item) => (
            <article key={item.id}><strong>{item.name || item.id}</strong><p>{item.input}</p><button className="button danger compact" onClick={() => removeEval(item.id)}>Delete</button></article>
          ))}
        </div>
      </div>
    </div>
  );
}

function KnowledgeDiff({
  id,
  run,
  setNotice,
}: {
  id: string;
  run: (task: () => Promise<void>) => Promise<void>;
  setNotice: (value: string) => void;
}) {
  const [diff, setDiff] = useState<Record<string, string | string[] | null> | null>(null);

  function compare() {
    void run(async () => {
      const result = await api.diff(id);
      setDiff(result);
      setNotice("Compared current knowledge with the latest compiled snapshot.");
    });
  }

  const sections = diff
    ? Object.entries(diff).filter(([, value]) => Array.isArray(value))
    : [];

  return (
    <div className="panel diff-panel">
      <div className="panel-heading">
        <div><span className="kicker">CHANGE IMPACT</span><h3>Knowledge Diff</h3></div>
        <button className="button primary" onClick={compare}>Compare snapshot</button>
      </div>
      {diff ? (
        <div className="diff-grid">
          {sections.map(([name, value]) => (
            <article key={name}><span>{name.replaceAll("_", " ")}</span><strong>{(value as string[]).length}</strong>{(value as string[]).map((item) => <p key={item}>{item}</p>)}</article>
          ))}
        </div>
      ) : (
        <EmptyState title="No comparison loaded" body="Compile to create a snapshot, edit knowledge, then compare." />
      )}
    </div>
  );
}

function Settings({
  detail,
  refresh,
  setNotice,
  run,
}: {
  detail: LibraryDetail | null;
  refresh: () => Promise<void>;
  setNotice: (value: string) => void;
  run: (task: () => Promise<void>) => Promise<void>;
}) {
  const [base, setBase] = useState(getApiBase());
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [profileName, setProfileName] = useState("");
  const [provider, setProvider] = useState("ollama");
  const [model, setModel] = useState("gemma3");
  const [profileBase, setProfileBase] = useState("");
  const [apiKeyEnv, setApiKeyEnv] = useState("");
  const [packageName, setPackageName] = useState(detail?.manifest.name || "");
  const [description, setDescription] = useState(detail?.manifest.description || "");
  const [domain, setDomain] = useState(detail?.manifest.domain || "general");
  const [defaultProvider, setDefaultProvider] = useState(
    detail?.manifest.model_policy.default_provider || "ollama",
  );
  const [defaultModel, setDefaultModel] = useState(
    detail?.manifest.model_policy.default_model || "gemma3",
  );
  const [allowOnline, setAllowOnline] = useState(
    detail?.manifest.model_policy.allow_online_models || false,
  );
  const [adapter, setAdapter] = useState(
    detail?.manifest.retrieval_policy.vector_adapter || "local",
  );
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [hybrid, setHybrid] = useState(
    detail?.manifest.retrieval_policy.use_hybrid_search || false,
  );
  const loadProfiles = useCallback(() => api.profiles().then(setProfiles), []);
  useEffect(() => void loadProfiles(), [loadProfiles]);
  useEffect(() => {
    void api.capabilities().then(setCapabilities).catch(() => setCapabilities(null));
  }, []);
  useEffect(() => {
    if (!detail) return;
    setPackageName(detail.manifest.name);
    setDescription(detail.manifest.description);
    setDomain(detail.manifest.domain);
    setDefaultProvider(detail.manifest.model_policy.default_provider);
    setDefaultModel(detail.manifest.model_policy.default_model);
    setAllowOnline(detail.manifest.model_policy.allow_online_models);
    setAdapter(detail.manifest.retrieval_policy.vector_adapter);
    setHybrid(detail.manifest.retrieval_policy.use_hybrid_search);
  }, [detail]);
  function submit(event: FormEvent) {
    event.preventDefault();
    setApiBase(base);
    void refresh();
    setNotice("API endpoint updated.");
  }
  function saveProfile(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      await api.saveProfile({
        name: profileName,
        provider,
        model,
        base_url: profileBase || null,
        api_key_env: apiKeyEnv || null,
        options: {},
      });
      setProfileName("");
      await loadProfiles();
      setNotice("Model profile saved. Secrets remain in environment variables.");
    });
  }
  function saveRetrieval() {
    if (!detail) return;
    if (capabilities && !capabilities.vector_adapters[adapter]) {
      setNotice(`${adapter} is unavailable in this runtime.`);
      return;
    }
    void run(async () => {
      await api.updateLibrary(detail.manifest.id, {
        retrieval_policy: {
          ...detail.manifest.retrieval_policy,
          vector_adapter: adapter,
          use_hybrid_search: hybrid,
        },
      });
      await refresh();
      setNotice("Retrieval policy saved. Recompile the package to rebuild indexes.");
    });
  }
  function removeProfile(profileId: string) {
    void run(async () => {
      await api.deleteProfile(profileId);
      await loadProfiles();
      setNotice("Model profile deleted.");
    });
  }
  function savePackage() {
    if (!detail) return;
    void run(async () => {
      await api.updateLibrary(detail.manifest.id, {
        name: packageName,
        description,
        domain,
        model_policy: {
          ...detail.manifest.model_policy,
          default_provider: defaultProvider,
          default_model: defaultModel,
          allow_online_models: allowOnline,
        },
      });
      await refresh();
      setNotice("Package manifest saved.");
    });
  }
  return (
    <div className="settings-grid">
      <div className="panel settings-panel">
        <span className="kicker">PACKAGE MANIFEST</span><h3>Package settings</h3>
        <label>Name<input value={packageName} onChange={(event) => setPackageName(event.target.value)} /></label>
        <label>Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} /></label>
        <label>Domain<input value={domain} onChange={(event) => setDomain(event.target.value)} /></label>
        <label>Default provider<input value={defaultProvider} onChange={(event) => setDefaultProvider(event.target.value)} /></label>
        <label>Default model<input value={defaultModel} onChange={(event) => setDefaultModel(event.target.value)} /></label>
        <label className="check-label"><input type="checkbox" checked={allowOnline} onChange={(event) => setAllowOnline(event.target.checked)} /> Allow online model providers</label>
        <button className="button primary" onClick={savePackage} disabled={!detail}>Save package</button>
      </div>
      <form className="panel settings-panel" onSubmit={submit}>
        <span className="kicker">LOCAL RUNTIME</span><h3>Connection settings</h3>
        <label>FastAPI base URL<input value={base} onChange={(event) => setBase(event.target.value)} /></label>
        <p>The desktop starts its packaged backend automatically. Remote endpoints remain explicit.</p>
        <button className="button primary">Save and reconnect</button>
      </form>
      <div className="panel settings-panel">
        <span className="kicker">RETRIEVAL</span><h3>Index adapter</h3>
        <label>Vector adapter<select value={adapter} onChange={(event) => setAdapter(event.target.value as "local" | "chroma" | "qdrant")}><option value="local">local</option><option value="chroma" disabled={capabilities?.vector_adapters.chroma === false}>chroma{capabilities?.vector_adapters.chroma === false ? " (unavailable)" : ""}</option><option value="qdrant">qdrant</option></select></label>
        {capabilities?.vector_adapters.chroma === false && <p>Chroma requires the optional <code>klib-forge[chroma]</code> Python dependency and is not bundled in this desktop runtime.</p>}
        <label className="check-label"><input type="checkbox" checked={hybrid} onChange={(event) => setHybrid(event.target.checked)} /> Fuse lexical and vector results</label>
        <button className="button primary" onClick={saveRetrieval} disabled={!detail || capabilities?.vector_adapters[adapter] === false}>Save retrieval policy</button>
      </div>
      <form className="panel settings-panel" onSubmit={saveProfile}>
        <span className="kicker">MODEL PROFILES</span><h3>Reusable connector</h3>
        <label>Name<input value={profileName} onChange={(event) => setProfileName(event.target.value)} required /></label>
        <label>Provider<input value={provider} onChange={(event) => setProvider(event.target.value)} required /></label>
        <label>Model<input value={model} onChange={(event) => setModel(event.target.value)} required /></label>
        <label>Base URL<input value={profileBase} onChange={(event) => setProfileBase(event.target.value)} /></label>
        <label>API-key environment variable<input value={apiKeyEnv} onChange={(event) => setApiKeyEnv(event.target.value)} placeholder="NVIDIA_API_KEY" /></label>
        <button className="button primary">Save profile</button>
      </form>
      <div className="panel card-list">
        {profiles.map((profile) => (
          <article key={profile.id}><strong>{profile.name}</strong><p>{profile.provider}/{profile.model}<br />{profile.base_url}<br />Secret: {profile.api_key_env || "none"}</p><button className="button danger compact" onClick={() => removeProfile(profile.id)}>Delete</button></article>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return <article><strong>{value.toString().padStart(2, "0")}</strong><span>{label}</span></article>;
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return <div className="empty-state"><div className="empty-mark">K</div><strong>{title}</strong><p>{body}</p></div>;
}

export default App;
