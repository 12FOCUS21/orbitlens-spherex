import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { defineConfig } from '@playwright/test'

const root = fileURLToPath(new URL('..', import.meta.url))
const port = Number(process.env.ORBITLENS_E2E_PORT ?? 8766)
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Puerto E2E inválido.')
const python = process.env.ORBITLENS_TEST_PYTHON ?? path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
const executablePath = process.env.ORBITLENS_BROWSER ?? (process.platform === 'win32' ? [
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
].find(existsSync) : undefined)

export default defineConfig({
  testDir: './e2e',
  testMatch: 'vanilla.spec.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    browserName: 'chromium',
    launchOptions: { executablePath },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    serviceWorkers: 'block',
  },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1365, height: 900 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: `"${python}" -m uvicorn web_browser_server:app --app-dir tests --host 127.0.0.1 --port ${port} --no-proxy-headers`,
    cwd: root,
    url: `http://127.0.0.1:${port}/api/health`,
    reuseExistingServer: false,
    timeout: 45_000,
    env: { ORBITLENS_REQUIRE_PRESETS: '1' },
  },
})
