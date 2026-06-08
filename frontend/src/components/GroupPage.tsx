import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Save, Trash2, X } from "lucide-react";
import { AgentWindow } from "./AgentWindow";
import { ALL_AGENTS, agentColor } from "../agents";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  listTemplates,
  saveTemplate,
  deleteTemplate,
  type GroupAgentConfig,
  type GroupTemplate,
} from "../groupTemplatesApi";

/**
 * GROUP page — SELECT ANY subset of the 8 agents → spawn their chat windows SIDE BY SIDE.
 * Each window's ORDER, COLOR, and LABEL are editable, and the whole arrangement saves/reloads
 * as a NAMED template (persisted server-side via /api/group-templates).
 */
export function GroupPage() {
  const [configs, setConfigs] = useState<GroupAgentConfig[]>([]);
  const [templates, setTemplates] = useState<GroupTemplate[]>([]);
  const [saveName, setSaveName] = useState("");
  const [loaded, setLoaded] = useState<string>("");

  const refresh = useCallback(async () => {
    setTemplates(await listTemplates());
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);

  const selected = new Set(configs.map((c) => c.alias));

  function toggle(alias: string) {
    setConfigs((prev) =>
      prev.some((c) => c.alias === alias)
        ? prev.filter((c) => c.alias !== alias)
        // label defaults EMPTY → the window falls back to the agent's persona name (from the live
        // profile config); the field is an OPTIONAL per-window override, not a hardcoded name.
        : [...prev, { alias, label: "", color: agentColor(alias) }],
    );
  }
  function update(alias: string, patch: Partial<GroupAgentConfig>) {
    setConfigs((prev) => prev.map((c) => (c.alias === alias ? { ...c, ...patch } : c)));
  }
  function move(idx: number, dir: -1 | 1) {
    setConfigs((prev) => {
      const next = [...prev];
      const j = idx + dir;
      if (j < 0 || j >= next.length) return prev;
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    });
  }

  async function onSave() {
    const name = saveName.trim();
    if (!name || configs.length === 0) return;
    await saveTemplate({ name, agents: configs });
    setLoaded(name);
    setSaveName("");
    await refresh();
  }
  function onLoad(name: string) {
    const t = templates.find((x) => x.name === name);
    if (!t) return;
    setLoaded(name);
    setConfigs(
      t.agents.map((a) => ({
        alias: a.alias,
        label: a.label || "", // empty → window falls back to the agent's persona name
        color: a.color || agentColor(a.alias),
      })),
    );
  }
  async function onDelete() {
    if (!loaded) return;
    await deleteTemplate(loaded);
    setLoaded("");
    await refresh();
  }

  return (
    <div className="page page-group">
      {/* --- controls: agent multi-select + template save/load --- */}
      <div className="group-controls">
        <div className="group-pick">
          <span className="page-toolbar-label">Agents</span>
          <div className="group-chips">
            {ALL_AGENTS.map((a) => (
              <button
                key={a.alias}
                className={cn("group-chip", selected.has(a.alias) && "selected")}
                style={selected.has(a.alias) ? { borderColor: a.color, color: a.color } : undefined}
                onClick={() => toggle(a.alias)}
              >
                {a.label}
              </button>
            ))}
          </div>
        </div>
        <div className="group-template-bar">
          <Select value={loaded} onValueChange={onLoad}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Load template…" />
            </SelectTrigger>
            <SelectContent>
              {templates.length === 0 ? (
                <SelectItem value="__none" disabled>
                  No templates yet
                </SelectItem>
              ) : (
                templates.map((t) => (
                  <SelectItem key={t.name} value={t.name}>
                    {t.name}
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={onDelete} disabled={!loaded} title="Delete template">
            <Trash2 size={14} />
          </Button>
          <Input
            className="w-[180px]"
            placeholder="Template name"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
          />
          <Button size="sm" onClick={onSave} disabled={!saveName.trim() || configs.length === 0}>
            <Save size={14} /> Save
          </Button>
        </div>
      </div>

      {/* --- per-window settings: order / color / label --- */}
      {configs.length > 0 && (
        <div className="group-settings">
          {configs.map((c, i) => (
            <div key={c.alias} className="group-setting-row">
              <span className="group-order">{i + 1}</span>
              <input
                type="color"
                className="group-color"
                value={c.color}
                title="Window color"
                onChange={(e) => update(c.alias, { color: e.target.value })}
              />
              <Input
                className="group-label"
                value={c.label}
                onChange={(e) => update(c.alias, { label: e.target.value })}
              />
              <span className="group-alias">{c.alias}</span>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => move(i, -1)}
                disabled={i === 0}
                title="Move left"
              >
                <ArrowLeft size={14} />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => move(i, 1)}
                disabled={i === configs.length - 1}
                title="Move right"
              >
                <ArrowRight size={14} />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => toggle(c.alias)}
                title="Remove"
              >
                <X size={14} />
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* --- the side-by-side windows (in `configs` order) --- */}
      <div className="group-windows" style={{ ["--n" as any]: Math.max(configs.length, 1) }}>
        {configs.length === 0 ? (
          <div className="group-empty">
            Select agents above to spawn their chat windows side by side.
          </div>
        ) : (
          configs.map((c) => (
            <div key={c.alias} className="group-window-cell">
              <AgentWindow alias={c.alias} title={c.label} color={c.color} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
