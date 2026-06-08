import { MessageSquare, User, Users, Clock, Dumbbell } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Page } from "../pages";

/** SidePanel — the app-wide LEFT navigation rail. Switches the pages: Main (CEO + editor),
 *  Specialist (choose one + editor), Group (select any → side-by-side windows + templates),
 *  Crons (scheduled automations + per-agent heartbeat). */
const NAV: { id: Page; label: string; Icon: typeof MessageSquare }[] = [
  { id: "main", label: "Main", Icon: MessageSquare },
  { id: "specialist", label: "Specialist", Icon: User },
  { id: "group", label: "Group", Icon: Users },
  { id: "crons", label: "Crons", Icon: Clock },
  { id: "gym", label: "Gym", Icon: Dumbbell },
];

export function SidePanel({ page, onNavigate }: { page: Page; onNavigate: (p: Page) => void }) {
  return (
    <nav className="side-panel" aria-label="Pages">
      <div className="side-brand" title="PromptWorld">PW</div>
      {NAV.map(({ id, label, Icon }) => (
        <button
          key={id}
          className={cn("side-item", page === id && "active")}
          data-page={id}
          aria-current={page === id ? "page" : undefined}
          onClick={() => onNavigate(id)}
          title={label}
        >
          <Icon size={20} strokeWidth={1.75} />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}
