import { useState } from "react";
import type { Sample } from "./api";
export default function Trajectory({ samples }: { samples: Sample[] }) {
  const [index, setIndex] = useState(0);
  const current = samples[Math.min(index, samples.length - 1)];
  if (!current) return <p className="muted">No preview samples available.</p>;
  const xs = samples.flatMap((s) => [s.ego_x, s.actor_x]).filter(Number.isFinite);
  const ys = samples.flatMap((s) => [s.ego_y, s.actor_y]).filter(Number.isFinite);
  const xmin = Math.min(...xs, 0) - 10,
    xmax = Math.max(...xs, 50) + 10,
    ymin = Math.min(...ys, -5) - 2,
    ymax = Math.max(...ys, 5) + 2;
  const x = (v: number) => 30 + ((v - xmin) / (xmax - xmin)) * 640;
  const y = (v: number) => 180 - ((v - ymin) / (ymax - ymin)) * 150;
  return (
    <div className="trajectory">
      <div className="trajectory-top">
        <span>
          <i className="dot ego" /> Ego vehicle <i className="dot actor" /> Challenger
        </span>
        <span>{current.t.toFixed(1)} s</span>
      </div>
      <svg
        viewBox="0 0 700 210"
        role="img"
        aria-label="Illustrative kinematic trajectory of the ego vehicle and first challenger, not a simulation"
      >
        <defs>
          <pattern id="grid" width="35" height="30" patternUnits="userSpaceOnUse">
            <path d="M 35 0 L 0 0 0 30" fill="none" stroke="currentColor" strokeWidth=".4" />
          </pattern>
        </defs>
        <rect width="700" height="210" fill="url(#grid)" />
        <path d={`M 0 ${y(0)} H 700 M 0 ${y(3.5)} H 700`} stroke="currentColor" opacity=".3" strokeDasharray="8 8" />
        <polyline
          points={samples.map((s) => `${x(s.ego_x)},${y(s.ego_y)}`).join(" ")}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="2"
        />
        <polyline
          points={samples.map((s) => `${x(s.actor_x)},${y(s.actor_y)}`).join(" ")}
          fill="none"
          stroke="var(--amber)"
          strokeDasharray="4 4"
          strokeWidth="2"
        />
        <rect x={x(current.ego_x) - 9} y={y(current.ego_y) - 5} width="18" height="10" rx="3" fill="var(--accent)" />
        <circle cx={x(current.actor_x)} cy={y(current.actor_y)} r="6" fill="var(--amber)" />
      </svg>
      <label className="timeline">
        Preview time
        <input
          aria-label="Preview time"
          type="range"
          min={0}
          max={samples.length - 1}
          value={Math.min(index, samples.length - 1)}
          onChange={(e) => setIndex(Number(e.target.value))}
        />
      </label>
      <small>Illustrative 2D kinematics · first challenger only · not a CARLA result</small>
    </div>
  );
}
