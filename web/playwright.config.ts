import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/browser",
  retries: 0,
  workers: 2,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3101",
    channel: process.env.PW_CHANNEL ?? "chromium",
  },
  webServer: [
    {
      command: "next start --hostname 127.0.0.1 --port 3101",
      url: "http://127.0.0.1:3101",
      env: { FIELDSHIFT_DATA_MODE: "fixture" },
      reuseExistingServer: false,
    },
    {
      command: "next start --hostname 127.0.0.1 --port 3102",
      url: "http://127.0.0.1:3102",
      env: { FIELDSHIFT_DATA_MODE: "api" },
      reuseExistingServer: false,
    },
  ],
});
