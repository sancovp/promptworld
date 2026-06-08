import { useCallback, useEffect, useState } from "react";
import { Clock, Play, Power, Plus, Trash2, Repeat } from "lucide-react";
import { AgentAvatar } from "./AgentAvatar";
import { ALL_AGENTS, agentLabel } from "../agents";
import {
  listAutomations,
  createAutomation,
  setAutomationEnabled,
  fireAutomation,
  deleteAutomation,
  getHeartbeat,
  setHeartbeat,
  getAutomationView,
  type Automation,
  type Heartbeat,
  type ScheduleEvent,
} from "../automationsApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

/**
 * CronsPage (V2 (f)) — scheduled automations + per-agent HEARTBEAT, over CAVE's REAL automation engine
 * (the server reuses `pw.automation_registry` + CAVEAgent's 60s Heart tick). Each automation fires a
 * prompt at a target agent on an interval (a real turn). NO mock: create/enable/disable/fire/delete all
 * hit the live registry, and "Fire now" runs it immediately so you can confirm it actually fires.
 */
function fmtSchedule(s: string): string {
  if (s?.startsWith("every:")) {
    const n = parseInt(s.split(":")[1], 10);
    return Number.isFinite(n) ? `every ${n}s` : s;
  }
  return s;
}
function fmtWhen(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

export function CronsPage() {
  const [autos, setAutos] = useState<Automation[]>([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  // create form
  const [name, setName] = useState("");
  const [target, setTarget] = useState("ceo");
  const [schedMode, setSchedMode] = useState<"interval" | "cron">("interval");
  const [interval, setInterval] = useState(300);
  const [cronExpr, setCronExpr] = useState("0 3 * * *");
  const [prompt, setPrompt] = useState("");

  // upcoming-fires preview
  const [events, setEvents] = useState<ScheduleEvent[]>([]);

  // heartbeat
  const [hbAlias, setHbAlias] = useState("ceo");
  const [hb, setHb] = useState<Heartbeat | null>(null);

  const refresh = useCallback(async () => {
    try {
      setAutos(await listAutomations());
      try {
        setEvents(await getAutomationView(7));
      } catch {
        setEvents([]);
      }
    } catch (e: any) {
      setStatus("list error: " + e.message);
    }
  }, []);

  const loadHb = useCallback(async (alias: string) => {
    try {
      setHb(await getHeartbeat(alias));
    } catch (e: any) {
      setStatus("heartbeat error: " + e.message);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);
  useEffect(() => {
    loadHb(hbAlias);
  }, [hbAlias, loadHb]);

  const onCreate = async () => {
    const nm = name.trim();
    if (!nm || !prompt.trim()) return;
    setBusy(true);
    setStatus("");
    try {
      await createAutomation({
        name: nm,
        alias: target,
        prompt: prompt.trim(),
        ...(schedMode === "cron"
          ? { schedule: cronExpr.trim() }
          : { interval_seconds: interval }),
      });
      setName("");
      setPrompt("");
      setStatus(`created ${nm}`);
      await refresh();
    } catch (e: any) {
      setStatus("create error: " + e.message);
    }
    setBusy(false);
  };

  const onToggle = async (a: Automation) => {
    setBusy(true);
    try {
      await setAutomationEnabled(a.name, !a.enabled);
      await refresh();
    } catch (e: any) {
      setStatus("toggle error: " + e.message);
    }
    setBusy(false);
  };

  const onFire = async (a: Automation) => {
    setBusy(true);
    setStatus(`firing ${a.name}…`);
    try {
      const r = await fireAutomation(a.name);
      setStatus(`fired ${a.name}: ${JSON.stringify(r?.code_result ?? r)}`);
      await refresh();
    } catch (e: any) {
      setStatus("fire error: " + e.message);
    }
    setBusy(false);
  };

  const onDelete = async (a: Automation) => {
    setBusy(true);
    try {
      await deleteAutomation(a.name);
      await refresh();
      setStatus(`deleted ${a.name}`);
    } catch (e: any) {
      setStatus("delete error: " + e.message);
    }
    setBusy(false);
  };

  const onSaveHb = async (enabled: boolean) => {
    if (!hb) return;
    setBusy(true);
    try {
      const next = await setHeartbeat(hbAlias, {
        enabled,
        interval_seconds: hb.interval_seconds,
        prompt: hb.prompt,
      });
      setHb(next);
      setStatus(`heartbeat for ${hbAlias}: ${next.enabled ? "ON" : "off"} (every ${next.interval_seconds}s)`);
      await refresh();
    } catch (e: any) {
      setStatus("heartbeat save error: " + e.message);
    }
    setBusy(false);
  };

  return (
    <div className="page page-crons">
      <div className="crons-head">
        <Clock size={16} />
        <span>Crons &amp; Heartbeat</span>
        <span className="crons-sub">scheduled automations fired by the agent Heart — reusing CAVE's engine</span>
      </div>

      <div className="crons-body">
        {/* ---- CEO / per-agent HEARTBEAT ---- */}
        <section className="crons-card crons-heartbeat">
          <div className="crons-card-title">
            <Repeat size={14} /> Agent heartbeat
          </div>
          <div className="crons-row">
            <label className="crons-field">
              <span>Agent</span>
              <Select value={hbAlias} onValueChange={setHbAlias}>
                <SelectTrigger className="w-[200px]">
                  <span className="crons-target"><AgentAvatar alias={hbAlias} size={18} /> {agentLabel(hbAlias)}</span>
                </SelectTrigger>
                <SelectContent>
                  {ALL_AGENTS.map((a) => (
                    <SelectItem key={a.alias} value={a.alias}>
                      <span className="crons-target"><AgentAvatar alias={a.alias} size={18} /> {agentLabel(a.alias)}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <label className="crons-field">
              <span>Interval (s)</span>
              <Input
                type="number"
                className="w-[110px]"
                value={hb?.interval_seconds ?? 300}
                onChange={(e) => hb && setHb({ ...hb, interval_seconds: Math.max(10, parseInt(e.target.value || "0", 10) || 300) })}
              />
            </label>
            <div className="crons-hb-state">
              <span className={cn("crons-pill", hb?.enabled ? "on" : "off")}>{hb?.enabled ? "ON" : "off"}</span>
              <Button size="sm" variant={hb?.enabled ? "outline" : "default"} disabled={busy || !hb} onClick={() => onSaveHb(!hb?.enabled)}>
                <Power size={14} className="mr-1" /> {hb?.enabled ? "Disable" : "Enable"}
              </Button>
              <Button size="sm" variant="outline" disabled={busy || !hb} onClick={() => onSaveHb(!!hb?.enabled)} title="Save interval + prompt">
                Save
              </Button>
            </div>
          </div>
          <label className="crons-field crons-field-wide">
            <span>Heartbeat prompt</span>
            <textarea
              className="crons-textarea"
              rows={2}
              value={hb?.prompt ?? ""}
              onChange={(e) => hb && setHb({ ...hb, prompt: e.target.value })}
            />
          </label>
        </section>

        {/* ---- CREATE a cron ---- */}
        <section className="crons-card">
          <div className="crons-card-title">
            <Plus size={14} /> New automation
          </div>
          <div className="crons-row">
            <label className="crons-field">
              <span>Name</span>
              <Input className="w-[180px]" placeholder="daily_review" value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="crons-field">
              <span>Target agent</span>
              <Select value={target} onValueChange={setTarget}>
                <SelectTrigger className="w-[200px]">
                  <span className="crons-target"><AgentAvatar alias={target} size={18} /> {agentLabel(target)}</span>
                </SelectTrigger>
                <SelectContent>
                  {ALL_AGENTS.map((a) => (
                    <SelectItem key={a.alias} value={a.alias}>
                      <span className="crons-target"><AgentAvatar alias={a.alias} size={18} /> {agentLabel(a.alias)}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <label className="crons-field">
              <span>Schedule</span>
              <div className="crons-schedmode">
                <button type="button" className={cn("crons-modebtn", schedMode === "interval" && "active")} onClick={() => setSchedMode("interval")}>
                  Interval
                </button>
                <button type="button" className={cn("crons-modebtn", schedMode === "cron" && "active")} onClick={() => setSchedMode("cron")}>
                  Cron expr
                </button>
              </div>
            </label>
            {schedMode === "interval" ? (
              <label className="crons-field">
                <span>Interval (s)</span>
                <Input type="number" className="w-[110px]" value={interval} onChange={(e) => setInterval(Math.max(10, parseInt(e.target.value || "0", 10) || 300))} />
              </label>
            ) : (
              <label className="crons-field">
                <span>Cron expression</span>
                <Input className="w-[160px]" placeholder="0 3 * * *" value={cronExpr} onChange={(e) => setCronExpr(e.target.value)} />
              </label>
            )}
          </div>
          <label className="crons-field crons-field-wide">
            <span>Prompt (fired at the agent each interval)</span>
            <textarea className="crons-textarea" rows={2} placeholder="Summarize today's changes and post a status." value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          </label>
          <div>
            <Button size="sm" disabled={busy || !name.trim() || !prompt.trim()} onClick={onCreate}>
              <Plus size={14} className="mr-1" /> Create automation
            </Button>
          </div>
        </section>

        {/* ---- LIST ---- */}
        <section className="crons-card crons-list-card">
          <div className="crons-card-title">
            <Clock size={14} /> Automations ({autos.length})
          </div>
          {autos.length === 0 ? (
            <div className="crons-empty">No automations yet — create one above.</div>
          ) : (
            <table className="crons-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Target</th>
                  <th>Schedule</th>
                  <th>Runs</th>
                  <th>Last run</th>
                  <th>State</th>
                  <th className="crons-actions-th">Actions</th>
                </tr>
              </thead>
              <tbody>
                {autos.map((a) => (
                  <tr key={a.name} className={cn(!a.enabled && "crons-row-disabled")}>
                    <td className="crons-name">{a.name}</td>
                    <td>
                      {a.alias ? (
                        <span className="crons-target"><AgentAvatar alias={a.alias} size={18} /> {agentLabel(a.alias)}</span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>{fmtSchedule(a.schedule)}</td>
                    <td>{a.run_count}</td>
                    <td>{fmtWhen(a.last_run)}</td>
                    <td><span className={cn("crons-pill", a.enabled ? "on" : "off")}>{a.enabled ? "ON" : "off"}</span></td>
                    <td className="crons-actions">
                      <Button size="icon" variant="ghost" className="h-8 w-8" title="Fire now" disabled={busy} onClick={() => onFire(a)}>
                        <Play size={14} />
                      </Button>
                      <Button size="icon" variant="ghost" className="h-8 w-8" title={a.enabled ? "Disable" : "Enable"} disabled={busy} onClick={() => onToggle(a)}>
                        <Power size={14} className={a.enabled ? "text-emerald-400" : "text-muted-foreground"} />
                      </Button>
                      <Button size="icon" variant="ghost" className="h-8 w-8" title="Delete" disabled={busy} onClick={() => onDelete(a)}>
                        <Trash2 size={14} className="text-destructive" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        {/* ---- upcoming fires (calendar view, next 7 days) ---- */}
        <section className="crons-card">
          <div className="crons-card-title">
            <Clock size={14} /> Upcoming fires — next 7 days ({events.length})
          </div>
          {events.length === 0 ? (
            <div className="crons-empty">No fires scheduled in the next 7 days (enable an automation above).</div>
          ) : (
            <div className="crons-events">
              {events.slice(0, 30).map((e, i) => (
                <div key={i} className="crons-event">
                  <span className="crons-event-time">{fmtWhen(e.time)}</span>
                  <span className="crons-event-name">{e.name}</span>
                  <span className="crons-event-sched">{fmtSchedule(e.schedule)}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        {status && <div className="crons-status">{status}</div>}
      </div>
    </div>
  );
}
