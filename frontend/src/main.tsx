import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./monacoSetup"; // point the Monaco loader at the SELF-HOSTED /monaco/vs — runs before App
import "./index.css"; // Tailwind base/utilities + shadcn theme vars (powers the shadcn editor workbench)
import "@assistant-ui/react-ui/styles/index.css"; // PREBUILT assistant-ui chat theme (styled Thread + markdown)
import "./styles.css"; // our layout (panes/gallery/explorer/terminal) — last (composes on top)

// assistant-ui's theme ships its dark palette under a `.dark` ancestor (shadcn convention). Our app
// is dark, so opt in explicitly (don't rely on the browser's prefers-color-scheme).
document.documentElement.classList.add("dark");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
