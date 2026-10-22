import { useEffect, useRef, useState } from "react";
import { api, readable, type Case, type Catalog, type Project, type Run, type Suite, type User } from "./api";
import Auth from "./Auth";
import Accounts from "./Accounts";
import Overview from "./Overview";
import Generate from "./Generate";
import Library from "./Library";
import Executions from "./Executions";
import { Empty, ErrorMessage, PageTitle } from "./ui";
type Workspace = {
  cases: Case[];
  suites: Suite[];
  runs: Run[];
  metrics: Record<string, number>;
  audit: Record<string, unknown>[];
};
const emptyWorkspace: Workspace = { cases: [], suites: [], runs: [], metrics: {}, audit: [] };
const navigation = [
  { name: "Overview", icon: "◫", section: "WORKSPACE" },
  { name: "Generate", icon: "✧" },
  { name: "Case library", icon: "▤" },
  { name: "Suites & runs", icon: "▷" },
  { name: "Audit trail", icon: "≡", section: "EVIDENCE" },
  { name: "Accounts", icon: "⊕" },
];
const descriptions: Record<string, string> = {
  Overview: "A clear view of your scenarios, approvals, and execution evidence.",
  Generate: "Start with a situation. Build a reproducible set of scenarios.",
  "Case library": "Inspect, revise, and review each scenario before execution.",
  "Suites & runs": "Snapshot approved cases and record explicit execution outcomes.",
  "Audit trail": "Trace recorded actions across your local project.",
  Accounts: "Create local author and reviewer accounts with explicit roles.",
};
function getStored(key: string) {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}
function store(key: string, value: string) {
  try {
    value ? localStorage.setItem(key, value) : localStorage.removeItem(key);
  } catch {
    /* Session still works if storage is unavailable. */
  }
}
export default function App() {
  const [token, setToken] = useState(() => getStored("sek-token"));
  const [user, setUser] = useState<User | null>(null);
  const [authError, setAuthError] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(() => getStored("sek-project"));
  const [catalog, setCatalog] = useState<Catalog>({ maps: [], kinds: [], weather: [] });
  const [workspace, setWorkspace] = useState<Workspace>(emptyWorkspace);
  const [view, setView] = useState("Overview");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const navigationPanel = useRef<HTMLElement>(null);
  const [newProject, setNewProject] = useState(false);
  function closeNavigation() {
    setMobileOpen(false);
    if (mobileOpen) menuButton.current?.focus();
  }
  useEffect(() => {
    if (!mobileOpen) return;
    navigationPanel.current?.querySelector<HTMLAnchorElement>("a")?.focus();
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMobileOpen(false);
        menuButton.current?.focus();
      }
    }
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [mobileOpen]);
  function logout() {
    if (token) void api("/auth/logout", token, {}).catch(() => undefined);
    store("sek-token", "");
    setToken("");
    setUser(null);
    setAuthError("");
    setWorkspace(emptyWorkspace);
  }
  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    setAuthError("");
    Promise.all([
      api<User>("/auth/me", token, undefined, controller.signal),
      api<Project[]>("/projects", token, undefined, controller.signal),
      api<Catalog>("/catalog", token, undefined, controller.signal),
    ])
      .then(([me, list, cat]) => {
        setUser(me);
        setProjects(list);
        setCatalog(cat);
        setProjectId((current) => (list.some((p) => p.id === current) ? current : (list[0]?.id ?? "")));
      })
      .catch((e) => {
        if (!controller.signal.aborted) setAuthError(String(e));
      });
    return () => controller.abort();
  }, [token]);
  useEffect(() => {
    if (!token || !user || !projectId) {
      setWorkspace(emptyWorkspace);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError("");
    const suffix = `?project_id=${encodeURIComponent(projectId)}`;
    Promise.all([
      api<Case[]>(`/cases${suffix}`, token, undefined, controller.signal),
      api<Suite[]>(`/suites${suffix}`, token, undefined, controller.signal),
      api<Run[]>(`/runs${suffix}`, token, undefined, controller.signal),
      api<Record<string, number>>(`/metrics${suffix}`, token, undefined, controller.signal),
      api<Record<string, unknown>[]>(`/audit${suffix}`, token, undefined, controller.signal),
    ])
      .then(([cases, suites, runs, metrics, audit]) => {
        setWorkspace({ cases, suites, runs, metrics, audit });
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(String(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [token, user, projectId, revision]);
  function refresh() {
    setRevision((r) => r + 1);
  }
  function chooseProject(id: string) {
    setProjectId(id);
    store("sek-project", id);
    setWorkspace(emptyWorkspace);
  }
  async function createProject(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(true);
    setError("");
    try {
      const project = await api<Project>("/projects", token, { name: new FormData(form).get("name") });
      setProjects((p) => [...p, project]);
      chooseProject(project.id);
      setNewProject(false);
      form.reset();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  if (!token)
    return (
      <Auth
        onLogin={(value, me) => {
          store("sek-token", value);
          setToken(value);
          setUser(me);
        }}
      />
    );
  if (!user)
    return (
      <main className="session-loading">
        <div className="brand-icon">S↗</div>
        <h1>Opening your workbench</h1>
        <p role="status">Verifying your local session…</p>
        <ErrorMessage error={authError} />
        <button onClick={logout}>Return to sign in</button>
      </main>
    );
  const project = projects.find((p) => p.id === projectId);
  const metrics = workspace.metrics;
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside ref={navigationPanel} id="workspace-navigation" className={`sidebar ${mobileOpen ? "open" : ""}`}>
        <a className="wordmark" href="#main" onClick={closeNavigation}>
          <span className="brand-icon">
            S<span>↗</span>
          </span>
          <span>
            Scenario
            <br />
            Evidence Kit
          </span>
        </a>
        <div className="sidebar-project">
          <label htmlFor="project-select">ACTIVE PROJECT</label>
          <select id="project-select" value={projectId} onChange={(e) => chooseProject(e.target.value)}>
            <option value="" disabled>
              Select a project
            </option>
            {projects.map((p) => (
              <option value={p.id} key={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <button
            className="sidebar-new"
            onClick={() => {
              setNewProject((p) => !p);
              closeNavigation();
            }}
          >
            + New project
          </button>
        </div>
        <nav aria-label="Main navigation">
          {navigation
            .filter((n) => n.name !== "Accounts" || user.role === "owner")
            .map((n) => (
              <div key={n.name}>
                {n.section && <p className="nav-caption">{n.section}</p>}
                <button
                  className={view === n.name ? "nav-item active" : "nav-item"}
                  aria-current={view === n.name ? "page" : undefined}
                  onClick={() => {
                    setView(n.name);
                    closeNavigation();
                  }}
                >
                  <span aria-hidden="true">{n.icon}</span>
                  {n.name}
                  {n.name === "Case library" && <small>{workspace.cases.length}</small>}
                </button>
              </div>
            ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-label">
            <i /> LOCAL · OFFLINE FIRST
          </div>
          <p>
            Evidence you can inspect.
            <br />
            Outcomes you can trace.
          </p>
          <div className="profile">
            <span className="avatar">{user.name.slice(0, 1).toUpperCase()}</span>
            <span>
              <strong>{user.name}</strong>
              <small>{user.role}</small>
            </span>
            <button onClick={logout} aria-label="Sign out" title="Sign out">
              ↗
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <button
            className="mobile-toggle"
            ref={menuButton}
            aria-label="Toggle navigation"
            aria-controls="workspace-navigation"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen((v) => !v)}
          >
            ☰
          </button>
          <span className="breadcrumb">
            Workspace <span>/</span> <strong>{project?.name || "Get started"}</strong>
          </span>
          <span className="top-status">
            <i /> Local instance <span className="divider">|</span> v0.1
          </span>
        </header>
        <main id="main">
          <PageTitle eyebrow="SCENARIO EVIDENCE KIT" title={view}>
            {descriptions[view]}
          </PageTitle>
          <ErrorMessage error={error} />
          {newProject && (
            <section className="panel new-project">
              <form onSubmit={createProject}>
                <label>
                  New project name
                  <input name="name" autoFocus required maxLength={150} placeholder="e.g. Urban interaction study" />
                </label>
                <button className="primary" disabled={busy}>
                  Create project
                </button>
                <button type="button" onClick={() => setNewProject(false)}>
                  Cancel
                </button>
              </form>
            </section>
          )}
          {view === "Accounts" && user.role === "owner" ? (
            <Accounts token={token} />
          ) : !projectId ? (
            <section className="panel">
              <Empty title="Your first project starts here">
                Create a project to organize scenarios, review revisions, and collect execution evidence.
              </Empty>
              <div className="center">
                <button className="primary" onClick={() => setNewProject(true)}>
                  + Create a project
                </button>
              </div>
            </section>
          ) : loading && workspace === emptyWorkspace ? (
            <section className="panel loading" role="status">
              <span className="loader" /> Loading project evidence…
            </section>
          ) : error ? (
            <button onClick={refresh}>Retry project data</button>
          ) : (
            <div key={projectId}>
              {view === "Overview" && <Overview metrics={metrics} cases={workspace.cases} setView={setView} />}
              {view === "Generate" && (
                <Generate
                  token={token}
                  projectId={projectId}
                  catalog={catalog}
                  role={user.role}
                  onCreated={() => {
                    refresh();
                    setView("Case library");
                  }}
                />
              )}
              {view === "Case library" && (
                <Library token={token} projectId={projectId} cases={workspace.cases} user={user} refresh={refresh} />
              )}
              {view === "Suites & runs" && (
                <Executions
                  token={token}
                  projectId={projectId}
                  cases={workspace.cases}
                  suites={workspace.suites}
                  runs={workspace.runs}
                  refresh={refresh}
                />
              )}
              {view === "Audit trail" && (
                <section className="panel">
                  <div className="section-head">
                    <div>
                      <h2>Project audit trail</h2>
                      <p>Bounded recent actions returned by the server.</p>
                    </div>
                    <button onClick={refresh}>↻ Refresh</button>
                  </div>
                  {workspace.audit.length ? (
                    <div className="audit-list">
                      {workspace.audit.map((entry, index) => (
                        <article key={index}>
                          <span className="audit-dot" />
                          <pre>{readable(entry)}</pre>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <Empty title="No recorded actions">Project actions will appear here as they are recorded.</Empty>
                  )}
                </section>
              )}
            </div>
          )}
        </main>
        <footer className="app-footer">
          <span>Scenario Evidence Kit</span>
          <span>Synthetic inputs. Explicit checks. Honest outcomes.</span>
        </footer>
      </div>
    </div>
  );
}
