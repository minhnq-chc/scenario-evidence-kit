import { useState } from "react";
import { api, readable, type Case, type Run, type Suite } from "./api";
import { Badge, Empty, ErrorMessage, Status } from "./ui";
export default function Executions({
  token,
  projectId,
  cases,
  suites,
  runs,
  refresh,
}: {
  token: string;
  projectId: string;
  cases: Case[];
  suites: Suite[];
  runs: Run[];
  refresh: () => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [detail, setDetail] = useState<Run | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [requestKey, setRequestKey] = useState<string>(crypto.randomUUID());
  async function action(work: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await work();
      refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <ErrorMessage error={error} />
      {message && (
        <p role="status" className="success">
          {message}
        </p>
      )}
      <div className="execution-grid">
        <section className="panel">
          <div className="section-head">
            <div>
              <p className="eyebrow">01 / SNAPSHOT</p>
              <h2>Build an approved suite</h2>
            </div>
            <Badge>{suites.length} SUITES</Badge>
          </div>
          <p className="muted">A suite snapshots approved revisions and their fingerprints.</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const name = new FormData(form).get("name");
              void action(async () => {
                await api("/suites", token, { project_id: projectId, name, case_ids: selected });
                setSelected([]);
                form.reset();
                setMessage("Suite created from approved revisions.");
              });
            }}
          >
            <label>
              Suite name
              <input name="name" placeholder="Wet weather regression" required maxLength={150} />
            </label>
            <fieldset>
              <legend>Approved scenarios</legend>
              <div className="approved-cases">
                {cases.filter((c) => c.status === "approved").length ? (
                  cases
                    .filter((c) => c.status === "approved")
                    .map((c) => (
                      <label className="checkbox-row" key={c.id}>
                        <input
                          type="checkbox"
                          checked={selected.includes(c.id)}
                          onChange={(e) =>
                            setSelected((s) => (e.target.checked ? [...s, c.id] : s.filter((id) => id !== c.id)))
                          }
                        />
                        <span>
                          {c.title}
                          <small>Revision {c.revision}</small>
                        </span>
                      </label>
                    ))
                ) : (
                  <p className="muted">Approve a scenario in the library to include it here.</p>
                )}
              </div>
            </fieldset>
            <button className="primary" disabled={busy || selected.length === 0}>
              Create suite · {selected.length} selected
            </button>
          </form>
        </section>
        <section className="panel">
          <div className="section-head">
            <div>
              <p className="eyebrow">02 / EXECUTE</p>
              <h2>Run a suite</h2>
            </div>
            <Badge>EXPLICIT MODE</Badge>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              void action(async () => {
                const run = await api<Run>("/runs", token, {
                  suite_id: data.get("suite"),
                  mode: data.get("mode"),
                  idempotency_key: requestKey,
                });
                setDetail(run);
                setRequestKey(crypto.randomUUID());
                setMessage("Run request recorded. Inspect its actual status below.");
              });
            }}
          >
            <label>
              Suite
              <select name="suite" required defaultValue="">
                <option value="" disabled>
                  Select a suite
                </option>
                {suites.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} · {s.items.length} cases
                  </option>
                ))}
              </select>
            </label>
            <label>
              Execution mode
              <select name="mode">
                <option value="offline">Offline evidence checks</option>
                <option value="carla">CARLA · configured adapter required</option>
              </select>
            </label>
            <label>
              Idempotency key
              <div className="inline-field">
                <input value={requestKey} onChange={(e) => setRequestKey(e.target.value)} required />
                <button
                  type="button"
                  onClick={() => setRequestKey(crypto.randomUUID())}
                  aria-label="Generate a new idempotency key"
                >
                  ↻
                </button>
              </div>
            </label>
            <div className="notice">
              <strong>Offline means simulation NOT_RUN.</strong>
              <p>
                CARLA requires an explicitly configured executable. A missing adapter returns an error; no simulation
                results are invented.
              </p>
            </div>
            <button className="primary" disabled={busy || !suites.length}>
              {busy ? "Submitting…" : "Create run ↗"}
            </button>
          </form>
        </section>
      </div>
      <section className="panel run-panel">
        <div className="section-head">
          <div>
            <p className="eyebrow">EXECUTION RECORD</p>
            <h2>Recent runs</h2>
          </div>
          <button onClick={refresh}>↻ Refresh</button>
        </div>
        {runs.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Mode</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <button
                        className="text-button"
                        disabled={busy}
                        onClick={() => void action(async () => setDetail(await api<Run>(`/runs/${r.id}`, token)))}
                      >
                        {r.id.slice(0, 14)} ↗
                      </button>
                    </td>
                    <td>{r.mode}</td>
                    <td>
                      <Status value={r.status} />
                    </td>
                    <td>{new Date(r.created_at).toLocaleString()}</td>
                    <td>
                      {["running", "queued"].includes(r.status) && (
                        <button
                          disabled={busy}
                          onClick={() =>
                            void action(async () => setDetail(await api<Run>(`/runs/${r.id}/cancel`, token, {})))
                          }
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="No runs recorded">Create a suite and choose an execution mode to begin.</Empty>
        )}
        {detail && (
          <section className="run-detail">
            <div className="section-head">
              <h3>
                Run details <Status value={detail.status} />
              </h3>
              <button onClick={() => setDetail(null)} aria-label="Close run details">
                Close ×
              </button>
            </div>
            <code>{detail.id}</code>
            {detail.error && <ErrorMessage error={readable(detail.error)} />}
            <pre>{JSON.stringify(detail.results, null, 2)}</pre>
            {detail.mode === "offline" && <Badge>SIMULATION NOT RUN</Badge>}
          </section>
        )}
      </section>
    </>
  );
}
