// Client for the PromptWorld workspace file API (path-jailed server-side).

export interface TreeNode {
  name: string;
  path: string;
  type: "dir" | "file";
  size?: number;
  children?: TreeNode[];
}

async function jsonOrThrow(r: Response, what: string) {
  if (!r.ok) {
    let detail = `${what} ${r.status}`;
    try {
      const e = await r.json();
      detail = e.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return r.json();
}

export async function getTree(): Promise<{ root: string; tree: TreeNode[] }> {
  return jsonOrThrow(await fetch("/api/files/tree"), "tree");
}

export async function readFile(path: string): Promise<{ path: string; content: string; size: number }> {
  return jsonOrThrow(await fetch("/api/files/read?path=" + encodeURIComponent(path)), "read");
}

export async function writeFile(path: string, content: string): Promise<{ ok: boolean; path: string; bytes: number }> {
  return jsonOrThrow(
    await fetch("/api/files/write", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path, content }),
    }),
    "write",
  );
}

export async function makeDir(path: string): Promise<{ ok: boolean; path: string; type: string }> {
  return jsonOrThrow(
    await fetch("/api/files/mkdir", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ path }),
    }),
    "mkdir",
  );
}

export async function deletePath(path: string): Promise<{ ok: boolean; path: string; type: string }> {
  return jsonOrThrow(
    await fetch("/api/files/delete?path=" + encodeURIComponent(path), { method: "DELETE" }),
    "delete",
  );
}

export async function renamePath(from: string, to: string): Promise<{ ok: boolean; from: string; to: string }> {
  return jsonOrThrow(
    await fetch("/api/files/rename", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ from, to }),
    }),
    "rename",
  );
}

/** Map a filename to a Monaco language id. */
export function languageForPath(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  const map: Record<string, string> = {
    py: "python", ts: "typescript", tsx: "typescript", js: "javascript", jsx: "javascript",
    json: "json", md: "markdown", css: "css", scss: "scss", html: "html", htm: "html",
    sh: "shell", bash: "shell", yml: "yaml", yaml: "yaml", toml: "ini", ini: "ini",
    sql: "sql", pl: "perl", rs: "rust", go: "go", java: "java", c: "c", cpp: "cpp", h: "cpp",
    txt: "plaintext",
  };
  return map[ext] ?? "plaintext";
}
