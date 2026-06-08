import { useCallback, useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  Folder,
  FolderOpen,
  FolderPlus,
  FileText,
  FilePlus,
  Save,
  RefreshCw,
  Plus,
  Pencil,
  Trash2,
  X,
} from "lucide-react";
import {
  getTree,
  readFile,
  writeFile,
  makeDir,
  deletePath,
  renamePath,
  languageForPath,
  type TreeNode,
} from "../fileApi";
import { onOpenFile } from "../editorBus";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { cn } from "@/lib/utils";

// MAXIMUM Monaco workbench, ported from heaven_chat_v2's file-editor (shadcn Card/Button/Input/
// ScrollArea + lucide icons) and EXTENDED with multiple-open-file TABS. The file backend is rewired
// to PromptWorld's path-jailed /api/files (no docker-exec). Monaco is self-hosted (/monaco/vs).

interface Tab {
  path: string;
  content: string;
  dirty: boolean;
}

function basename(p: string): string {
  const parts = p.split("/");
  return parts[parts.length - 1] || p;
}

function dirname(p: string): string {
  const i = p.lastIndexOf("/");
  return i < 0 ? "" : p.slice(0, i);
}

export function FileExplorer() {
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [tabs, setTabs] = useState<Tab[]>([]);
  const [activePath, setActivePath] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [newName, setNewName] = useState("");
  const [newDir, setNewDir] = useState("");
  const [theme, setTheme] = useState("vs-dark"); // heaven's editor Settings: Monaco theme
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const tabsRef = useRef<Tab[]>([]);
  const activeRef = useRef<string | null>(null);
  tabsRef.current = tabs;
  activeRef.current = activePath;

  const active = tabs.find((t) => t.path === activePath) ?? null;

  const refreshTree = useCallback(async () => {
    try {
      setBusy(true);
      const t = await getTree();
      setTree(t.tree);
    } catch (e: any) {
      setStatus("tree error: " + e.message);
    } finally {
      setBusy(false);
    }
  }, []);

  const open = useCallback(async (path: string) => {
    if (tabsRef.current.find((t) => t.path === path)) {
      setActivePath(path);
      return;
    }
    try {
      const f = await readFile(path);
      setTabs((prev) => [...prev, { path, content: f.content, dirty: false }]);
      setActivePath(path);
      setStatus(`opened ${path}`);
    } catch (e: any) {
      setStatus(`open error: ${e.message}`);
    }
  }, []);

  const closeTab = useCallback((path: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setTabs((prev) => {
      const idx = prev.findIndex((t) => t.path === path);
      const next = prev.filter((t) => t.path !== path);
      if (activeRef.current === path) {
        const fb = next[idx] ?? next[idx - 1] ?? next[next.length - 1] ?? null;
        setActivePath(fb ? fb.path : null);
      }
      return next;
    });
  }, []);

  const onChange = useCallback((value: string | undefined) => {
    const path = activeRef.current;
    if (!path) return;
    setTabs((prev) => prev.map((t) => (t.path === path ? { ...t, content: value ?? "", dirty: true } : t)));
  }, []);

  const save = useCallback(async () => {
    const path = activeRef.current;
    if (!path) return;
    const tab = tabsRef.current.find((t) => t.path === path);
    if (!tab) return;
    try {
      const r = await writeFile(path, tab.content);
      setTabs((prev) => prev.map((t) => (t.path === path ? { ...t, dirty: false } : t)));
      setStatus(`saved ${path} (${r.bytes} bytes)`);
    } catch (e: any) {
      setStatus(`save error: ${e.message}`);
    }
  }, []);

  const createFile = useCallback(async () => {
    const name = newName.trim();
    if (!name) return;
    try {
      await writeFile(name, "");
      setNewName("");
      setStatus(`created ${name}`);
      await refreshTree();
      open(name);
    } catch (e: any) {
      setStatus(`create error: ${e.message}`);
    }
  }, [newName, refreshTree, open]);

  const createFolder = useCallback(async () => {
    const name = newDir.trim();
    if (!name) return;
    try {
      await makeDir(name);
      setNewDir("");
      setStatus(`created folder ${name}`);
      await refreshTree();
    } catch (e: any) {
      setStatus(`mkdir error: ${e.message}`);
    }
  }, [newDir, refreshTree]);

  const remove = useCallback(
    async (path: string, e?: React.MouseEvent) => {
      e?.stopPropagation();
      try {
        await deletePath(path);
        setTabs((prev) => prev.filter((t) => t.path !== path));
        if (activeRef.current === path) setActivePath(null);
        setStatus(`deleted ${path}`);
        await refreshTree();
      } catch (err: any) {
        setStatus(`delete error: ${err.message}`);
      }
    },
    [refreshTree],
  );

  // Context-menu actions. `baseDir` = the folder to create inside (a dir node's own path, or a
  // file node's parent). Names come from a prompt (kept simple + reliable).
  const createAt = useCallback(
    async (baseDir: string, kind: "file" | "dir") => {
      const label = kind === "file" ? "New file name:" : "New folder name:";
      const name = window.prompt(label);
      if (!name || !name.trim()) return;
      const rel = baseDir ? `${baseDir}/${name.trim()}` : name.trim();
      try {
        if (kind === "file") {
          await writeFile(rel, "");
          await refreshTree();
          open(rel);
        } else {
          await makeDir(rel);
          await refreshTree();
        }
        setStatus(`created ${rel}`);
      } catch (e: any) {
        setStatus(`create error: ${e.message}`);
      }
    },
    [refreshTree, open],
  );

  const renameNode = useCallback(
    async (path: string) => {
      const next = window.prompt("Rename to:", basename(path));
      if (!next || !next.trim() || next.trim() === basename(path)) return;
      const dir = dirname(path);
      const to = dir ? `${dir}/${next.trim()}` : next.trim();
      try {
        await renamePath(path, to);
        // keep an open tab pointing at the renamed file
        setTabs((prev) => prev.map((t) => (t.path === path ? { ...t, path: to } : t)));
        if (activeRef.current === path) setActivePath(to);
        setStatus(`renamed ${path} -> ${to}`);
        await refreshTree();
      } catch (e: any) {
        setStatus(`rename error: ${e.message}`);
      }
    },
    [refreshTree],
  );

  const toggleDir = (path: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });

  // external "open this file" requests (e.g. the profile editor's Edit-prompt button)
  useEffect(() => onOpenFile((path) => open(path)), [open]);

  // initial tree + live /ws file_changed handling
  useEffect(() => {
    refreshTree();
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws`);
    ws.onmessage = (e) => {
      let obj: any;
      try {
        obj = JSON.parse(e.data);
      } catch {
        return;
      }
      if (obj?.type !== "file_changed") return;
      // Fetch the fresh tree, update it, AND use it to decide whether to reload an open tab.
      // Reloading only when the path STILL EXISTS avoids a readFile() on a just-DELETED file
      // (delete broadcasts file_changed for the now-gone path) — which would 404 in the console.
      getTree()
        .then((t) => {
          setTree(t.tree);
          const present = new Set<string>();
          const collect = (ns: TreeNode[]) =>
            ns.forEach((n) => (n.type === "file" ? present.add(n.path) : n.children && collect(n.children)));
          collect(t.tree);
          if (obj.path && present.has(obj.path)) {
            const tab = tabsRef.current.find((tt) => tt.path === obj.path);
            if (tab && !tab.dirty) {
              readFile(obj.path)
                .then((f) =>
                  setTabs((prev) => prev.map((tt) => (tt.path === obj.path ? { ...tt, content: f.content } : tt))),
                )
                .catch(() => {});
            }
          }
        })
        .catch(() => {});
    };
    return () => ws.close();
  }, [refreshTree]);

  // recursive tree
  const renderTree = (nodes: TreeNode[], depth = 0) =>
    nodes.map((n) => {
      if (n.type === "dir") {
        const isOpen = !collapsed.has(n.path);
        return (
          <div key={n.path} className="flex flex-col">
            <ContextMenu>
              <ContextMenuTrigger asChild>
                <div
                  className="tree-dir group flex items-center rounded px-1 py-0.5 hover:bg-accent cursor-pointer"
                  style={{ paddingLeft: depth * 12 + 4 }}
                  onClick={() => toggleDir(n.path)}
                >
                  {isOpen ? (
                    <FolderOpen className="h-4 w-4 mr-1.5 shrink-0 text-amber-400" />
                  ) : (
                    <Folder className="h-4 w-4 mr-1.5 shrink-0 text-amber-400" />
                  )}
                  <span className="text-sm truncate flex-1">{n.name}</span>
                  <button
                    className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-destructive/20"
                    title="Delete folder"
                    onClick={(e) => remove(n.path, e)}
                  >
                    <Trash2 className="h-3 w-3 text-muted-foreground" />
                  </button>
                </div>
              </ContextMenuTrigger>
              <ContextMenuContent>
                <ContextMenuItem onSelect={() => createAt(n.path, "file")}>
                  <FilePlus /> New File
                </ContextMenuItem>
                <ContextMenuItem onSelect={() => createAt(n.path, "dir")}>
                  <FolderPlus /> New Folder
                </ContextMenuItem>
                <ContextMenuSeparator />
                <ContextMenuItem onSelect={() => renameNode(n.path)}>
                  <Pencil /> Rename
                </ContextMenuItem>
                <ContextMenuItem className="text-destructive focus:text-destructive" onSelect={() => remove(n.path)}>
                  <Trash2 /> Delete
                </ContextMenuItem>
              </ContextMenuContent>
            </ContextMenu>
            {isOpen && n.children && n.children.length > 0 && renderTree(n.children, depth + 1)}
          </div>
        );
      }
      return (
        <ContextMenu key={n.path}>
          <ContextMenuTrigger asChild>
            <div
              className={cn(
                "tree-file group flex items-center rounded px-1 py-0.5 cursor-pointer hover:bg-accent",
                activePath === n.path && "bg-accent",
              )}
              style={{ paddingLeft: depth * 12 + 4 }}
              onClick={() => open(n.path)}
              title={n.path}
            >
              <FileText className="h-4 w-4 mr-1.5 shrink-0 text-sky-400" />
              <span className="text-sm truncate flex-1">{n.name}</span>
              <button
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-destructive/20"
                title="Delete file"
                onClick={(e) => remove(n.path, e)}
              >
                <Trash2 className="h-3 w-3 text-muted-foreground" />
              </button>
            </div>
          </ContextMenuTrigger>
          <ContextMenuContent>
            <ContextMenuItem onSelect={() => createAt(dirname(n.path), "file")}>
              <FilePlus /> New File
            </ContextMenuItem>
            <ContextMenuItem onSelect={() => createAt(dirname(n.path), "dir")}>
              <FolderPlus /> New Folder
            </ContextMenuItem>
            <ContextMenuSeparator />
            <ContextMenuItem onSelect={() => renameNode(n.path)}>
              <Pencil /> Rename
            </ContextMenuItem>
            <ContextMenuItem className="text-destructive focus:text-destructive" onSelect={() => remove(n.path)}>
              <Trash2 /> Delete
            </ContextMenuItem>
          </ContextMenuContent>
        </ContextMenu>
      );
    });

  return (
    <Card className="flex h-full w-full min-w-0 flex-1 flex-col overflow-hidden rounded-none border-0">
      <CardHeader className="flex-none border-b p-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">Workspace</CardTitle>
          <div className="flex items-center gap-2">
            {/* heaven editor Settings: Monaco theme select */}
            <Select value={theme} onValueChange={setTheme}>
              <SelectTrigger className="h-8 w-[150px] text-xs" title="Editor theme">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="vs-dark">Dark</SelectItem>
                <SelectItem value="vs-light">Light</SelectItem>
                <SelectItem value="hc-black">High Contrast Dark</SelectItem>
                <SelectItem value="hc-light">High Contrast Light</SelectItem>
              </SelectContent>
            </Select>
            {active && (
              <Button variant="outline" size="sm" onClick={save} disabled={!active.dirty}>
                <Save className="mr-1 h-4 w-4" />
                Save
              </Button>
            )}
            <Button variant="outline" size="icon" className="h-8 w-8" onClick={refreshTree} title="Refresh">
              <RefreshCw className={cn("h-4 w-4", busy && "animate-spin")} />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 overflow-hidden p-0">
        {/* TREE SIDEBAR */}
        <div className="flex w-60 flex-none flex-col overflow-hidden border-r">
          <div className="flex flex-col gap-1 border-b p-2">
            <div className="flex items-center gap-1">
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && createFile()}
                placeholder="new/file.py"
                className="h-8 text-xs"
              />
              <Button variant="outline" size="sm" className="h-8" onClick={createFile} disabled={!newName.trim()} title="New file">
                <Plus className="h-3 w-3" />
              </Button>
            </div>
            <div className="flex items-center gap-1">
              <Input
                value={newDir}
                onChange={(e) => setNewDir(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && createFolder()}
                placeholder="new/folder"
                className="h-8 text-xs"
              />
              <Button variant="outline" size="sm" className="h-8" onClick={createFolder} disabled={!newDir.trim()} title="New folder">
                <FolderPlus className="h-3 w-3" />
              </Button>
            </div>
          </div>
          <ScrollArea className="flex-1">
            <div className="p-1">
              {tree.length > 0 ? (
                renderTree(tree)
              ) : (
                <div className="p-4 text-center text-xs text-muted-foreground">Empty workspace</div>
              )}
            </div>
          </ScrollArea>
        </div>

        {/* EDITOR AREA */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* OPEN-FILE TABS */}
          <div className="flex items-stretch overflow-x-auto border-b bg-background">
            {tabs.length === 0 && (
              <span className="px-3 py-2 text-xs text-muted-foreground">No file open — pick one from the tree</span>
            )}
            {tabs.map((t) => (
              <div
                key={t.path}
                role="tab"
                onClick={() => setActivePath(t.path)}
                title={t.path}
                className={cn(
                  "editor-tab flex max-w-[220px] cursor-pointer items-center gap-2 border-r px-3 py-2 text-sm",
                  t.path === activePath
                    ? "bg-card text-foreground shadow-[inset_0_2px_0_hsl(var(--primary))]"
                    : "text-muted-foreground hover:bg-accent",
                )}
              >
                <span className="truncate">{basename(t.path)}</span>
                <span
                  className="rounded p-0.5 hover:bg-accent"
                  onClick={(e) => closeTab(t.path, e)}
                  title="Close"
                >
                  {t.dirty ? <span className="text-amber-400">●</span> : <X className="h-3 w-3" />}
                </span>
              </div>
            ))}
          </div>

          {/* MONACO */}
          <div className="relative flex-1">
            {active ? (
              <Editor
                theme={theme}
                path={active.path}
                language={languageForPath(active.path)}
                value={active.content}
                onChange={onChange}
                onMount={(editor, monaco) => {
                  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => save());
                }}
                options={{ fontSize: 13, minimap: { enabled: true }, wordWrap: "on", automaticLayout: true }}
              />
            ) : (
              <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
                <FileText className="mb-3 h-14 w-14 opacity-20" />
                <p className="text-sm">Open a file to start editing</p>
              </div>
            )}
          </div>
          <div className="flex-none border-t px-3 py-1 font-mono text-xs text-muted-foreground">
            {active ? active.path : ""}
            {active?.dirty ? "  ●" : ""}
            {status ? `   ${status}` : ""}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
