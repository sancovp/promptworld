import { loader } from "@monaco-editor/react";

// Monaco is SELF-HOSTED, not loaded from a CDN. The build step copies node_modules/monaco-editor/
// min/vs into dist/monaco/vs, and the server serves it at /monaco/vs (see promptworld_server
// _mount_frontend). Pointing the AMD loader at the same-origin /monaco/vs means the editor renders
// regardless of the browser's internet / any CDN being blocked — the fix for "Monaco doesn't render".
// (We can't let vite BUNDLE monaco — that OOMs the build at low RAM — but serving the pre-built
//  min/vs as static files involves no bundling, so there is no OOM.)
loader.config({
  paths: { vs: "/monaco/vs" },
});
