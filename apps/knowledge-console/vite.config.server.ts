import { defineConfig } from "vite";

// Server build: bundle the Node HTTP server (src/server/index.ts) to
// dist-server/index.js. Node built-ins and node_modules stay external.
export default defineConfig({
  build: {
    outDir: "dist-server",
    ssr: "src/server/index.ts",
    target: "node18",
    rollupOptions: {
      output: { entryFileNames: "index.js" },
    },
  },
  ssr: {
    // App code (route modules, lib) is bundled; deps resolve from node_modules.
    noExternal: [],
  },
});
