import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: "./" so the built bundle works from any static path (repro-friendly).
export default defineConfig({
  base: "./",
  plugins: [react()],
});
