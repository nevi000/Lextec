// Regenerates src/types/api.d.ts from the FastAPI OpenAPI schema (no running server needed).
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const apiDir = path.resolve(here, "../../api");
const python = process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python";
const json = execFileSync(
  path.join(apiDir, python),
  ["-W", "ignore", "-c", "import json; from app.main import app; print(json.dumps(app.openapi()))"],
  { cwd: apiDir, encoding: "utf8", env: { ...process.env, AI_PROVIDER: "mock", AUTO_MIGRATE: "false" } },
);
const tmp = path.join(mkdtempSync(path.join(os.tmpdir(), "lextec-")), "openapi.json");
writeFileSync(tmp, json);
execFileSync("npx", ["openapi-typescript", tmp, "-o", path.resolve(here, "../src/types/api.d.ts")], {
  stdio: "inherit",
  shell: true,
});
console.log("Generated src/types/api.d.ts");
