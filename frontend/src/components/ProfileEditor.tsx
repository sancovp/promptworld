import { useEffect, useRef, useState } from "react";
import { FileEdit, Upload, Trash2, X } from "lucide-react";
import { useAgentProfile, saveProfile, fileToAvatarDataUrl } from "../agentProfiles";
import { agentLabel, agentColor, agentPromptPath } from "../agents";
import { openFileInEditor } from "../editorBus";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * ProfileEditor — the small per-agent PROFILE page (V2 (a)(b)(c)). A modal reachable from the
 * agent header: edits ONLY the display NAME + AVATAR (image upload, downscaled client-side), and
 * offers an "Edit prompt" button that opens this agent's CLAUDE.md in the Monaco workbench (the
 * prompt is edited DIRECTLY there + @ file-refs — there is NO prompt-block system). Saves to
 * /api/agents/{alias}/profile; persists across reload.
 */
export function ProfileEditor({ alias, onClose }: { alias: string; onClose: () => void }) {
  const prof = useAgentProfile(alias);
  const accent = agentColor(alias);
  const [name, setName] = useState(prof.display_name || "");
  // staged avatar: undefined = unchanged, string = new data URL, null = cleared
  const [staged, setStaged] = useState<string | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  // keep the name field in sync if the profile loads after open
  useEffect(() => {
    setName(prof.display_name || "");
  }, [prof.display_name]);

  // close on Escape
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const previewSrc = staged === undefined ? prof.avatar : staged; // null => show initial
  const display = (name || prof.display_name || agentLabel(alias)).trim();
  const initial = (display[0] || "?").toUpperCase();

  const onPick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-picking the same file
    if (!file) return;
    setErr("");
    try {
      setStaged(await fileToAvatarDataUrl(file));
    } catch (e2: any) {
      setErr(e2?.message || "could not read image");
    }
  };

  const onSave = async () => {
    setBusy(true);
    setErr("");
    try {
      const patch: { display_name?: string | null; avatar?: string | null } = {
        display_name: name.trim() || null,
      };
      if (staged !== undefined) patch.avatar = staged; // string => set, null => clear
      await saveProfile(alias, patch);
      onClose();
    } catch (e: any) {
      setErr(e?.message || "save failed");
      setBusy(false);
    }
  };

  const onEditPrompt = () => {
    openFileInEditor(agentPromptPath(alias));
    onClose();
  };

  return (
    <div className="profile-backdrop" onMouseDown={onClose}>
      <div className="profile-modal" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="profile-modal-head">
          <span className="profile-modal-title">Agent profile — {agentLabel(alias)}</span>
          <button className="profile-close" onClick={onClose} title="Close">
            <X size={16} />
          </button>
        </div>

        <div className="profile-modal-body">
          <div className="profile-avatar-row">
            <span
              className="agent-avatar profile-avatar-preview"
              style={{ background: previewSrc ? "#0b0f14" : accent, ["--avatar-accent" as any]: accent }}
            >
              {previewSrc ? (
                <img className="agent-avatar-img" src={previewSrc} alt={display} />
              ) : (
                <span className="agent-avatar-initial" style={{ fontSize: 30 }}>
                  {initial}
                </span>
              )}
            </span>
            <div className="profile-avatar-actions">
              <input ref={fileRef} type="file" accept="image/*" className="profile-file-input" onChange={onPick} />
              <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()}>
                <Upload size={14} className="mr-1" /> Upload avatar
              </Button>
              {previewSrc && (
                <Button variant="ghost" size="sm" onClick={() => setStaged(null)} title="Remove avatar">
                  <Trash2 size={14} className="mr-1" /> Remove
                </Button>
              )}
            </div>
          </div>

          <div className="profile-field">
            <Label htmlFor="profile-name" className="profile-label">
              Display name
            </Label>
            <Input
              id="profile-name"
              value={name}
              placeholder={agentLabel(alias)}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && onSave()}
            />
          </div>

          <div className="profile-prompt-note">
            The agent's prompt is its <code>CLAUDE.md</code>, edited directly in the workbench (+ <code>@</code> file-refs).
          </div>
          <Button variant="outline" size="sm" className="profile-edit-prompt" onClick={onEditPrompt}>
            <FileEdit size={14} className="mr-1" /> Edit prompt (CLAUDE.md)
          </Button>

          {err && <div className="profile-err">{err}</div>}
        </div>

        <div className="profile-modal-foot">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button size="sm" onClick={onSave} disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
}
