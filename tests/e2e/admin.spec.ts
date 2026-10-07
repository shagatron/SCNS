import { expect, test, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

// Login request bodies and session tokens must never enter retained traces or screenshots.
test.use({ trace: 'off', screenshot: 'off', video: 'off' })

async function login(page: Page, role = 'owner') {
  const password = process.env.SCNS_E2E_PASSWORD
  if (!password) throw new Error('Run make test-e2e to provision isolated credentials.')
  await page.goto('/admin')
  await page.getByLabel('Username', { exact: true }).fill(`browser-${role}`)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Admin dashboard' })).toBeVisible()
}

async function draft(page: Page) {
  const created = page.waitForResponse(r => r.url().endsWith('/drafts') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Create draft from published release' }).click()
  const data = await (await created).json()
  await expect(page.getByRole('combobox', { name: 'Selected draft', exact: true })).toHaveValue(data.id)
  await expect(page.getByRole('button', { name: 'Add place', exact: true })).toBeEnabled()
  return data
}

async function save(page: Page) {
  await page.getByRole('button', { name: 'Save draft record' }).click()
  await expect(page.getByRole('status')).toContainText('Draft saved')
}

async function remove(page: Page, name: string) {
  await page.getByRole('button', { name: `Delete ${name}`, exact: true }).click()
  await page.getByRole('button', { name: 'Confirm delete', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Record deleted')
}

test('admin catalog CRUD, private drafts, audit, mobile layout and logout', async ({ page }) => {
  test.setTimeout(60000)
  await login(page)
  const created = await draft(page)
  const code = `UI_${test.info().project.name.startsWith('mobile') ? 'M' : 'D'}`
  await page.getByRole('button', { name: 'Buildings', exact: true }).click()
  await page.getByRole('button', { name: 'Add building', exact: true }).click()
  await page.getByLabel('Code', { exact: true }).fill(code)
  await page.getByLabel('Name', { exact: true }).fill('Private building')
  await page.getByLabel('Footprint coordinate rings', { exact: false }).fill('[[[0,0],[0.001,0],[0.001,0.001],[0,0]]]')
  await save(page)
  await page.getByRole('button', { name: 'Places', exact: true }).click()
  await page.getByRole('button', { name: 'Add place', exact: true }).click()
  await page.getByLabel('Code', { exact: true }).fill(code)
  await page.getByLabel('Name', { exact: true }).fill('Private destination')
  await page.getByRole('combobox', { name: 'Building', exact: true }).selectOption({ label: `${code} · Private building` })
  await page.getByLabel('Longitude', { exact: true }).fill('0.0005')
  await page.getByLabel('Latitude', { exact: true }).fill('0.0005')
  await save(page)
  await page.getByRole('button', { name: `Edit ${code} · Private destination`, exact: true }).click()
  await page.getByLabel('Name', { exact: true }).fill('Private destination revised')
  await save(page)
  const name = `${code} · Private destination revised`
  await page.getByRole('button', { name: 'Departments', exact: true }).click()
  await page.getByRole('button', { name: 'Add department', exact: true }).click()
  await page.getByLabel('Code', { exact: true }).fill(code)
  await page.getByLabel('Name', { exact: true }).fill('Private department')
  await page.getByRole('listbox', { name: /Associated places/ }).selectOption({ label: name })
  await save(page)
  await page.getByRole('button', { name: 'Aliases', exact: true }).click()
  await page.getByRole('button', { name: 'Add alias', exact: true }).click()
  await page.getByRole('combobox', { name: 'Place', exact: true }).selectOption({ label: name })
  await page.getByLabel('Alias', { exact: true }).fill('Unpublished alias')
  await save(page)
  await page.getByRole('button', { name: 'Anchors', exact: true }).click()
  await page.getByRole('button', { name: 'Add anchor', exact: true }).click()
  await page.getByRole('combobox', { name: 'Place', exact: true }).selectOption({ label: name })
  await page.getByRole('combobox', { name: 'Navigation node', exact: true }).selectOption({ index: 1 })
  await save(page)
  const publicSearch = await page.request.get(`/api/v1/campuses/${created.campus_id}/search?q=Private`)
  expect((await publicSearch.json()).total).toBe(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze()
  expect(accessibility.violations).toEqual([])
  await remove(page, `${name} · Anchor · unknown · open`)
  await page.getByRole('button', { name: 'Aliases', exact: true }).click()
  await remove(page, 'Unpublished alias (en)')
  await page.getByRole('button', { name: 'Departments', exact: true }).click()
  await remove(page, `${code} · Private department`)
  await page.getByRole('button', { name: 'Places', exact: true }).click()
  await remove(page, name)
  await page.getByRole('button', { name: 'Buildings', exact: true }).click()
  await remove(page, `${code} · Private building`)
  await page.getByRole('button', { name: 'Audit records', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'catalog.buildings.delete', exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Admin sign in' })).toBeVisible()
  expect((await page.request.get('/api/v1/admin/session')).status()).toBe(401)
})

test('stale edit preserves input and requires explicit reconciliation', async ({ page, context }) => {
  await login(page, 'editor')
  const created = await draft(page)
  const second = await context.newPage()
  await second.goto('/admin')
  await second.getByRole('combobox', { name: 'Selected draft', exact: true }).selectOption(created.id)
  for (const tab of [page, second]) await tab.getByRole('button', { name: 'Edit LIB · Library', exact: true }).click()
  await page.getByLabel('Name', { exact: true }).fill('First editor name')
  await save(page)
  await second.getByLabel('Name', { exact: true }).fill('Second editor input')
  await second.getByRole('button', { name: 'Save draft record' }).click()
  await expect(second.getByRole('alert')).toContainText('changed since you loaded')
  await expect(second.getByLabel('Name', { exact: true })).toHaveValue('Second editor input')
  await expect(second.getByRole('button', { name: 'Save draft record' })).toBeDisabled()
  await second.getByRole('button', { name: 'Load latest for comparison' }).click()
  await expect(second.locator('.admin-notice pre')).toContainText('First editor name')
  await second.getByRole('button', { name: /I have reconciled my input/ }).click()
  await save(second)
  const publicSearch = await page.request.get(`/api/v1/campuses/${created.campus_id}/search?q=books`)
  expect((await publicSearch.json()).items[0].name).toBe('Library')
  await second.close()
})

test('reviewer and operations roles expose only permitted controls', async ({ page }) => {
  await login(page, 'reviewer_publisher')
  await expect(page.getByRole('button', { name: 'Create draft from published release' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Users and roles', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Audit records', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Add place', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await login(page, 'operations')
  await expect(page.getByRole('heading', { name: 'Operations access' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Draft catalog', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Audit records', exact: true })).toHaveCount(0)
})

test('system administrator provisions and changes a campus role', async ({ page }) => {
  await login(page)
  await page.getByRole('button', { name: 'Users and roles', exact: true }).click()
  const username = `ui-${test.info().project.name}`
  await page.getByLabel('New username', { exact: true }).fill(username)
  await page.getByLabel('Display name', { exact: true }).fill('UI account')
  await page.getByLabel('Initial password', { exact: false }).fill(process.env.SCNS_E2E_PASSWORD!)
  await page.getByRole('combobox', { name: 'Campus role', exact: true }).selectOption('editor')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Campus account created')
  const row = page.locator('li').filter({ has: page.getByRole('combobox', { name: `Role for ${username}`, exact: true }) })
  await row.getByRole('combobox').selectOption('operations')
  await row.getByRole('button', { name: 'Replace campus roles' }).click()
  await expect(page.getByRole('status')).toContainText('Campus role updated')
  await expect(row).toContainText(`${username} · operations`)
})

test('fresh anonymous admin visit reaches normal login and stops checking the session', async ({ page }) => {
  let checks = 0
  page.on('request', request => { if (request.url().endsWith('/api/v1/admin/session')) checks++ })
  await page.goto('/admin', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Admin sign in', exact: true })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
  expect(checks).toBeLessThanOrEqual(2) // React StrictMode may cancel/restart one initial fetch.
  const settled = checks
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })
    window.dispatchEvent(new Event('visibilitychange'))
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
    window.dispatchEvent(new Event('visibilitychange'))
    Reflect.deleteProperty(document, 'visibilityState')
  })
  await page.waitForLoadState('networkidle')
  expect(checks).toBe(settled)
})

test('revocation of an established session returns to login once, while deliberate logout is quiet', async ({ page }) => {
  await login(page, 'operations')
  // Revoke on the server outside the UI's sign-out handler, as another tab could.
  // Test credentials/session tokens are ephemeral and tracing is disabled above.
  const current = await page.request.get('/api/v1/admin/session')
  const csrf = (await current.json()).csrf_token
  const revoked = await page.request.post('/api/v1/admin/logout', { headers: { Origin: 'http://127.0.0.1:5174', 'X-CSRF-Token': csrf } })
  expect(revoked.status()).toBe(204)
  let rechecks = 0
  page.on('request', request => { if (request.url().endsWith('/api/v1/admin/session')) rechecks++ })
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })
    window.dispatchEvent(new Event('visibilitychange'))
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
    window.dispatchEvent(new Event('visibilitychange'))
    Reflect.deleteProperty(document, 'visibilityState')
  })
  await expect(page.getByRole('heading', { name: 'Admin sign in', exact: true })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveText('Your session ended. Sign in to continue.')
  await page.waitForLoadState('networkidle')
  expect(rechecks).toBe(1)
  await page.getByLabel('Username', { exact: true }).fill('browser-operations')
  await page.getByLabel('Password', { exact: true }).fill(process.env.SCNS_E2E_PASSWORD!)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Admin dashboard' })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Admin sign in', exact: true })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await page.waitForLoadState('networkidle')
  expect(rechecks).toBe(1)
})
