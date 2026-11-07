import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Isolated ports + throw-away DB so e2e never touches your dev data.
const API_PORT = 8100;
const WEB_PORT = 5273;
const apiDir = path.resolve(__dirname, "../api");
const win = process.platform === "win32";
const python = path.join(apiDir, ".venv", win ? "Scripts" : "bin", win ? "python.exe" : "python");

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${WEB_PORT}`, trace: "retain-on-failure", locale: "de-CH" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      // FIXTURE snapshots (origin FIXTURE, labelled as test data) so the briefing shows cached sources without Fedlex.
      command: `"${python}" -m app.cli fedlex seed-fixtures && "${python}" -m uvicorn app.main:app --port ${API_PORT}`,
      cwd: apiDir,
      url: `http://localhost:${API_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        AI_PROVIDER: "mock",
        GEMINI_API_KEY: "", // e2e must never use the real key from .env
        APP_TODAY: "2026-11-07", // reproducible "days since receipt"
        APP_ENV: "test",
        DATABASE_URL: `sqlite:///${path.resolve(__dirname, "test-results", `e2e-${Date.now()}.db`).split(path.sep).join("/")}`,
      },
    },
    {
      command: "npx vite",
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: { VITE_PORT: String(WEB_PORT), VITE_API_PROXY: `http://localhost:${API_PORT}` },
    },
  ],
});
