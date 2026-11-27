import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:3000",
    channel: process.env.CI ? undefined : "chrome",
    headless: true,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command:
        "cd ../backend && APP_ENV=development OTP_PROVIDER=console ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/api/v1/health",
      reuseExistingServer: !process.env.CI,
      timeout: 45_000,
    },
    {
      command: "npm run dev --workspace=@bagodi/customer-web -- --host 127.0.0.1 --port 3000",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 45_000,
    },
    {
      command: "npm run dev --workspace=@bagodi/merchant-admin -- --host 127.0.0.1 --port 3001",
      url: "http://127.0.0.1:3001",
      reuseExistingServer: !process.env.CI,
      timeout: 45_000,
    },
  ],
});

