import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: '../tests/e2e', fullyParallel: true, workers: 2,
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure',
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } },
  projects: [
    { name: 'desktop-chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile-chromium', use: { ...devices['Pixel 7'], viewport: { width: 360, height: 800 } } },
  ],
  webServer: [
    { command: '../backend/.venv/bin/uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8000', url: 'http://127.0.0.1:8000/api/v1/health/ready', reuseExistingServer: !process.env.CI, timeout: 60000 },
    { command: 'npm run dev -- --host 127.0.0.1', url: 'http://127.0.0.1:5173', reuseExistingServer: !process.env.CI, timeout: 60000 },
  ],
})
