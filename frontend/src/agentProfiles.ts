import { useSyncExternalStore } from "react";

/**
 * agentProfiles — the per-agent PROFILE (V2 (a)(b)): customizable DISPLAY NAME + AVATAR, fetched
 * from /api/agents/{alias}/profile and cached in a small useSyncExternalStore store so that saving
 * a profile re-renders EVERY header showing that agent (Main + Specialist + Group, the selector).
 *
 * The avatar is uploaded as a base64 data URL in the PUT body (the file input is read client-side
 * via FileReader + downscaled on a canvas); the server saves it and returns a served URL.
 */
export interface AgentProfile {
  alias: string;
  display_name: string | null;
  avatar: string | null; // served URL (cache-busted) or null
}

export async function getProfile(alias: string): Promise<AgentProfile> {
  const r = await fetch(`/api/agents/${encodeURIComponent(alias)}/profile`);
  if (!r.ok) throw new Error(`profile ${alias}: ${r.status}`);
  return r.json();
}

export async function saveProfile(
  alias: string,
  patch: { display_name?: string | null; avatar?: string | null },
): Promise<AgentProfile> {
  const r = await fetch(`/api/agents/${encodeURIComponent(alias)}/profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) {
    let detail = `${r.status}`;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(`save profile ${alias}: ${detail}`);
  }
  const prof: AgentProfile = await r.json();
  setStored(alias, prof);
  return prof;
}

// ---- tiny reactive store (one snapshot per alias) ----------------------------
const store = new Map<string, AgentProfile>();
const listeners = new Map<string, Set<() => void>>();
const fetched = new Set<string>();

function emit(alias: string) {
  listeners.get(alias)?.forEach((l) => l());
}

function setStored(alias: string, prof: AgentProfile) {
  store.set(alias, prof);
  emit(alias);
}

function subscribe(alias: string, cb: () => void): () => void {
  let set = listeners.get(alias);
  if (!set) listeners.set(alias, (set = new Set()));
  set.add(cb);
  // lazy first fetch (once per alias)
  if (!fetched.has(alias)) {
    fetched.add(alias);
    getProfile(alias)
      .then((p) => setStored(alias, p))
      .catch(() => {
        /* leave the default snapshot */
      });
  }
  return () => set!.delete(cb);
}

const EMPTY: AgentProfile = { alias: "", display_name: null, avatar: null };

/**
 * useAgentProfile — the live profile for an alias. Returns {alias, display_name, avatar}; the
 * fields are null until fetched / set. Re-renders when saveProfile updates this alias.
 */
export function useAgentProfile(alias: string): AgentProfile {
  return useSyncExternalStore(
    (cb) => subscribe(alias, cb),
    () => store.get(alias) ?? EMPTY,
    () => store.get(alias) ?? EMPTY,
  );
}

/**
 * fileToAvatarDataUrl — read a chosen image File, downscale it on a canvas to a square <= `size`px
 * (keeps the stored avatar small + the circle crisp), and return a PNG/JPEG data URL ready to PUT.
 * SVGs are passed through unscaled (canvas can't reliably rasterize them here). Falls back to the
 * raw FileReader data URL if canvas processing fails.
 */
export function fileToAvatarDataUrl(file: File, size = 256): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("could not read file"));
    reader.onload = () => {
      const raw = String(reader.result || "");
      if (file.type === "image/svg+xml" || !raw.startsWith("data:image/")) {
        resolve(raw);
        return;
      }
      const img = new Image();
      img.onload = () => {
        try {
          const side = Math.min(img.width, img.height) || size;
          const sx = (img.width - side) / 2;
          const sy = (img.height - side) / 2;
          const canvas = document.createElement("canvas");
          canvas.width = size;
          canvas.height = size;
          const ctx = canvas.getContext("2d");
          if (!ctx) {
            resolve(raw);
            return;
          }
          ctx.drawImage(img, sx, sy, side, side, 0, 0, size, size);
          const mime = file.type === "image/png" ? "image/png" : "image/jpeg";
          resolve(canvas.toDataURL(mime, 0.9));
        } catch {
          resolve(raw);
        }
      };
      img.onerror = () => resolve(raw);
      img.src = raw;
    };
    reader.readAsDataURL(file);
  });
}
