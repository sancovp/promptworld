/**
 * agents — the canonical roster of the 8 PromptWorld agents (CEO + 7 PromptGym specialists).
 * Single source of truth for aliases + display labels + default accent colors, shared by the
 * gallery seed (App), the Specialist selector, and the Group multi-select.
 */
export interface AgentDef {
  alias: string;
  label: string;
  color: string; // default accent (group windows can override per-template)
}

export const CEO: AgentDef = { alias: "ceo", label: "CEO", color: "#1d4ed8" };

// the 7 PromptGym component types (the scoped-AIOS specialists). `label` is only a generic FALLBACK
// shown before the profile loads — the real DISPLAY NAME comes from the hot-reloading persona config
// (promptgym/agent_personas.json) via the profile API (useAgentProfile), so names are NOT hardcoded
// here. The profile editor (#45) lets a user override name+avatar; Isaac re-skins the theme by editing
// the JSON config + each persona's promptgym/<type>/CLAUDE.md.
export const SPECIALISTS: AgentDef[] = [
  { alias: "skill", label: "Skill", color: "#2a9c68" },
  { alias: "mcp", label: "MCP", color: "#a855f7" },
  { alias: "harness", label: "Harness", color: "#f59e0b" },
  { alias: "operating_system", label: "Operating System", color: "#ef4444" },
  { alias: "prompt", label: "Prompt", color: "#06b6d4" },
  { alias: "team", label: "Team", color: "#ec4899" },
  { alias: "cave_team", label: "Cave Team", color: "#e3b341" },
  { alias: "workflow", label: "Workflow", color: "#84cc16" },
];

export const ALL_AGENTS: AgentDef[] = [CEO, ...SPECIALISTS];

const BY_ALIAS = new Map(ALL_AGENTS.map((a) => [a.alias, a]));

export function agentLabel(alias: string): string {
  return BY_ALIAS.get(alias)?.label ?? alias;
}

export function agentColor(alias: string): string {
  return BY_ALIAS.get(alias)?.color ?? "#232a32";
}

/**
 * agentPromptPath — the agent's editable PROMPT file, RELATIVE to the workspace root (V2 (c):
 * the prompt IS a CLAUDE.md edited directly in the Monaco workbench, not a prompt-block system).
 * The CEO's prompt is its persona append (agents/engineer-ceo.md); each gym specialist's prompt is
 * its scoped-AIOS CLAUDE.md (promptgym/<type>/CLAUDE.md). The profile editor's "Edit prompt" button
 * opens this path in the workbench (see editorBus). Workspace root = the CEO cwd = the instance dir.
 */
export function agentPromptPath(alias: string): string {
  if (alias === "ceo") return "agents/engineer-ceo.md";
  return `promptgym/${alias}/CLAUDE.md`;
}
