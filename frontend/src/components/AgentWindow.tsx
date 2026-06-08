import { useCallback, useState } from "react";
import {
  useExternalStoreRuntime,
  AssistantRuntimeProvider,
  type ThreadMessageLike,
  type AppendMessage,
} from "@assistant-ui/react";
import { Thread } from "./Thread";
import { ConversationsMenu } from "./ConversationsMenu";
import { AgentAvatar } from "./AgentAvatar";
import { ProfileEditor } from "./ProfileEditor";
import { useAgentChat, sendMessage, setAgentMessages } from "../chatStore";
import { useAgentProfile } from "../agentProfiles";
import { agentLabel, agentColor } from "../agents";

/**
 * AgentWindow — one chat window for ONE agent (by alias). It is a STATELESS VIEW over the
 * global chatStore: live state (messages + isRunning) and the stream-folding live in the
 * store (per alias, independent of mount), so switching the 3 pages never wipes history and
 * no /ws event is missed while a window is unmounted.
 *
 * The composer's onNew posts to the right endpoint via the store: CEO → /api/chat,
 * a gym specialist → /api/gym/{alias}. The reply always streams back over /ws → the store.
 *
 * `title` + `color` let the GROUP page relabel/recolor a window (per saved template). Defaults
 * come from the agents roster.
 */
export function AgentWindow({
  alias,
  title,
  color,
}: {
  alias: string;
  title?: string;
  color?: string;
}) {
  const isCeo = alias === "ceo";
  const { messages, isRunning } = useAgentChat(alias);
  const profile = useAgentProfile(alias);
  const accent = color || agentColor(alias);
  // title (a Group-template override) wins; else the agent's profile display name; else the roster label
  const head = title || profile.display_name || agentLabel(alias);
  const [profileOpen, setProfileOpen] = useState(false);
  const idle = messages.length === 0 && !isRunning;

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const text = (message.content ?? [])
        .map((c: any) => (c?.type === "text" ? c.text : ""))
        .join("");
      await sendMessage(alias, text);
    },
    [alias],
  );

  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages,
    isRunning,
    onNew,
    setMessages: (ms) => setAgentMessages(alias, ms as ThreadMessageLike[]),
    convertMessage: (m) => m,
  });

  return (
    <div
      className={"agent-window" + (isCeo ? " agent-ceo" : "") + (isRunning ? " running" : "")}
      style={{ ["--agent-accent" as any]: accent }}
    >
      <div className="agent-head">
        <button
          className="agent-identity"
          onClick={() => setProfileOpen(true)}
          title={`${head} — edit profile`}
        >
          <AgentAvatar alias={alias} name={title} color={accent} size={22} />
          <span className="agent-name">{head}</span>
        </button>
        {isRunning ? <span className="agent-dot" /> : null}
        <span className="agent-head-spacer" />
        <ConversationsMenu alias={alias} />
      </div>
      <AssistantRuntimeProvider runtime={runtime}>
        <Thread placeholder={`Message ${head}…`} emptyText="" />
      </AssistantRuntimeProvider>
      {idle && (
        <div className="agent-idle-overlay" aria-hidden="true">
          <AgentAvatar alias={alias} name={title} color={accent} size={56} />
          <div className="agent-idle-label">{head} — idle</div>
        </div>
      )}
      {profileOpen && <ProfileEditor alias={alias} onClose={() => setProfileOpen(false)} />}
    </div>
  );
}
