import * as nodePath from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const CONFIG_DIR = nodePath.dirname(fileURLToPath(import.meta.url));
process.env.RAZORMESH_GOLD_DIR =
  process.env.RAZORMESH_GOLD_DIR ??
  nodePath.resolve(CONFIG_DIR, "../../data/phase3/gold");

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: 0,
  use: {
    baseURL: process.env.RAZORMESH_E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.RAZORMESH_E2E_EXTERNAL
    ? undefined
    : {
        command: "pnpm dev",
        env: { RAZORMESH_REVIEWER_ENABLED: "1" },
        url: "http://localhost:3000",
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
