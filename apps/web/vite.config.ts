/// <reference types="vitest/config" />
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const apiTarget = process.env.VITE_API_PROXY ?? "http://localhost:8000";
// VITE_HOST=0.0.0.0 (dev.ps1 -Lan) lets a phone on the same network open the app; the API itself stays on localhost.
const host = process.env.VITE_HOST ?? "localhost";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    host,
    port: Number(process.env.VITE_PORT ?? 5173),
    strictPort: true,
    // xfwd adds the caller's address: the API only lets non-local callers use the phone endpoints
    proxy: { "/api": { target: apiTarget, changeOrigin: false, xfwd: true } },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
