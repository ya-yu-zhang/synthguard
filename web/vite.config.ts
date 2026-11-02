import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// The Python server (synthguard ui) serves the build: "/" -> index.html, "/static/*" -> files.
// The output is committed, so machines that only run the UI never need Node.
export default defineConfig({
  base: "/static/",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  build: {
    outDir: "../src/synthguard/ui_static",
    emptyOutDir: true,
    assetsDir: "assets",
    chunkSizeWarningLimit: 900,
    // the minifier strips license comments; ship the bundled packages' licenses beside the build
    license: { fileName: "THIRD_PARTY_LICENSES.md" },
  },
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
})
