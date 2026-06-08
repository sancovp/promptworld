/**
 * gymApi — client for PromptWorld's GYM MODULE (the additive specs layer). A SPEC is a unit of
 * work to build/measure (title + body), with a STATUS lifecycle (draft → active → measuring →
 * done/abandoned), a list of OBSERVATIONS/measurements, and a list of RESEARCH-RUNS (a specialist
 * agent dispatched against the spec, whose reply-excerpt is recorded back). Thin layer over the
 * server-side gym_specs JSON store (server/gym_specs.py, /api/gym-specs/*). DISTINCT from the
 * PromptGym agent registry (the specialists themselves) — this only persists spec records.
 */
export type GymStatus = "draft" | "active" | "measuring" | "done" | "abandoned";

export const GYM_STATUSES: GymStatus[] = ["draft", "active", "measuring", "done", "abandoned"];

export interface GymObservation {
  ts: string;
  text: string;
  metric: string | null;
}

export interface GymRun {
  ts: string;
  alias: string;
  request: string;
  reply_excerpt: string;
}

export interface GymPaper {
  id: string;
  ts: string;
  title: string;
  body: string;
  published: boolean;
}

export interface GymSpec {
  id: string;
  title: string;
  body: string;
  status: GymStatus;
  owner_alias: string;
  created_at: string;
  observations: GymObservation[];
  runs: GymRun[];
  assigned_agent: string;
  schedule: string | null;
  published: boolean;
  papers: GymPaper[];
}

async function jfetch(url: string, init?: RequestInit): Promise<any> {
  const r = await fetch(url, init);
  if (!r.ok) {
    let detail = `${r.status}`;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return r.json();
}

export async function listSpecs(status?: GymStatus, owner?: string): Promise<GymSpec[]> {
  const q = new URLSearchParams();
  if (status) q.set("status", status);
  if (owner) q.set("owner", owner);
  const qs = q.toString();
  const data = await jfetch(`/api/gym-specs${qs ? `?${qs}` : ""}`);
  return data.specs ?? [];
}

export async function getSpec(id: string): Promise<GymSpec> {
  return jfetch(`/api/gym-specs/${encodeURIComponent(id)}`);
}

export async function createSpec(
  title: string,
  body: string,
  owner_alias: string,
  assigned_agent?: string,
  schedule?: string,
): Promise<GymSpec> {
  const payload: Record<string, unknown> = { title, body, owner_alias };
  if (assigned_agent) payload.assigned_agent = assigned_agent;
  if (schedule) payload.schedule = schedule;
  return jfetch("/api/gym-specs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateSpec(
  id: string,
  patch: { status?: GymStatus; body?: string; title?: string; assigned_agent?: string; schedule?: string },
): Promise<GymSpec> {
  return jfetch(`/api/gym-specs/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

export async function observe(id: string, text: string, metric?: string): Promise<GymSpec> {
  return jfetch(`/api/gym-specs/${encodeURIComponent(id)}/observe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, metric: metric || null }),
  });
}

/** Dispatch a specialist (alias) against the spec with a request. Returns the updated spec + the
 *  full reply string (the server records only a 500-char excerpt onto the spec). The agent's live
 *  output also streams over /ws → the chatStore for that alias (surfaced via AgentWindow). */
export async function runResearch(
  id: string,
  alias: string,
  request: string,
): Promise<{ spec: GymSpec; reply: string }> {
  return jfetch(`/api/gym-specs/${encodeURIComponent(id)}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ alias, request }),
  });
}

/** Run the spec's ASSIGNED agent's research turn (it spawns a review subagent that empirically tests
 *  the idea and writes a research paper onto the spec). For a team-assigned spec the server skips and
 *  returns `{spec, skipped}`. */
export async function researchNow(
  id: string,
): Promise<{ spec: GymSpec; paper_added?: boolean; skipped?: string }> {
  return jfetch(`/api/gym-specs/${encodeURIComponent(id)}/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

/** Put the spec's research loop on a CRON schedule (e.g. "every:3600" or a crontab line). 400 for team. */
export async function scheduleSpec(
  id: string,
  schedule: string,
): Promise<{ spec: GymSpec; automation: any }> {
  return jfetch(`/api/gym-specs/${encodeURIComponent(id)}/schedule`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ schedule }),
  });
}

/** Stop the spec's scheduled research loop. */
export async function stopSchedule(id: string): Promise<{ spec: GymSpec; stopped: boolean }> {
  return jfetch(`/api/gym-specs/${encodeURIComponent(id)}/schedule/stop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

/** Add a research paper (markdown) onto the spec. */
export async function addPaper(id: string, title: string, body: string): Promise<GymSpec> {
  return jfetch(`/api/gym-specs/${encodeURIComponent(id)}/papers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, body }),
  });
}

/** Update a paper on the spec (title/body/published). */
export async function updatePaper(
  id: string,
  paperId: string,
  patch: { title?: string; body?: string; published?: boolean },
): Promise<GymSpec> {
  return jfetch(`/api/gym-specs/${encodeURIComponent(id)}/papers/${encodeURIComponent(paperId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

/** Publish / unpublish the whole spec. */
export async function publishSpec(id: string, published: boolean): Promise<GymSpec> {
  return jfetch(`/api/gym-specs/${encodeURIComponent(id)}/publish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ published }),
  });
}
