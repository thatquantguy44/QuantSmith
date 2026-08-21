import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

// Two build modes:
//   normal      -> dist/ with separate hashed assets, served by the Python API.
//   SINGLEFILE  -> one self-contained index.html (all JS/CSS inlined) for the
//                  shareable snapshot / Artifact (spec REQ-012, NFR-002).
const singlefile = process.env.SINGLEFILE === "1";

export default defineConfig({
  base: "./",
  plugins: [react(), ...(singlefile ? [viteSingleFile()] : [])],
  build: {
    target: "es2020",
    // No external hosts, no remote fonts (spec NFR-002): everything is bundled.
    assetsInlineLimit: singlefile ? 100_000_000 : 4096,
    cssCodeSplit: !singlefile,
    chunkSizeWarningLimit: 2000,
  },
});
