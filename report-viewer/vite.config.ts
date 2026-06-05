import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base so the built dashboard works when opened from any path
// (e.g. a CI artifact server or a sub-directory), not just the domain root.
export default defineConfig({
  base: "./",
  plugins: [react()],
});
