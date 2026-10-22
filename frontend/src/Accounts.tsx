import { useState } from "react";
import { api } from "./api";
import { Badge, ErrorMessage } from "./ui";
export default function Accounts({ token }: { token: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api("/auth/users", token, {
        name: data.get("name"),
        password: data.get("password"),
        role: data.get("role"),
      });
      setMessage(`Account created for ${data.get("name")}.`);
      form.reset();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel account-panel">
      <div className="section-head">
        <div>
          <h2>Create a local account</h2>
          <p>Authors prepare scenarios. Reviewers can approve or reject revisions.</p>
        </div>
        <Badge>OWNER ONLY</Badge>
      </div>
      <ErrorMessage error={error} />
      {message && (
        <p className="success" role="status">
          {message}
        </p>
      )}
      <form onSubmit={submit}>
        <label>
          Account name
          <input name="name" autoComplete="off" required maxLength={100} />
        </label>
        <label>
          Initial password
          <input name="password" type="password" autoComplete="new-password" minLength={12} required />
        </label>
        <small>At least 12 characters. No password is generated or displayed.</small>
        <label>
          Role
          <select name="role">
            <option value="author">Author</option>
            <option value="reviewer">Reviewer</option>
          </select>
        </label>
        <button className="primary" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
    </section>
  );
}
