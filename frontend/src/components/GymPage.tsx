import { useCallback, useEffect, useMemo, useState } from "react";
import { Dumbbell, Plus, Play, Eye, FlaskConical, ClipboardList, FileText, Repeat, Globe, Square } from "lucide-react";
import { AgentAvatar } from "./AgentAvatar";
import { AgentWindow } from "./AgentWindow";
import { ALL_AGENTS, agentLabel } from "../agents";
import {
  listSpecs,
  createSpec,
  updateSpec,
  observe,
  runResearch,
  researchNow,
  scheduleSpec,
  stopSchedule,
  updatePaper,
  publishSpec,
  getSpec,
  GYM_STATUSES,
  type GymSpec,
  type GymStatus,
} from "../gymApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger } from "@/components/ui/select";
import { cn } from "@/lib/utils";

/**
 * GymPage (V2 (g)) — the GYM MODULE: write SPECS, track each spec's STATUS through the lifecycle
 * (draft → active → measuring → done/abandoned), record OBSERVATIONS/measurements, and launch
 * RESEARCH-RUNS (dispatch a specialist against the spec; the reply is recorded back + streams live
 * over /ws via the existing chatStore/AgentWindow). NO mock: every action hits the live
 * /api/gym-specs routes (server/gym_specs.py). Master/detail: a spec LIST on the left, the selected
 * spec's detail (status/observations/runs) on the right, mirroring the rest of the app's language.
 */
