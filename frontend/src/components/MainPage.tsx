import { AgentWindow } from "./AgentWindow";
import { FileExplorer } from "./FileExplorer";

/** MAIN page — only the CEO chat + the Monaco editor, side by side. */
export function MainPage() {
  return (
    <div className="page page-split">
      <section className="page-chat">
        <AgentWindow alias="ceo" />
      </section>
      <section className="page-editor">
        <FileExplorer />
      </section>
    </div>
  );
}
