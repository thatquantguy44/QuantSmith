import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";
import { devApi } from "./vite-plugins/dev-api";

// Client build + dev server.
//   normal            -> dist/, served by the Node server; devApi handles /api/*
//                         in dev by dispatching to the same file-system route
//                         modules the production server uses.
//   SINGLEFILE=1       -> one self-contained HTML file (all JS/CSS inlined) for
//                         a shareable, server-less snapshot (paired with
//                         VITE_HASH_ROUTER=1 and a model injected by
//                         build-snapshot.py). devApi is dropped since there is
//                         no dev server in that mode.
const singlefile = process.env.SINGLEFILE === "1";

export default defineConfig({
  base: "./",
  plugins: [react(), ...(singlefile ? [viteSingleFile()] : [devApi()])],
  build: {
    outDir: singlefile ? "dist-single" : "dist",
    target: "es2020",
    assetsInlineLimit: singlefile ? 100_000_000 : 4096,
    cssCodeSplit: !singlefile,
    chunkSizeWarningLimit: 2000,
  },
});
