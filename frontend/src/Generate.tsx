import { useEffect, useRef, useState } from "react";
import { api, type Case, type Catalog } from "./api";
import { Badge, ErrorMessage } from "./ui";
export default function Generate({
  token,
  projectId,
  catalog,
  role,
  onCreated,
}: {
  token: string;
  projectId: string;
  catalog: Catalog;
  role: string;
  onCreated: (cases: Case[]) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [description, setDescription] = useState("");
  const [engine, setEngine] = useState("templates");
  const session = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    session.current = controller;
    return () => controller.abort();
  }, [projectId, token]);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const controller = session.current;
    if (!controller || controller.signal.aborted) return;
    setBusy(true);
    setError("");
    try {
      const cases = await api<Case[]>(
        "/generate",
        token,
        {
          project_id: projectId,
          engine,
          description,
          count: Number(data.get("count")),
          seed: Number(data.get("seed")),
          map_name: data.get("map"),
          ...(data.get("kind") ? { kind: data.get("kind") } : {}),
        },
        controller.signal,
      );
      if (!controller.signal.aborted) onCreated(cases);
    } catch (e) {
      if (!controller.signal.aborted) setError(String(e));
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  return (
    <div className="generate-layout">
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Describe a scenario</h2>
            <p>
              {engine === "templates"
                ? "Turn a driving situation into reproducible template variations."
                : "Draft structured scenarios with the configured OpenAI provider."}
            </p>
          </div>
          <Badge tone="positive">{engine === "templates" ? "TEMPLATE ENGINE" : "OPENAI PLANNER"}</Badge>
        </div>
        <form onSubmit={submit}>
          <label>
            Generation engine
            <select value={engine} onChange={(e) => setEngine(e.target.value)}>
              <option value="templates">Offline deterministic templates</option>
              <option value="openai" disabled={!catalog.openai_configured || role !== "owner"}>
                OpenAI planner · optional paid provider
                {!catalog.openai_configured ? " · not configured" : role !== "owner" ? " · owner only" : ""}
              </option>
            </select>
          </label>
          <label>
            Scenario description
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="A car cuts in ahead of the ego vehicle in heavy rain…"
              rows={6}
              required
              maxLength={10000}
            />
          </label>
          <small>
            {engine === "templates"
              ? "English and Vietnamese keywords supported. This is bounded template generation."
              : "Sends your description to the configured provider and may incur charges. Model output is not guaranteed deterministic by the seed. Review every result."}
          </small>
          <div className="field-grid">
            <label>
              Map
              <select name="map">
                {catalog.maps.map((m) => (
                  <option key={m.name}>{m.name}</option>
                ))}
              </select>
            </label>
            <label>
              Scenario kind
              <select name="kind">
                <option value="">Infer from description</option>
                {catalog.kinds.map((k) => (
                  <option key={k} value={k}>
                    {k.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Variations
              <input name="count" type="number" min={1} max={20} defaultValue={3} required />
            </label>
            <label>
              Random seed
              <input name="seed" type="number" min={0} max={2147483647} defaultValue={42} required />
            </label>
          </div>
          <ErrorMessage error={error} />
          <div className="form-footer">
            <span>
              {engine === "templates"
                ? "Same inputs. Reproducible scenarios."
                : "Model drafts require validation and review."}
            </span>
            <button className="primary" disabled={busy || !projectId}>
              {busy ? "Generating…" : "Generate cases ↗"}
            </button>
          </div>
        </form>
      </section>
      <aside className="guide">
        <p className="eyebrow">A GOOD STARTING POINT</p>
        <h2>Make the situation specific.</h2>
        <p>Describe the actor, the maneuver, and the conditions. Review the generated parameters before approval.</p>
        <div className="example">
          <Badge>EXAMPLE · TIẾNG VIỆT</Badge>
          <p>“Người đi bộ băng qua đường trước xe ego trong sương mù.”</p>
          <button
            className="text-button"
            onClick={() => setDescription("Người đi bộ băng qua đường trước xe ego trong sương mù.")}
          >
            Use this description ↗
          </button>
        </div>
        <div className="notice">
          <strong>Synthetic environment</strong>
          <p>
            Demo maps are illustrative. An offline PASS does not confirm map compatibility, XSD conformance, or driving
            safety.
          </p>
        </div>
      </aside>
    </div>
  );
}
