import { expect, test, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
test.use({ actionTimeout: 15000, trace: 'off', screenshot: 'off', video: 'off' })
async function login(page: Page, campus: string, role = 'operations') {
  await page.goto('/admin'); await page.getByLabel('Username', { exact: true }).fill(`browser-${role}`); await page.getByLabel('Password', { exact: true }).fill(process.env.SCNS_E2E_PASSWORD!)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click(); await expect(page.getByRole('heading', { name: 'Admin dashboard' })).toBeVisible()
  await page.getByRole('combobox', { name: 'Assigned campus', exact: true }).selectOption({ label: campus }); await page.getByRole('button', { name: 'Closures and outages', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Closures and lift outages', exact: true })).toBeVisible()
}
async function fill(page: Page, reason = 'Synthetic Courtyard walkway incident, not a real closure.') {
  const targets = await page.getByRole('combobox', { name: 'Published restriction target', exact: true }).locator('option').allTextContents()
  const pair = targets.find(label => label.startsWith('outdoor_path ·') && label.includes('Courtyard → West'))!
  expect(pair).toBeTruthy()
  await page.getByRole('combobox', { name: 'Published restriction target', exact: true }).selectOption({ label: pair })
  await page.getByRole('textbox', { name: 'Public restriction reason', exact: true }).fill(reason)
}
async function reopen(page: Page) {
  await page.getByRole('textbox', { name: 'Reopening verification evidence', exact: true }).fill('Synthetic incident resolved in software; no physical verification. PRIVATE-EVIDENCE')
  await page.getByRole('checkbox', { name: 'I explicitly verified reopening or cancellation of this incident', exact: true }).check()
  await page.getByRole('button', { name: 'Verify and reopen', exact: true }).click()
  await expect(page.getByText('Operator-verified reopening recorded. Other restrictions remain in force.', { exact: true })).toBeVisible()
}
test('operational restriction changes route, hides stale results, preserves selections and verifies reopening', async ({ page, browser }, info) => {
  const campus = `Synthetic closures fixture ${info.project.name.startsWith('mobile') ? 'mobile' : 'desktop'}`
  await login(page, campus)
  const context = await browser.newContext({ viewport: page.viewportSize() ?? undefined }), publicPage = await context.newPage()
  try {
    await publicPage.goto('/'); await publicPage.getByRole('combobox', { name: 'Explore campus', exact: true }).selectOption({ label: campus })
    await publicPage.getByRole('combobox', { name: 'Destination', exact: true }).selectOption({ label: 'Library' })
    await publicPage.getByRole('button', { name: 'Find walking route', exact: false }).click(); await expect(publicPage.locator('.route-metrics')).toContainText('257')
    await fill(page)
    await page.getByRole('button', { name: 'Record restriction', exact: true }).click()
    await expect(page.getByText('Restriction recorded. Routes use the live overlay; drafts were not published.', { exact: true })).toBeVisible()
    await publicPage.getByRole('button', { name: 'Check restrictions', exact: true }).click()
    await expect(publicPage.getByRole('alert').filter({ hasText: 'Previous route hidden' })).toBeVisible()
    await expect(publicPage.locator('.route-details')).toHaveCount(0)
    await expect(publicPage.getByRole('combobox', { name: 'Destination', exact: true })).not.toHaveValue('')
    const computed = publicPage.waitForResponse(r => r.url().endsWith('/api/v1/routes'))
    await publicPage.getByRole('button', { name: 'Find walking route', exact: false }).click()
    const result = await (await computed).json(); expect(result.distance_m).toBe(310.2); expect(result.segments).toHaveLength(3); expect(result.closure_overlay_version).toBe(1)
    await expect(publicPage.locator('.route-details')).toBeVisible()
    await publicPage.getByRole('combobox', { name: 'Route preference', exact: true }).selectOption('step_free')
    const accessibleResponse = publicPage.waitForResponse(r => r.url().endsWith('/api/v1/routes'))
    await publicPage.getByRole('button', { name: 'Find walking route', exact: false }).click()
    const accessible = await (await accessibleResponse).json(); expect(accessible.distance_m).toBe(405.43); expect(accessible.segments).toHaveLength(4)
    await expect(publicPage.locator('.route-details')).toBeVisible()
    await publicPage.route('**/api/v1/campuses/*/closures', r => r.abort()); await publicPage.getByRole('button', { name: 'Check restrictions', exact: true }).click()
    await expect(publicPage.getByRole('alert').filter({ hasText: 'Previous route hidden' })).toBeVisible(); await expect(publicPage.getByRole('button', { name: 'Find walking route', exact: false })).toBeDisabled()
    await publicPage.unroute('**/api/v1/campuses/*/closures'); await publicPage.getByRole('button', { name: 'Check restrictions', exact: true }).click()
    await expect(publicPage.getByRole('button', { name: 'Find walking route', exact: false })).toBeEnabled(); await expect(publicPage.locator('.route-details')).toHaveCount(0)
    await page.getByRole('button', { name: /Courtyard.*West.*closed/ }).click(); await reopen(page)
    await publicPage.getByRole('button', { name: 'Check restrictions', exact: true }).click(); await publicPage.getByRole('button', { name: 'Find walking route', exact: false }).click(); await expect(publicPage.locator('.route-metrics')).toContainText('257')
    expect(await publicPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    expect((await new AxeBuilder({ page }).include('main').analyze()).violations).toEqual([])
    const status = await (await publicPage.request.get(`/api/v1/campuses/${result.campus_id}/closures`)).text(); expect(status).not.toContain('PRIVATE-EVIDENCE')
  } finally { await context.close() }
})
test('stale overlay edits retain input, ambiguous-response retries stay duplicate-free and reviewers are read-only', async ({ page, browser }, info) => {
  const campus = `Synthetic closures conflicts fixture ${info.project.name.startsWith('mobile') ? 'mobile' : 'desktop'}`
  await login(page, campus)
  const context = await browser.newContext({ viewport: page.viewportSize() ?? undefined }), other = await context.newPage()
  try {
    await login(other, campus)
    await fill(page, 'A retained synthetic restriction reason.')
    await fill(other, 'B independent synthetic restriction reason.')
    await other.getByRole('button', { name: 'Record restriction', exact: true }).click(); await expect(other.getByText('Restriction recorded. Routes use the live overlay; drafts were not published.', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Record restriction', exact: true }).click(); await expect(page.getByRole('button', { name: 'Use latest overlay and keep my inputs', exact: true })).toBeVisible()
    await expect(page.getByRole('textbox', { name: 'Public restriction reason', exact: true })).toHaveValue('A retained synthetic restriction reason.')
    await page.getByRole('button', { name: 'Use latest overlay and keep my inputs', exact: true }).click()
    await page.route('**/api/v1/admin/campuses/*/closures', async r => { if (r.request().method() === 'POST') { await r.fetch(); await r.abort() } else await r.continue() })
    await page.getByRole('button', { name: 'Record restriction', exact: true }).click(); await expect(page.getByRole('button', { name: 'Retry unchanged operation', exact: true })).toBeVisible()
    await expect(page.getByRole('textbox', { name: 'Public restriction reason', exact: true })).toBeDisabled()
    await page.unroute('**/api/v1/admin/campuses/*/closures'); await page.getByRole('button', { name: 'Retry unchanged operation', exact: true }).click()
    await expect(page.getByText('Restriction recorded. Routes use the live overlay; drafts were not published.', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: /Courtyard.*West.*closed/ })).toHaveCount(2)
    await other.getByRole('button', { name: 'Sign out', exact: true }).click(); await login(other, campus, 'reviewer_publisher')
    await expect(other.getByRole('button', { name: 'Record restriction', exact: true })).toHaveCount(0)
    await expect(other.getByText('Read-only operational history.', { exact: false })).toBeVisible()
  } finally { await context.close() }
})
