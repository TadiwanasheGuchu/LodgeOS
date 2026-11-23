import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against the real API and database.
 * Requires PostgreSQL and Redis from docker-compose, migrations applied, and a
 * production build of the frontend (`npm run build`).
 */
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  workers: 1,
  // No retries: the specs run in order and build on each other's data, so a retried test
  // re-creates records that already exist and hides the first, real failure.
  retries: 0,
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "off",
    // Kept for the CI artifact when something fails.
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] }, testIgnore: /mobile\.spec\.ts/ },
    { name: "phone", use: { ...devices["Pixel 7"] }, testMatch: /mobile\.spec\.ts/ },
  ],
  webServer: [
    {
      command: "uv run uvicorn app.main:app --port 8000",
      // Request log in CI output, to see whether the API received a stalled request.
      stdout: process.env.CI ? "pipe" : "ignore",
      cwd: "../backend",
      url: "http://127.0.0.1:8000/health/ready",
      reuseExistingServer: !process.env.CI,
      env: { LODGEOS_COOKIE_SECURE: "false" },
    },
    {
      command: "npm run start -- --port 3000",
      url: "http://localhost:3000/sign-in",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
