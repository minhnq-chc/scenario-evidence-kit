export type User = { id: string; name: string; role: string };
export type Scenario = {
  id: string;
  title: string;
  description: string;
  map_name: string;
  kind: string;
  seed: number;
  duration_s: number;
  weather: string;
  ego_speed_mps: number;
  actors: { id: string; kind: string; speed_mps: number; start_x_m: number; start_y_m: number }[];
  parameters: Record<string, unknown>;
};
export type Validation = {
  status: string;
  checks: { name: string; status: string; message: string }[];
  fingerprint: string;
};
export type Case = {
  id: string;
  project_id: string;
  revision: number;
  title: string;
  status: string;
  scenario: Scenario;
  validation: Validation;
  created_at: string;
};
export type Project = { id: string; name: string };
export type Suite = { id: string; name: string; items: { case_id: string; revision: number; fingerprint: string }[] };
export type Run = {
  id: string;
  suite_id: string;
  mode: string;
  status: string;
  created_at: string;
  results: unknown[];
  error?: string;
};
export type Sample = { t: number; ego_x: number; ego_y: number; actor_x: number; actor_y: number };
export type Catalog = {
  maps: { name: string; synthetic: boolean }[];
  kinds: string[];
  weather: string[];
  openai_configured?: boolean;
};
export function readable(value: unknown): string {
  return typeof value === "string" ? value : (JSON.stringify(value, null, 2) ?? "Unknown error");
}
export async function api<T>(path: string, token = "", body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(readable(payload.detail ?? payload));
  }
  return response.json();
}
export async function download(path: string, token: string, filename: string) {
  const response = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error(readable(await response.json().catch(() => response.statusText)));
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
