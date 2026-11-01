import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  use: {
    ...devices["Pixel 7"],
    browserName: "chromium",
    trace: "retain-on-failure",
  },
  webServer: [
    ...(process.env.GROCY_TEST_DIST
      ? [
          {
            command: "python3 ../../tests/real_stack_server.py",
            url: "http://127.0.0.1:8767/react/",
            reuseExistingServer: false,
          },
        ]
      : []),
    {
      command: "python3 ../../tests/preview_server.py",
      url: "http://127.0.0.1:8765/react/",
      reuseExistingServer: false,
    },
    {
      command: "python3 ../../tests/preview_server.py --ingress",
      url: "http://127.0.0.1:8766/api/hassio_ingress/browser-test/react/",
      reuseExistingServer: false,
    },
  ],
});
