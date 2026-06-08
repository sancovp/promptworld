/**
 * groupTemplatesApi — client for the server-side GROUP templates (/api/group-templates).
 * A template captures a side-by-side agent arrangement: which agents, in what ORDER, with
 * each window's LABEL + COLOR. Persisted server-side (survives restart) — the maximum option.
 */
export interface GroupAgentConfig {
  alias: string;
  label: string;
  color: string;
}

export interface GroupTemplate {
  name: string;
  agents: GroupAgentConfig[];
}

export async function listTemplates(): Promise<GroupTemplate[]> {
  const r = await fetch("/api/group-templates");
  if (!r.ok) return [];
  const data = await r.json();
  return Array.isArray(data?.templates) ? data.templates : [];
}

export async function saveTemplate(t: GroupTemplate): Promise<GroupTemplate> {
  const r = await fetch("/api/group-templates", {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(t),
  });
  if (!r.ok) throw new Error(`save failed: ${r.status}`);
  return r.json();
}

export async function deleteTemplate(name: string): Promise<void> {
  await fetch(`/api/group-templates?name=${encodeURIComponent(name)}`, { method: "DELETE" });
}
