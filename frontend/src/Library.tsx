import { useEffect, useRef, useState } from "react";
import { api, download, type Case, type Sample, type User } from "./api";
import { Badge, Empty, ErrorMessage, Status } from "./ui";
import Trajectory from "./Trajectory";
export default function Library({
  token,
  projectId,
  cases,
  user,
  refresh,
}: {
  token: string;
  projectId: string;
  cases: Case[];
  user: User;
  refresh: () => void;
}) {
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<Case | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [editor, setEditor] = useState("");
  const [tab, setTab] = useState("Overview");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState("");
  const [query, setQuery] = useState("");
  const [revisionKey, setRevisionKey] = useState(0);
  const [message, setMessage] = useState("");
  const editorCase = useRef("");
  const actionResult = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (message) actionResult.current?.focus();
  }, [message]);
  const activeId = selected || cases[0]?.id || "";
  useEffect(() => {
    if (!activeId) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setDetail((current) => (current?.id === activeId ? current : null));
    Promise.all([
      api<Case>(`/cases/${activeId}`, token, undefined, controller.signal),
      api<Sample[]>(`/cases/${activeId}/preview`, token, undefined, controller.signal),
    ])
      .then(([item, preview]) => {
        if (controller.signal.aborted) return;
        setDetail(item);
        if (editorCase.current !== item.id) {
          setEditor(JSON.stringify(item.scenario, null, 2));
          editorCase.current = item.id;
        }
        setSamples(preview);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(String(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [activeId, token, revisionKey]);
  async function downloadFile(path: string, filename: string) {
    setError("");
    try {
      await download(path, token, filename);
    } catch (e) {
      setError(String(e));
    }
  }
  async function action(work: () => Promise<unknown>, success = "") {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await work();
      if (success) setMessage(success);
      refresh();
      setRevisionKey((k) => k + 1);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function importFile(file?: File) {
    if (!file) return;
    if (file.size > 1000000) {
      setError("XML file must be smaller than 1 MB.");
      return;
    }
    await action(async () => {
      const result = await api<Case>("/cases/import", token, { project_id: projectId, xml: await file.text() });
      setSelected(result.id);
    }, "XML imported as a draft.");
  }
  const filtered = cases.filter((c) => `${c.title} ${c.status}`.toLowerCase().includes(query.toLowerCase()));
  return (
    <>
      <div className="library-toolbar">
        <label className="search">
          <span className="sr-only">Search cases</span>
          <input placeholder="Search scenarios…" value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <label className={`file-button ${busy ? "disabled" : ""}`}>
          Import XML
          <input
            type="file"
            accept=".xosc,.xml"
            disabled={busy}
            onChange={(e) => {
              void importFile(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </label>
      </div>
      <ErrorMessage error={error} />
      {message && (
        <p role="status" className="success" tabIndex={-1} ref={actionResult}>
          {message}
        </p>
      )}
      <div className="library-layout">
        <section className="case-list" aria-label="Scenario library">
          <div className="list-heading">
            SCENARIOS <span>{cases.length.toString().padStart(2, "0")}</span>
          </div>
          {filtered.length ? (
            filtered.map((item) => (
              <button
                className={`case-row ${activeId === item.id ? "selected" : ""}`}
                key={item.id}
                onClick={() => {
                  setSelected(item.id);
                  setNote("");
                  setTab("Overview");
                  setMessage("");
                }}
              >
                <span className="case-kicker">
                  REV {item.revision} <Status value={item.status} />
                </span>
                <strong>{item.title}</strong>
                <span className="muted">
                  {item.scenario.kind.replaceAll("_", " ")} · seed {item.scenario.seed}
                </span>
              </button>
            ))
          ) : (
            <Empty title="No scenarios yet">Generate a scenario or import a supported XML file.</Empty>
          )}
        </section>
        <section className="panel case-detail">
          {loading && !detail ? (
            <p role="status">Loading scenario…</p>
          ) : detail ? (
            <>
              <div className="section-head">
                <div>
                  <p className="eyebrow">SCENARIO / REVISION {detail.revision}</p>
                  <h2>{detail.title}</h2>
                </div>
                <Status value={detail.status} />
              </div>
              <div className="tabs" aria-label="Scenario sections">
                {["Overview", "Validation", "JSON revision"].map((t) => (
                  <button
                    key={t}
                    aria-pressed={tab === t}
                    className={tab === t ? "active" : ""}
                    onClick={() => setTab(t)}
                  >
                    {t}
                  </button>
                ))}
              </div>
              {tab === "Overview" && (
                <>
                  <div className="scenario-meta">
                    <span>
                      MAP<strong>{detail.scenario.map_name}</strong>
                    </span>
                    <span>
                      WEATHER<strong>{detail.scenario.weather}</strong>
                    </span>
                    <span>
                      DURATION<strong>{detail.scenario.duration_s} s</strong>
                    </span>
                    <span>
                      EGO SPEED<strong>{detail.scenario.ego_speed_mps} m/s</strong>
                    </span>
                  </div>
                  <Trajectory key={detail.id + detail.revision} samples={samples} />
                  <p className="description">{detail.scenario.description}</p>
                  <div className="notice">
                    <Badge>OFFLINE SUBSET</Badge>
                    <p>
                      The preview is illustrative. Validation and export do not certify ADS safety or arbitrary
                      simulator compatibility.
                    </p>
                  </div>
                  <div className="download-row">
                    <button
                      disabled={busy}
                      onClick={() => void downloadFile(`/cases/${detail.id}/xosc`, `${detail.id}.xosc`)}
                    >
                      ↓ OpenSCENARIO XML
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => void downloadFile(`/cases/${detail.id}/report`, `${detail.id}-evidence.json`)}
                    >
                      ↓ Evidence JSON
                    </button>
                  </div>
                </>
              )}
              {tab === "Validation" && (
                <>
                  <div className="validation-summary">
                    <Status value={detail.validation.status} />
                    <p>Offline supported-subset checks. No XSD or safety certification.</p>
                  </div>
                  <div className="checks">
                    {detail.validation.checks.map((c, i) => (
                      <div key={i}>
                        <Status value={c.status} />
                        <span>
                          <strong>{c.name}</strong>
                          <small>{c.message}</small>
                        </span>
                      </div>
                    ))}
                  </div>
                  <label>
                    Input fingerprint<code className="fingerprint">{detail.validation.fingerprint}</code>
                  </label>
                </>
              )}
              {tab === "JSON revision" && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void action(async () => {
                      let scenario: unknown;
                      try {
                        scenario = JSON.parse(editor);
                      } catch {
                        throw new Error("Enter valid JSON before saving.");
                      }
                      await api(`/cases/${detail.id}/revisions`, token, { scenario });
                    }, "New draft revision saved. Previous revision retained.");
                  }}
                >
                  <label>
                    Scenario JSON
                    <textarea
                      className="code-editor"
                      rows={19}
                      value={editor}
                      onChange={(e) => setEditor(e.target.value)}
                      spellCheck={false}
                    />
                  </label>
                  <p className="muted">Saving creates a new draft. Previous revisions remain immutable.</p>
                  <button className="primary" disabled={busy}>
                    Save new draft revision
                  </button>
                </form>
              )}
              {["owner", "reviewer"].includes(user.role) && (
                <form className="review" onSubmit={(e) => e.preventDefault()}>
                  <div className="section-head">
                    <h3>Review this revision</h3>
                    <Badge>OWNER / REVIEWER</Badge>
                  </div>
                  <label>
                    Review note
                    <textarea
                      rows={2}
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder="Record your review rationale…"
                    />
                  </label>
                  <div className="review-actions">
                    <button
                      className="danger-outline"
                      disabled={busy || detail.status !== "draft"}
                      onClick={() =>
                        void action(
                          () => api(`/cases/${detail.id}/review`, token, { decision: "rejected", note }),
                          "Revision rejected.",
                        )
                      }
                    >
                      Reject
                    </button>
                    <button
                      className="primary"
                      disabled={busy || detail.status !== "draft" || detail.validation.status !== "PASS"}
                      onClick={() =>
                        void action(
                          () => api(`/cases/${detail.id}/review`, token, { decision: "approved", note }),
                          "Revision approved.",
                        )
                      }
                    >
                      Approve revision ✓
                    </button>
                  </div>
                </form>
              )}
            </>
          ) : (
            <Empty title="Choose a scenario">Inspect the trajectory, validation checks and revision history.</Empty>
          )}
        </section>
      </div>
    </>
  );
}
