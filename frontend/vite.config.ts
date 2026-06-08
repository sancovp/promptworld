import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// base: "./" so the built asset URLs are relative — works when the FastAPI server
// serves dist/index.html at "/" and mounts dist/assets at "/assets".
export default defineConfig({
  plugins: [react()],
  base: "./",
  resolve: {
    // "@" -> src, so ported shadcn components (which import "@/lib/utils",
    // "@/components/ui/...") resolve verbatim.
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
