import { useEffect, useState } from "react";
import { api, type User } from "./api";
import { Badge, ErrorMessage } from "./ui";
export default function Auth({ onLogin }: { onLogin: (token: string, user: User) => void }) {
  const [initialized, setInitialized] = useState<boolean | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function check() {
    setError("");
    try {
      setInitialized((await api<{ initialized: boolean }>("/auth/status")).initialized);
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => {
    void check();
  }, []);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      const result = await api<{ token: string; user: User }>(initialized ? "/auth/login" : "/auth/bootstrap", "", {
        name: data.get("name"),
        password: data.get("password"),
      });
      onLogin(result.token, result.user);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-shell">
      <section className="auth-story">
        <div className="wordmark">
          <span className="brand-icon">
            S<span>↗</span>
          </span>{" "}
          Scenario
          <br />
          Evidence Kit
        </div>
        <div>
          <Badge tone="light">DETERMINISTIC BY DESIGN</Badge>
          <h1>
            From scenario
            <br />
            to evidence.
          </h1>
          <p>Build reproducible driving scenarios. Inspect every revision. Keep a clear record of what was checked.</p>
          <div className="auth-steps">
            <span>01 / Generate</span>
            <span>02 / Review</span>
            <span>03 / Record</span>
          </div>
        </div>
        <small>OFFLINE FIRST · SIMULATION EXPLICIT</small>
      </section>
      <section className="auth-form">
        <p className="eyebrow">YOUR LOCAL WORKBENCH</p>
        <h2>{initialized === false ? "Create your workspace" : "Welcome to the workbench"}</h2>
        <p className="subtitle">
          {initialized === false
            ? "Set up the first owner account. There are no default credentials."
            : "Sign in to continue your scenario work."}
        </p>
        <ErrorMessage error={error} />
        {initialized === null ? (
          <button onClick={check}>Retry connection</button>
        ) : (
          <form onSubmit={submit}>
            <label>
              Account name
              <input name="name" autoComplete="username" required maxLength={100} />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete={initialized ? "current-password" : "new-password"}
                minLength={initialized ? undefined : 12}
                required
              />
            </label>
            {!initialized && <small>Use at least 12 characters.</small>}
            <button className="primary wide" disabled={busy}>
              {busy ? "Connecting…" : initialized ? "Open workbench →" : "Create owner account →"}
            </button>
          </form>
        )}
        <p className="auth-note">
          Synthetic maps and offline checks are clearly distinguished from actual simulator execution.
        </p>
      </section>
    </main>
  );
}
