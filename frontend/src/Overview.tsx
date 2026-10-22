import type { Case } from "./api";
import { Badge, Empty } from "./ui";
export default function Overview({
  metrics,
  cases,
  setView,
}: {
  metrics: Record<string, number>;
  cases: Case[];
  setView: (view: string) => void;
}) {
  return (
    <>
      <div className="metric-grid">
        {[
          { label: "Scenarios", value: metrics.cases, note: "Latest revisions", icon: "▤" },
          { label: "Approved", value: metrics.approved, note: "Ready for suite snapshots", icon: "✓" },
          {
            label: "Offline checks passed",
            value: metrics.offline_pass,
            note: "Supported subset only",
            icon: "◈",
          },
          {
            label: "Simulation passes",
            value: metrics.simulation_pass,
            note: `${metrics.simulation_not_run ?? 0} not run`,
            icon: "▷",
          },
        ].map((m) => (
          <section className="metric" key={m.label}>
            <div>
              <span>{m.label}</span>
              <span className="metric-icon">{m.icon}</span>
            </div>
            <strong>
              {m.value ?? 0}
              <small>{m.label === "Simulation passes" ? "actual results" : ""}</small>
            </strong>
            <p>{m.note}</p>
          </section>
        ))}
      </div>
      <div className="overview-grid">
        <section className="welcome-card">
          <p className="eyebrow">REPRODUCIBLE SCENARIOS. TRACEABLE EVIDENCE.</p>
          <h2>
            Define the situation.
            <br />
            Inspect the details.
          </h2>
          <p>
            Generate bounded templates, review every parameter, and keep your evidence attached to an immutable
            revision.
          </p>
          <button className="primary" onClick={() => setView("Generate")}>
            Create a scenario ↗
          </button>
          <div className="welcome-track" aria-hidden="true">
            <span className="track-line" />
            <span className="track-car one" />
            <span className="track-car two" />
          </div>
        </section>
        <section className="panel workflow">
          <p className="eyebrow">YOUR WORKFLOW</p>
          {[
            {
              n: "01",
              title: "Generate & inspect",
              text: "English or Vietnamese input. Deterministic templates.",
              view: "Generate",
            },
            {
              n: "02",
              title: "Review a revision",
              text: "Check parameters, preview the trajectory, approve.",
              view: "Case library",
            },
            {
              n: "03",
              title: "Collect the evidence",
              text: "Snapshot suites. Record offline or simulator outcomes.",
              view: "Suites & runs",
            },
          ].map((step) => (
            <button key={step.n} onClick={() => setView(step.view)}>
              <span>{step.n}</span>
              <div>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </div>
              <b>↗</b>
            </button>
          ))}
        </section>
      </div>
      <section className="panel">
        <div className="section-head">
          <div>
            <p className="eyebrow">PROJECT LIBRARY</p>
            <h2>Recent scenarios</h2>
          </div>
          <button className="text-button" onClick={() => setView("Case library")}>
            View library →
          </button>
        </div>
        {cases.length ? (
          <div className="recent-grid">
            {cases.slice(0, 3).map((c) => (
              <button className="recent-case" key={c.id} onClick={() => setView("Case library")}>
                <Badge>{c.status}</Badge>
                <h3>{c.title}</h3>
                <p>
                  {c.scenario.map_name} · rev {c.revision}
                </p>
                <span>Inspect scenario ↗</span>
              </button>
            ))}
          </div>
        ) : (
          <Empty title="A clean starting point">Your generated and imported scenarios will appear here.</Empty>
        )}
      </section>
      <p className="footnote">
        Demo maps are synthetic. Offline validation checks a supported subset; it does not establish ADS safety, XSD
        conformance, or simulator compatibility.
      </p>
    </>
  );
}
