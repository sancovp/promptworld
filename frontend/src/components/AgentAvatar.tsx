import { useAgentProfile } from "../agentProfiles";
import { agentColor, agentLabel } from "../agents";

/**
 * AgentAvatar — the per-agent identity circle (V2 (a)). Shows the agent's uploaded avatar image
 * if it has one, else a colored circle with the first letter of its display name. Reads the live
 * profile store, so it updates the instant a profile is saved anywhere.
 *
 * `name`/`color` overrides let a Group window use its per-template label/color; otherwise the
 * profile display_name (then the roster label) and the roster color are used.
 */
export function AgentAvatar({
  alias,
  size = 22,
  name,
  color,
}: {
  alias: string;
  size?: number;
  name?: string;
  color?: string;
}) {
  const prof = useAgentProfile(alias);
  const display = name || prof.display_name || agentLabel(alias);
  const accent = color || agentColor(alias);
  const initial = (display.trim()[0] || "?").toUpperCase();

  return (
    <span
      className="agent-avatar"
      style={{
        width: size,
        height: size,
        background: prof.avatar ? "#0b0f14" : accent,
        ["--avatar-accent" as any]: accent,
      }}
      title={display}
    >
      {prof.avatar ? (
        <img className="agent-avatar-img" src={prof.avatar} alt={display} />
      ) : (
        <span className="agent-avatar-initial" style={{ fontSize: Math.round(size * 0.5) }}>
          {initial}
        </span>
      )}
    </span>
  );
}
