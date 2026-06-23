import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { viteSingleFile } from "vite-plugin-singlefile";

// The dashboard ships as ONE self-contained index.html: viteSingleFile inlines
// all JS/CSS so `agent-risk-scan report --html` can bake a report into a single
// clickable file (and so the built template can be vendored into the Python
// package). Relative base keeps it working from any path / file://.
// Styling is Tailwind v4 (CSS-first @theme in src/index.css); its Vite plugin
// scans the JSX for utility classes at build time.
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss(), viteSingleFile()],
});
