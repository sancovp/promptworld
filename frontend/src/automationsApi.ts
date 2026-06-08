/**
 * automationsApi — client for PromptWorld's CRONS + per-agent HEARTBEAT (V2 (f)). These are a thin
 * layer over CAVE's REAL automation engine (the server reuses `pw.automation_registry` + CAVEAgent's
 * 60s Heart tick that fires due CronAutomations). An automation = a prompt fired at a target agent on
 * a schedule (default interval "every:N"); firing POSTs to the agent's own endpoint (a real turn).
 */
export interface Automation {
  name: string;
  description: string;
  schedule: string; // "every:300" or a cron expr
  enabled: boolean;
  alias: string | null; // target agent
  prompt: string | null;
  type: string;
  run_count: number;
  last_run: string | null;
}

export interface Heartbeat {
  alias: string;
  enabled: boolean;
  interval_seconds: number;
  prompt: string;
}

async function jpost(url: string, body?: unknown): Promise<any> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
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

export interface ScheduleEvent {
  time: string;
  name: string;
  schedule: string;
}

export async function listAutomations(): Promise<Automation[]> {
  const r = await fetch("/api/automations");
  if (!r.ok) throw new Error(`list automations: ${r.status}`);
  return (await r.json()).automations ?? [];
}

export async function getAutomationView(days = 7): Promise<ScheduleEvent[]> {
  const r = await fetch(`/api/automations/view?days=${days}`);
  if (!r.ok) throw new Error(`view: ${r.status}`);
  return (await r.json()).events ?? [];
}

export async function createAutomation(spec: {
  name: string;
  alias: string;
  prompt: string;
  interval_seconds?: number;
  schedule?: string;
  description?: string;
  enabled?: boolean;
}): Promise<Automation> {
  return (await jpost("/api/automations", spec)).automation;
}

export async function setAutomationEnabled(name: string, enabled: boolean): Promise<Automation> {
  return (await jpost(`/api/automations/${encodeURIComponent(name)}/${enabled ? "enable" : "disable"}`)).automation;
}

export async function fireAutomation(name: string): Promise<any> {
  return (await jpost(`/api/automations/${encodeURIComponent(name)}/fire`)).fired;
}

export async function deleteAutomation(name: string): Promise<boolean> {
  const r = await fetch(`/api/automations/${encodeURIComponent(name)}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`delete: ${r.status}`);
  return (await r.json()).deleted;
}

export async function getHeartbeat(alias: string): Promise<Heartbeat> {
  const r = await fetch(`/api/heartbeat/${encodeURIComponent(alias)}`);
  if (!r.ok) throw new Error(`heartbeat get: ${r.status}`);
  return r.json();
}

export async function setHeartbeat(
  alias: string,
  cfg: { enabled: boolean; interval_seconds: number; prompt: string },
): Promise<Heartbeat> {
  const r = await fetch(`/api/heartbeat/${encodeURIComponent(alias)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cfg),
  });
  if (!r.ok) throw new Error(`heartbeat put: ${r.status}`);
  return r.json();
}
