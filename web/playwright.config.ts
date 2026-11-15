import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/browser",
  retries: 0,
  workers: 2,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3001",
    channel: process.env.PW_CHANNEL ?? "chromium",
  },
  webServer: [
    {
      command: "npm start",
      url: "http://127.0.0.1:3001",
      env: { FIELDSHIFT_DATA_MODE: "fixture" },
      reuseExistingServer: true,
    },
    {
      command: "next start --hostname 127.0.0.1 --port 3002",
      url: "http://127.0.0.1:3002",
      env: { FIELDSHIFT_DATA_MODE: "api" },
      reuseExistingServer: false,
    },
  ],
});
