import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const dir = dirname(fileURLToPath(import.meta.url));

function stripLclPreloadFromIndex() {
  return {
    name: "strip-lcl-preload-from-index",
    transformIndexHtml: {
      order: "post",
      handler(html, ctx) {
        const file = String(ctx.filename || ctx.path || "").replace(/\\/g, "/");
        if (!file.endsWith("/index.html") && file !== "index.html") {
          return html;
        }
        return html
          .replace(/\s*<link rel="modulepreload"[^>]*lcl-[^>]*>/g, "")
          .replace(/\s*<link rel="modulepreload"[^>]*Gca[^>]*>/g, "")
          .replace(/\s*<link rel="modulepreload"[^>]*gca-[^>]*>/g, "");
      },
    },
  };
}

export default defineConfig({
  plugins: [react(), stripLclPreloadFromIndex()],
  base: process.env.VITE_BASE || "/",
  build: {
    rollupOptions: {
      input: {
        main: resolve(dir, "index.html"),
        lcl: resolve(dir, "lcl.html"),
      },
      output: {
        manualChunks(id) {
          if (id.includes("worldCountries") || id.includes("src/Lcl")) {
            return "lcl";
          }
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
    },
  },
});
