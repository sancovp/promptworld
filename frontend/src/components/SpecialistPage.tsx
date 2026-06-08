import { useState } from "react";
import { AgentWindow } from "./AgentWindow";
import { FileExplorer } from "./FileExplorer";
import { AgentAvatar } from "./AgentAvatar";
import { SPECIALISTS } from "../agents";
import { useAgentProfile } from "../agentProfiles";
import { agentLabel } from "../agents";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";

/** One row in the specialist <Select> — the agent's avatar circle + its display name (profile
 *  display_name, else the roster label). Used in both the trigger (selected) and the dropdown. */
function SpecialistOption({ alias }: { alias: string }) {
  const prof = useAgentProfile(alias);
  return (
    <span className="specialist-option">
      <AgentAvatar alias={alias} size={18} />
      <span className="specialist-option-name">{prof.display_name || agentLabel(alias)}</span>
    </span>
  );
}

/** SPECIALIST page — choose ONE specialist (shadcn Select, now with avatar + display name) → that
 *  specialist's chat + the Monaco editor. The chat keeps its history (chatStore) across selections. */
export function SpecialistPage() {
  const [alias, setAlias] = useState(SPECIALISTS[0].alias);
  return (
    <div className="page page-split">
      <section className="page-chat">
        <div className="page-toolbar">
          <span className="page-toolbar-label">Specialist</span>
          <Select value={alias} onValueChange={setAlias}>
            <SelectTrigger className="w-[240px]">
              <SpecialistOption alias={alias} />
            </SelectTrigger>
            <SelectContent>
              {SPECIALISTS.map((s) => (
                <SelectItem key={s.alias} value={s.alias}>
                  <SpecialistOption alias={s.alias} />
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="page-chat-body">
          <AgentWindow key={alias} alias={alias} />
        </div>
      </section>
      <section className="page-editor">
        <FileExplorer />
      </section>
    </div>
  );
}
