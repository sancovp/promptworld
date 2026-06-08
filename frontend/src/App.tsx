import { useEffect, useRef, useState } from "react";
import { SidePanel } from "./components/SidePanel";
import { MainPage } from "./components/MainPage";
import { SpecialistPage } from "./components/SpecialistPage";
import { GroupPage } from "./components/GroupPage";
import { CronsPage } from "./components/CronsPage";
import { GymPage } from "./components/GymPage";
import { TerminalPanel } from "./components/TerminalPanel";
import { publish } from "./agentBus";
import { ensureAgents } from "./chatStore";
import { ALL_AGENTS } from "./agents";
import type { Page } from "./pages";

// Seed the chatStore with the CEO + the 7 PromptGym specialists so EVERY agent folds its /ws
// stream from the start — even when its window isn't mounted (the 3 pages mount/unmount windows).
const SEED_ALIASES = ALL_AGENTS.map((a) => a.alias);

const PAGE_NOTE: Record<Page, string> = {
  main: "CEO + workspace editor",
  specialist: "one specialist + workspace editor",
  group: "group — side-by-side agent windows",
  crons: "crons — scheduled automations + agent heartbeat",
  gym: "gym — specs, statuses, observations + research-runs",
};

export default function App() {
  const known = useRef<Set<string>>(new Set(SEED_ALIASES));
  const [page, setPage] = useState<Page>("main");
  const [termOpen, setTermOpen] = useState(true); // the terminal panel is collapsible

  // ONE WebSocket, DEMULTIPLEXED by alias onto the agentBus → the chatStore folds each alias's
  // stream (independent of which window/page is mounted). Non-agent messages (e.g.
  // {type:"file_changed"}) are ignored here — the FileExplorer keeps its own /ws for those.
  useEffect(() => {
    ensureAgents(SEED_ALIASES);
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws`);
    ws.onmessage = (e: MessageEvent) => {
      let obj: any;
      try {
        obj = JSON.parse(e.data);
      } catch {
        return;
      }
      const alias = obj?.alias;
      if (!alias) return;
      if (!known.current.has(alias)) {
        known.current.add(alias);
        ensureAgents([alias]); // unknown alias on /ws → fold it too
      }
      publish(alias, obj.event ?? obj);
    };
    ws.onerror = () => {};
    return () => ws.close();
  }, []);

  return (
    <div className="app-shell">
      <SidePanel page={page} onNavigate={setPage} />
      <div className="app-body">
        <header className="app-header">
          PromptWorld <span>— {PAGE_NOTE[page]}</span>
        </header>
        <div className="app-page">
          {page === "main" && <MainPage />}
          {page === "specialist" && <SpecialistPage />}
          {page === "group" && <GroupPage />}
          {page === "crons" && <CronsPage />}
          {page === "gym" && <GymPage />}
        </div>
        <section className={"pane pane-terminal" + (termOpen ? "" : " collapsed")}>
          <div className="pane-title">
            <button
              className="term-toggle"
              onClick={() => setTermOpen((o) => !o)}
              title={termOpen ? "Hide the terminal" : "Show the terminal"}
            >
              {termOpen ? "▾" : "▸"} Terminal
            </button>
            <span className="pane-title-note">
              — not signed in? run <code>claude auth login</code> here
            </span>
          </div>
          {termOpen && <TerminalPanel />}
        </section>
      </div>
    </div>
  );
}
