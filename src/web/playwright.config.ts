import { defineConfig, devices } from "@playwright/test";

const python = process.env.AI4MS_PYTHON || "python";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: `${python} -m uvicorn ai4ms.api.app:app --host 127.0.0.1 --port 8010`,
      url: "http://127.0.0.1:8010/healthz",
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      env: {
        PYTHONPATH: "../../src",
        AI4MS_DATA_DIR: "/tmp/ai4ms-playwright-workbench",
      },
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
      url: "http://127.0.0.1:3100",
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      env: {
        AI4MS_API_INTERNAL_URL: "http://127.0.0.1:8010",
      },
    },
  ],
});
