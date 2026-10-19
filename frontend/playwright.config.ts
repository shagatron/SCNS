import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: '../tests/e2e', fullyParallel: true, workers: 2,
  timeout: 60000, // Bounded multi-actor workflows include downloads and native section scrolling.
  use: { baseURL: process.env.SCNS_E2E_BUILT_URL ?? 'http://127.0.0.1:5174', trace: 'retain-on-failure',
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } },
  projects: [
    { name: 'desktop-chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile-chromium', use: { ...devices['Pixel 7'], viewport: { width: 360, height: 800 } } },
  ],
  webServer: process.env.SCNS_E2E_BUILT_URL ? undefined : [
    { command: '../backend/.venv/bin/uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8001', url: 'http://127.0.0.1:8001/api/v1/health/ready', reuseExistingServer: false, timeout: 60000 },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5174', url: 'http://127.0.0.1:5174', reuseExistingServer: false, timeout: 60000 },
  ],
})