function fmtWhen(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function GymPage() {
  const [specs, setSpecs] = useState<GymSpec[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  // list filter
  const [filter, setFilter] = useState<GymStatus | "all">("all");

  // create form
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [owner, setOwner] = useState("ceo");
  const [assigned, setAssigned] = useState("ceo");

  // research-loop schedule input (for the selected spec)
  const [sched, setSched] = useState("every:3600");

  // observation input (for the selected spec)
  const [obsText, setObsText] = useState("");
  const [obsMetric, setObsMetric] = useState("");

  // run-research controls (for the selected spec)
  const [runAlias, setRunAlias] = useState("ceo");
  const [runRequest, setRunRequest] = useState("");
  const [lastReply, setLastReply] = useState("");

  const refresh = useCallback(async () => {
    try {
      setSpecs(await listSpecs());
    } catch (e: any) {
      setStatus("list error: " + e.message);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const selected = useMemo(() => specs.find((s) => s.id === selectedId) ?? null, [specs, selectedId]);

  // keep the selected spec valid; auto-select the first when none chosen
  useEffect(() => {
    if (selectedId && !specs.some((s) => s.id === selectedId)) setSelectedId("");
    if (!selectedId && specs.length > 0) setSelectedId(specs[0].id);
  }, [specs, selectedId]);

  // mirror the selected spec's schedule into the input (default to every:3600 when none)
  const selectedSpec = useMemo(() => specs.find((s) => s.id === selectedId) ?? null, [specs, selectedId]);
  useEffect(() => {
    setSched(selectedSpec?.schedule || "every:3600");
  }, [selectedSpec?.id, selectedSpec?.schedule]);

  const visible = useMemo(
    () => (filter === "all" ? specs : specs.filter((s) => s.status === filter)),
    [specs, filter],
  );

  const onCreate = async () => {
    const t = title.trim();
    if (!t) return;
    setBusy(true);
    setStatus("");
    try {
      const spec = await createSpec(t, body.trim(), owner, assigned);
      setTitle("");
      setBody("");
      setStatus(`created ${spec.id}`);
      await refresh();
      setSelectedId(spec.id);
    } catch (e: any) {
      setStatus("create error: " + e.message);
    }
    setBusy(false);
  };

  // pull the freshest copy of one spec and merge it into the list (used after any mutating action)
  const refreshSelected = useCallback(async (id: string) => {
    try {
      const fresh = await getSpec(id);
      setSpecs((prev) => prev.map((s) => (s.id === fresh.id ? fresh : s)));
      return fresh;
    } catch {
      return null;
    }
  }, []);

  const onStatus = async (s: GymSpec, next: GymStatus) => {
    setBusy(true);
    try {
      await updateSpec(s.id, { status: next });
      await refresh();
      setStatus(`${s.id}: status → ${next}`);
    } catch (e: any) {
      setStatus("status error: " + e.message);
    }
    setBusy(false);
  };

  const onObserve = async () => {
    if (!selected || !obsText.trim()) return;
    setBusy(true);
    try {
      const updated = await observe(selected.id, obsText.trim(), obsMetric.trim() || undefined);
      setObsText("");
      setObsMetric("");
      setSpecs((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      setStatus(`observed ${updated.id}`);
    } catch (e: any) {
      setStatus("observe error: " + e.message);
    }
    setBusy(false);
  };

  const onRun = async () => {
    if (!selected || !runRequest.trim()) return;
    setBusy(true);
    setStatus(`running ${runAlias} against ${selected.id}…`);
    setLastReply("");
    try {
      const { spec, reply } = await runResearch(selected.id, runAlias, runRequest.trim());
      setLastReply(reply || "");
      setSpecs((prev) => prev.map((s) => (s.id === spec.id ? spec : s)));
      setStatus(`run recorded on ${spec.id}`);
    } catch (e: any) {
      setStatus("run error: " + e.message);
    }
    setBusy(false);
  };

  // research loop: run the assigned agent's research turn now (it writes a paper onto the spec)
  const onResearchNow = async () => {
    if (!selected) return;
    setBusy(true);
    setStatus(`researching ${selected.id}…`);
    try {
      const res = await researchNow(selected.id);
      setSpecs((prev) => prev.map((s) => (s.id === res.spec.id ? res.spec : s)));
      if (res.skipped) setStatus(res.skipped);
      else setStatus(res.paper_added ? `paper added to ${res.spec.id}` : `research ran on ${res.spec.id}`);
    } catch (e: any) {
      setStatus("research error: " + e.message);
    }
    setBusy(false);
  };

  // research loop: put the spec on a cron schedule
  const onSchedule = async () => {
    if (!selected || !sched.trim()) return;
    setBusy(true);
    try {
      const res = await scheduleSpec(selected.id, sched.trim());
      setSpecs((prev) => prev.map((s) => (s.id === res.spec.id ? res.spec : s)));
      setStatus(`scheduled ${res.spec.id}: ${res.spec.schedule}`);
    } catch (e: any) {
      setStatus("schedule error: " + e.message);
    }
    setBusy(false);
  };

  // research loop: stop the scheduled loop
  const onStopSchedule = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      const res = await stopSchedule(selected.id);
      setSpecs((prev) => prev.map((s) => (s.id === res.spec.id ? res.spec : s)));
      setStatus(`schedule stopped on ${res.spec.id}`);
    } catch (e: any) {
      setStatus("stop error: " + e.message);
    }
    setBusy(false);
  };

  // toggle one paper's published flag
  const onTogglePaper = async (paperId: string, next: boolean) => {
    if (!selected) return;
    setBusy(true);
    try {
      const updated = await updatePaper(selected.id, paperId, { published: next });
      setSpecs((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      setStatus(`paper ${next ? "published" : "unpublished"} on ${updated.id}`);
    } catch (e: any) {
      setStatus("paper error: " + e.message);
    }
    setBusy(false);
  };

  // publish / unpublish the whole spec
  const onPublishSpec = async (next: boolean) => {
    if (!selected) return;
    setBusy(true);
    try {
      const updated = await publishSpec(selected.id, next);
      setSpecs((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      setStatus(`${updated.id}: ${next ? "published" : "unpublished"}`);
    } catch (e: any) {
      setStatus("publish error: " + e.message);
    }
    setBusy(false);
  };

  // when the user opens a spec, pull its freshest copy (runs/observations may have grown elsewhere)
  const onSelect = async (id: string) => {
    setSelectedId(id);
    setLastReply("");
    await refreshSelected(id);
  };

  return (
    <div className="page page-gym">
      <div className="gym-head">
        <Dumbbell size={16} />
        <span>Gym</span>
        <span className="gym-sub">specs · statuses · observations · research-runs — the additive build/measure layer</span>
      </div>

      <div className="gym-cols">
        {/* ---- LEFT: create + spec list ---- */}
        <div className="gym-left">
          <section className="gym-card">
            <div className="gym-card-title">
              <Plus size={14} /> New spec
            </div>
            <label className="gym-field">
              <span>Title</span>
              <Input placeholder="Harden the Skill specialist's CLAUDE.md" value={title} onChange={(e) => setTitle(e.target.value)} />
            </label>
            <label className="gym-field">
              <span>What do you want to exist — or to know why it can't yet?</span>
              <textarea
                className="gym-textarea"
                rows={3}
                placeholder="Describe what you want the agent to achieve with its specialization."
                value={body}
                onChange={(e) => setBody(e.target.value)}
              />
            </label>
            <label className="gym-field">
              <span>Owner agent (creator)</span>
              <Select value={owner} onValueChange={setOwner}>
                <SelectTrigger className="w-full">
                  <span className="gym-target"><AgentAvatar alias={owner} size={18} /> {agentLabel(owner)}</span>
                </SelectTrigger>
                <SelectContent>
                  {ALL_AGENTS.map((a) => (
                    <SelectItem key={a.alias} value={a.alias}>
                      <span className="gym-target"><AgentAvatar alias={a.alias} size={18} /> {agentLabel(a.alias)}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <label className="gym-field">
              <span>Researcher agent</span>
              <Select value={assigned} onValueChange={setAssigned}>
                <SelectTrigger className="w-full">
                  <span className="gym-target"><AgentAvatar alias={assigned} size={18} /> {agentLabel(assigned)}</span>
                </SelectTrigger>
                <SelectContent>
                  {ALL_AGENTS.map((a) => (
                    <SelectItem key={a.alias} value={a.alias}>
                      <span className="gym-target"><AgentAvatar alias={a.alias} size={18} /> {agentLabel(a.alias)}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <Button size="sm" disabled={busy || !title.trim()} onClick={onCreate}>
              <Plus size={14} className="mr-1" /> Create spec
            </Button>
          </section>

          <section className="gym-card gym-list-card">
            <div className="gym-card-title">
              <ClipboardList size={14} /> Specs ({specs.length})
              <span className="gym-filter">
                <button className={cn("gym-chip", filter === "all" && "active")} onClick={() => setFilter("all")}>all</button>
                {GYM_STATUSES.map((s) => (
                  <button key={s} className={cn("gym-chip", filter === s && "active")} onClick={() => setFilter(s)}>
                    {s}
                  </button>
                ))}
              </span>
            </div>
            {visible.length === 0 ? (
              <div className="gym-empty">No specs{filter !== "all" ? ` with status "${filter}"` : ""} — create one above.</div>
            ) : (
              <div className="gym-spec-list">
                {visible.map((s) => (
                  <button
                    key={s.id}
                    className={cn("gym-spec-card", s.id === selectedId && "selected")}
                    onClick={() => onSelect(s.id)}
                  >
                    <div className="gym-spec-top">
                      <span className="gym-spec-title">{s.title}</span>
                      {s.published && <span className="gym-published">published</span>}
                      <span className={cn("gym-pill", "gym-st-" + s.status)}>{s.status}</span>
                    </div>
                    <div className="gym-spec-meta">
                      <span className="gym-target"><AgentAvatar alias={s.assigned_agent || s.owner_alias} size={16} /> {agentLabel(s.assigned_agent || s.owner_alias)}</span>
                      <span className="gym-counts">
                        <Eye size={12} /> {s.observations.length}
                        <FileText size={12} /> {(s.papers ?? []).length}
                        <Play size={12} /> {s.runs.length}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>

        {/* ---- RIGHT: selected spec detail ---- */}
        <div className="gym-right">
          {!selected ? (
            <div className="gym-detail-empty">
              <Dumbbell size={40} />
              <div>Select a spec on the left, or create one, to track its status, observations, and research-runs.</div>
            </div>
          ) : (
            <div className="gym-detail">
              <section className="gym-card">
                <div className="gym-detail-head">
                  <span className="gym-detail-title">{selected.title}</span>
                  {selected.published && <span className="gym-published">published</span>}
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => onPublishSpec(!selected.published)}
                  >
                    <Globe size={14} className="mr-1" /> {selected.published ? "Unpublish spec" : "Publish spec"}
                  </Button>
                  <label className="gym-field gym-field-inline">
                    <span>Status</span>
                    <Select value={selected.status} onValueChange={(v) => onStatus(selected, v as GymStatus)}>
                      <SelectTrigger className="w-[160px]">
                        <span className={cn("gym-pill", "gym-st-" + selected.status)}>{selected.status}</span>
                      </SelectTrigger>
                      <SelectContent>
                        {GYM_STATUSES.map((s) => (
                          <SelectItem key={s} value={s}>
                            {s}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </label>
                </div>
                <div className="gym-detail-meta">
                  <span className="gym-target"><AgentAvatar alias={selected.assigned_agent || selected.owner_alias} size={18} /> {agentLabel(selected.assigned_agent || selected.owner_alias)}</span>
                  <span className="gym-detail-id">{selected.id}</span>
                  <span className="gym-detail-when">created {fmtWhen(selected.created_at)}</span>
                </div>
                {selected.body && <div className="gym-detail-body">{selected.body}</div>}
              </section>

              {/* ---- RESEARCH LOOP ---- */}
              <section className="gym-card">
                <div className="gym-card-title">
                  <Repeat size={14} /> Research loop
                </div>
                <div className="gym-loop">
                  <span className="gym-target"><AgentAvatar alias={selected.assigned_agent || selected.owner_alias} size={18} /> {agentLabel(selected.assigned_agent || selected.owner_alias)}</span>
                  {(selected.assigned_agent || selected.owner_alias) === "team" ? (
                    <div className="gym-caveat">
                      Teams can't be auto-researched — a team must be run by the researcher.
                    </div>
                  ) : (
                    <>
                      <label className="gym-field gym-field-grow">
                        <span>Schedule</span>
                        <Input
                          placeholder="every:3600 or 0 3 * * *"
                          value={sched}
                          onChange={(e) => setSched(e.target.value)}
                        />
                      </label>
                      <Button size="sm" disabled={busy || !sched.trim()} onClick={onSchedule}>
                        <Repeat size={14} className="mr-1" /> Start
                      </Button>
                      {selected.schedule && (
                        <Button size="sm" variant="outline" disabled={busy} onClick={onStopSchedule}>
                          <Square size={14} className="mr-1" /> Stop
                        </Button>
                      )}
                    </>
                  )}
                  <Button
                    size="sm"
                    disabled={busy || (selected.assigned_agent || selected.owner_alias) === "team"}
                    onClick={onResearchNow}
                  >
                    <FlaskConical size={14} className="mr-1" /> Research now
                  </Button>
                </div>
                {selected.schedule && (selected.assigned_agent || selected.owner_alias) !== "team" && (
                  <div className="gym-loop-when">scheduled: {selected.schedule}</div>
                )}
              </section>

              {/* ---- PAPERS ---- */}
              <section className="gym-card">
                <div className="gym-card-title">
                  <FileText size={14} /> Papers ({(selected.papers ?? []).length})
                </div>
                {(selected.papers ?? []).length === 0 ? (
                  <div className="gym-empty">No papers yet — run the research loop to produce one.</div>
                ) : (
                  <div className="gym-paper-list">
                    {[...(selected.papers ?? [])]
                      .slice()
                      .reverse()
                      .map((p) => (
                        <div key={p.id} className="gym-paper">
                          <div className="gym-paper-head">
                            <span className="gym-paper-title">{p.title}</span>
                            <span className="gym-paper-when">{fmtWhen(p.ts)}</span>
                            {p.published && <span className="gym-published">published</span>}
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={busy}
                              onClick={() => onTogglePaper(p.id, !p.published)}
                            >
                              <Globe size={14} className="mr-1" /> {p.published ? "Unpublish" : "Publish"}
                            </Button>
                          </div>
                          <pre className="gym-paper-body">{p.body}</pre>
                        </div>
                      ))}
                  </div>
                )}
              </section>

              {/* ---- OBSERVATIONS ---- */}
              <section className="gym-card">
                <div className="gym-card-title">
                  <Eye size={14} /> Observations ({selected.observations.length})
                </div>
                {selected.observations.length === 0 ? (
                  <div className="gym-empty">No observations yet — add a measurement below.</div>
                ) : (
                  <div className="gym-obs-list">
                    {selected.observations.map((o, i) => (
                      <div key={i} className="gym-obs">
                        <span className="gym-obs-when">{fmtWhen(o.ts)}</span>
                        {o.metric && <span className="gym-obs-metric">{o.metric}</span>}
                        <span className="gym-obs-text">{o.text}</span>
                      </div>
                    ))}
                  </div>
                )}
                <div className="gym-row">
                  <label className="gym-field gym-field-grow">
                    <span>Observation</span>
                    <Input placeholder="What did you measure / observe?" value={obsText} onChange={(e) => setObsText(e.target.value)} />
                  </label>
                  <label className="gym-field">
                    <span>Metric (optional)</span>
                    <Input className="w-[150px]" placeholder="e.g. pass@1 = 0.8" value={obsMetric} onChange={(e) => setObsMetric(e.target.value)} />
                  </label>
                  <Button size="sm" disabled={busy || !obsText.trim()} onClick={onObserve}>
                    <Plus size={14} className="mr-1" /> Add
                  </Button>
                </div>
              </section>

              {/* ---- RESEARCH RUNS ---- */}
              <section className="gym-card">
                <div className="gym-card-title">
                  <FlaskConical size={14} /> Research runs ({selected.runs.length})
                </div>
                {selected.runs.length === 0 ? (
                  <div className="gym-empty">No runs yet — dispatch a specialist below.</div>
                ) : (
                  <div className="gym-run-list">
                    {selected.runs.map((r, i) => (
                      <div key={i} className="gym-run">
                        <div className="gym-run-head">
                          <span className="gym-target"><AgentAvatar alias={r.alias} size={16} /> {agentLabel(r.alias)}</span>
                          <span className="gym-run-when">{fmtWhen(r.ts)}</span>
                        </div>
                        <div className="gym-run-request">{r.request}</div>
                        <div className="gym-run-reply">{r.reply_excerpt}</div>
                      </div>
                    ))}
                  </div>
                )}
                <div className="gym-row">
                  <label className="gym-field">
                    <span>Specialist</span>
                    <Select value={runAlias} onValueChange={setRunAlias}>
                      <SelectTrigger className="w-[200px]">
                        <span className="gym-target"><AgentAvatar alias={runAlias} size={18} /> {agentLabel(runAlias)}</span>
                      </SelectTrigger>
                      <SelectContent>
                        {ALL_AGENTS.map((a) => (
                          <SelectItem key={a.alias} value={a.alias}>
                            <span className="gym-target"><AgentAvatar alias={a.alias} size={18} /> {agentLabel(a.alias)}</span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </label>
                  <label className="gym-field gym-field-grow">
                    <span>Request (fired at the specialist)</span>
                    <Input placeholder="Research and propose the change for this spec." value={runRequest} onChange={(e) => setRunRequest(e.target.value)} />
                  </label>
                  <Button size="sm" disabled={busy || !runRequest.trim()} onClick={onRun}>
                    <Play size={14} className="mr-1" /> Run
                  </Button>
                </div>
                {lastReply && (
                  <div className="gym-run-reply gym-run-reply-latest">
                    <div className="gym-run-reply-label">latest reply</div>
                    {lastReply}
                  </div>
                )}
                {/* live stream of the assigned specialist (folds the same /ws as everywhere) */}
                <div className="gym-run-window">
                  <AgentWindow alias={selected.assigned_agent || runAlias} />
                </div>
              </section>

              {status && <div className="gym-status">{status}</div>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
