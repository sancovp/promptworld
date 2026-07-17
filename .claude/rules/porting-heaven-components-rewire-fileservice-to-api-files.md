# Porting Heaven Frontend Components → Rewire The File Backend From docker-exec To PromptWorld `/api/files`

The maximum-quality Monaco workbench to reuse lives in heaven_chat_v2:
`/home/GOD/heaven_chat_v2/components/file-explorer/file-editor.tsx` (614 lines — tree explorer + tabs +
Monaco + new-file/delete/save), plus `improved-file-editor.tsx`, and its `@/services/file-service` /
`@/services/docker-operations`. PORT the component (the UI is excellent), but **its file backend is the
KNOWN-BROKEN part and MUST be rewired.**

## The rewire (required)
Replace heaven's docker-exec FileService with calls to **PromptWorld's existing file API** (plain,
path-jailed Python I/O over `/workspace` — `server/file_api.py`, no docker-exec, no base64):
- tree   → `GET /api/files/tree`
- read   → `GET /api/files/read?path=...` (or the existing read endpoint)
- write  → `POST /api/files/write` `{path, content}`
Keep the heaven component's UI/UX (tree, tabs, dirty dots, close, save, Ctrl/Cmd-S, `/ws file_changed`
reload) — only swap the data layer. Keep PromptWorld's self-hosted Monaco (`/monaco/vs`, no CDN).

→ Why / history / how-to behind this rule: read the `understand-promptworld-rules` skill.
