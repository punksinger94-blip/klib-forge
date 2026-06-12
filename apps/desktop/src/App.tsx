import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  AskResult,
  getApiBase,
  initializeRuntime,
  Library,
  LibraryDetail,
  SearchResult,
  setApiBase,
  Source,
} from "./api";

type View = "overview" | "sources" | "glossary" | "rules" | "chat" | "evals" | "diff" | "settings";

const navigation: Array<{ id: View; label: string; eyebrow: string }> = [
  { id: "overview", label: "Dashboard", eyebrow: "01" },
  { id: "sources", label: "Sources", eyebrow: "02" },
  { id: "glossary", label: "Glossary", eyebrow: "03" },
  { id: "rules", label: "Rules", eyebrow: "04" },
  { id: "chat", label: "Playground", eyebrow: "05" },
  { id: "evals", label: "Eval Arena", eyebrow: "06" },
  { id: "diff", label: "Knowledge Diff", eyebrow: "07" },
  { id: "settings", label: "Settings", eyebrow: "08" },
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
          {view === "diff" && selectedId && (
            <KnowledgeDiff id={selectedId} run={run} setNotice={setNotice} />
          )}
          {view === "settings" && <Settings refresh={refresh} setNotice={setNotice} />}
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
  const [compileInfo, setCompileInfo] = useState<{ chunks: number; keywords: string[] } | null>(null);

  const load = useCallback(() => api.sources(id).then(setSources), [id]);
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
          <div className="table-row table-head"><span>Source</span><span>Type</span><span>Trust</span></div>
          {sources.map((source) => (
            <div className="table-row" key={source.id}>
              <span><strong>{source.title}</strong><small>{source.path}</small></span>
              <span>{source.type.toUpperCase()}</span>
              <span className="trust">{source.trust_level}</span>
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
            <article key={item.id}><strong>{item.source_term}</strong><span className="mapping">=&gt;</span><strong>{item.target_term}</strong><p>{item.notes}</p></article>
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
  const load = useCallback(() => api.rules(id).then(setItems), [id]);
  useEffect(() => void load(), [load]);

  function submit(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      await api.addRule(id, { title, body, priority });
      setTitle(""); setBody(""); setPriority(5);
      await load();
      setNotice("Rule added to the prompt layer.");
    });
  }

  return (
    <div className="two-column">
      <form className="panel editor-form" onSubmit={submit}>
        <span className="kicker">BEHAVIOR POLICY</span><h3>Add rule</h3>
        <label>Title<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <label>Instruction<textarea value={body} onChange={(event) => setBody(event.target.value)} required /></label>
        <label>Priority<input type="range" min="1" max="10" value={priority} onChange={(event) => setPriority(Number(event.target.value))} /><span>{priority}</span></label>
        <button className="button primary">Save rule</button>
      </form>
      <div className="panel">
        <div className="card-list rule-list">
          {items.map((item) => (
            <article key={item.id}><span className="priority">P{item.priority}</span><strong>{item.title}</strong><p>{item.body}</p></article>
          ))}
          {!items.length && <EmptyState title="No custom rules" body="Rules are layered ahead of examples and retrieved context." />}
        </div>
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
  const [result, setResult] = useState<AskResult | null>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    void run(async () => {
      const response = await api.ask(id, { input, provider, model, mode: detail.manifest.default_mode });
      setResult(response);
      setContext(response.retrieved_context);
      setNotice(`${response.provider}/${response.model} completed in ${response.latency_ms} ms.`);
    });
  }

  return (
    <div className="playground">
      <div className="panel chat-panel">
        <div className="model-bar">
          <label>Provider<select value={provider} onChange={(event) => setProvider(event.target.value)}><option>ollama</option><option>lmstudio</option><option>nvidia</option><option>openai</option><option>mock</option></select></label>
          <label>Model<input value={model} onChange={(event) => setModel(event.target.value)} /></label>
        </div>
        <div className="answer">
          {result ? <><span className="kicker">MODEL OUTPUT</span><pre>{result.output}</pre></> : <EmptyState title="Ask with this K-LIB" body="The prompt is assembled from policy, glossary, rules, examples, and retrieved evidence." />}
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
  const [results, setResults] = useState<Array<{ eval_id: string; score: number; output: string }>>([]);

  function evaluate() {
    void run(async () => {
      const next = await api.evaluate(id, { provider, model });
      setResults(next);
      const average = next.reduce((sum, item) => sum + item.score, 0) / Math.max(next.length, 1);
      setNotice(`Eval run complete. Average score: ${average.toFixed(1)}.`);
    });
  }

  return (
    <div className="panel eval-panel">
      <div className="panel-heading">
        <div><span className="kicker">REGRESSION TESTING</span><h3>Eval Arena</h3></div>
        <div className="inline-controls"><select value={provider} onChange={(event) => setProvider(event.target.value)}><option>ollama</option><option>lmstudio</option><option>nvidia</option><option>openai</option><option>mock</option></select><input value={model} onChange={(event) => setModel(event.target.value)} /><button className="button primary" onClick={evaluate}>Run evals</button></div>
      </div>
      <div className="score-grid">
        {results.map((result) => (
          <article key={result.eval_id}><div className="score">{result.score.toFixed(0)}</div><div><strong>{result.eval_id}</strong><p>{result.output}</p></div></article>
        ))}
        {!results.length && <EmptyState title={`${detail.eval_count} evals ready`} body="Corrections can become deterministic regression checks." />}
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
  refresh,
  setNotice,
}: {
  refresh: () => Promise<void>;
  setNotice: (value: string) => void;
}) {
  const [base, setBase] = useState(getApiBase());
  function submit(event: FormEvent) {
    event.preventDefault();
    setApiBase(base);
    void refresh();
    setNotice("API endpoint updated.");
  }
  return (
    <form className="panel settings-panel" onSubmit={submit}>
      <span className="kicker">LOCAL RUNTIME</span><h3>Connection settings</h3>
      <label>FastAPI base URL<input value={base} onChange={(event) => setBase(event.target.value)} /></label>
      <p>
        The desktop app starts and stops its packaged backend automatically. This setting is
        retained for browser development or an explicitly managed remote runtime. Ollama defaults
        to <code>http://localhost:11434/v1</code>.
      </p>
      <button className="button primary">Save and reconnect</button>
    </form>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return <article><strong>{value.toString().padStart(2, "0")}</strong><span>{label}</span></article>;
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return <div className="empty-state"><div className="empty-mark">K</div><strong>{title}</strong><p>{body}</p></div>;
}

export default App;
