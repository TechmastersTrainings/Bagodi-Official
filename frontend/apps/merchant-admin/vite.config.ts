import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@bagodi/api-client": path.resolve(__dirname, "../../packages/api-client/src"),
    },
  },
  server: {
    port: 5175,
    proxy: {
      "/api/v1": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 5175,
    proxy: {
      "/api/v1": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
    },
  },
});
