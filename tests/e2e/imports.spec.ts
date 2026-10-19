import { expect, test, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test.use({ trace: 'off', screenshot: 'off', video: 'off' })
async function setup(page: Page, role = 'owner') {
  const password = process.env.SCNS_E2E_PASSWORD
  if (!password) throw new Error('Use make test-e2e for isolated credentials.')
  await page.goto('/admin')
  await page.getByLabel('Username', { exact: true }).fill(`browser-${role}`)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Admin dashboard' })).toBeVisible()
  if (role === 'owner' || role === 'editor') {
    const created = page.waitForResponse(r => r.url().endsWith('/drafts') && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Create draft from published release' }).click()
    const draft = await (await created).json()
    await expect(page.getByRole('combobox', { name: 'Selected draft', exact: true })).toHaveValue(draft.id)
    await expect(page.getByRole('button', { name: 'Add place', exact: true })).toBeEnabled()
  }
  await page.getByRole('button', { name: 'Data imports', exact: true }).click()
}
async function upload(page: Page, name: string, content: string, format: string) {
  await page.getByRole('combobox', { name: 'Import format', exact: true }).selectOption(format)
  await page.getByLabel('Data file', { exact: true }).setInputFiles({ name, mimeType: 'application/octet-stream', buffer: Buffer.from(content) })
  await page.getByLabel('Source rights / authorization').fill('Original synthetic test data')
  await page.getByLabel('Source and verification notes').fill('Isolated browser fixture; no field verification')
  await page.getByRole('button', { name: 'Upload to selected draft' }).click()
  await expect(page.getByLabel('Import preview').getByText('Job state: preview ready', { exact: false })).toBeVisible({ timeout: 30000 })
}
function bundle(records: unknown[]) {
  return JSON.stringify({ schema_version: 'import-v1', units: 'WGS84_degrees_and_metres', campus_code: 'DEMO', timezone: 'Asia/Kolkata', records })
}

test('staged bundle preview, draft apply, public isolation, diagnostics and responsive UI', async ({ page }) => {
  test.setTimeout(60000)
  await setup(page)
  const code = `IMPORT_${test.info().project.name.startsWith('mobile') ? 'M' : 'D'}`
  const publicCampus = (await (await page.request.get('/api/v1/campuses')).json())[0]
  const before = await (await page.request.get(`/api/v1/campuses/${publicCampus.id}/release`)).json()
  const records = [{ entity: 'places', external_id: `browser-${code}`, data: { code, name: 'Synthetic imported browser place', kind: 'help', point: { type: 'Point', coordinates: [0.001, 0.001] } } }]
  await upload(page, `${code}.json`, bundle(records), 'json')
  const preview = page.getByLabel('Import preview')
  await expect(preview).toContainText('Additions: 1')
  await preview.getByText('Compare current and proposed fields', { exact: true }).click()
  await expect(preview.getByRole('heading', { name: 'Proposed', exact: true })).toBeVisible()
  await expect(preview.getByRole('button', { name: 'Apply batch to draft', exact: true })).toHaveCount(0)
  const downloadEvent = page.waitForEvent('download')
  await preview.getByRole('link', { name: 'Download row diagnostics CSV' }).click()
  const download = await downloadEvent
  expect(download.suggestedFilename()).toMatch(/diagnostics.csv$/)
  expect(await download.failure()).toBeNull()
  await preview.getByRole('button', { name: 'Validate clean preview' }).click()
  await preview.getByRole('button', { name: 'Apply batch to draft', exact: true }).click()
  await preview.getByRole('button', { name: 'Confirm apply to draft' }).click()
  await expect(preview).toContainText('Batch applied to draft. Public release unchanged.')
  expect(await (await page.request.get(`/api/v1/campuses/${publicCampus.id}/release`)).json()).toEqual(before)
  expect((await (await page.request.get(`/api/v1/campuses/${publicCampus.id}/search?q=${code}`)).json()).total).toBe(0)
  await page.getByRole('button', { name: 'Draft catalog', exact: true }).click()
  await expect(page.getByText(`${code} · Synthetic imported browser place`, { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Data imports', exact: true }).click()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([])
  // The same stable identity previews as unchanged rather than adding another place.
  await upload(page, `${code}.json`, bundle(records), 'json')
  await expect(page.getByLabel('Import preview')).toContainText('Unchanged: 1')
})

test('CSV field mapping, invalid diagnostics, corrected policy and cancellation', async ({ page }) => {
  test.setTimeout(60000)
  await setup(page, 'editor')
  await page.getByRole('combobox', { name: 'Default entity', exact: true }).selectOption('departments')
  await page.getByRole('button', { name: 'Add field mapping', exact: true }).click()
  await page.getByLabel('Source column 1').fill('key')
  const code = `CSV_${test.info().project.name.startsWith('mobile') ? 'M' : 'D'}`
  await upload(page, 'mapped.csv', `key,code,name\na,${code},Synthetic CSV\nb,${code},Duplicate candidate\n`, 'csv')
  const preview = page.getByLabel('Import preview')
  await expect(preview).toContainText('Conflicts: 1')
  await expect(preview.getByRole('button', { name: 'Validate clean preview' })).toBeDisabled()
  await expect(preview).toContainText('Duplicate code/link')
  await preview.getByText('Adjust mapping or duplicate policy', { exact: true }).click()
  await preview.getByLabel('Duplicate policy', { exact: false }).selectOption('upsert')
  await preview.getByRole('button', { name: 'Reprocess with these settings' }).click()
  await expect(preview).toContainText('Job state: preview ready', { timeout: 30000 })
  await expect(preview).toContainText('Conflicts: 1') // same code/different identities still needs explicit adoption
  await preview.getByRole('button', { name: 'Cancel import', exact: true }).click()
  await expect(preview).toContainText('Job state: cancelled')
})

test('GeoJSON validation and stale preview rejected after another draft edit', async ({ page }) => {
  test.setTimeout(60000)
  await setup(page)
  const code = `GEO_${test.info().project.name.startsWith('mobile') ? 'M' : 'D'}`
  const feature = { type: 'FeatureCollection', features: [{ type: 'Feature', properties: { external_id: `browser-${code}`, code, name: 'Synthetic GeoJSON', kind: 'help' }, geometry: { type: 'Point', coordinates: [0.001, 0.001] } }] }
  await upload(page, `${code}.geojson`, JSON.stringify(feature), 'geojson')
  const preview = page.getByLabel('Import preview')
  await preview.getByRole('button', { name: 'Validate clean preview' }).click()
  await page.getByRole('button', { name: 'Draft catalog', exact: true }).click()
  await page.getByRole('button', { name: 'Add place', exact: true }).click()
  await page.getByLabel('Code', { exact: true }).fill(`${code}_EDIT`)
  await page.getByLabel('Name', { exact: true }).fill('Other draft edit')
  await page.getByLabel('Longitude', { exact: false }).fill('0.001')
  await page.getByLabel('Latitude', { exact: false }).fill('0.001')
  await page.getByRole('button', { name: 'Save draft record' }).click()
  await expect(page.getByRole('status')).toContainText('Draft saved')
  await page.getByRole('button', { name: 'Data imports', exact: true }).click()
  await page.getByRole('button', { name: `${code}.geojson · validated`, exact: true }).first().click()
  await page.getByLabel('Import preview').getByRole('button', { name: 'Apply batch to draft', exact: true }).click()
  await page.getByRole('button', { name: 'Confirm apply to draft' }).click()
  await expect(page.getByLabel('Import preview').getByRole('alert')).toContainText('draft changed')
  await page.getByRole('button', { name: 'Refresh preview after draft changes' }).click()
  await expect(page.getByLabel('Import preview')).toContainText('Job state: preview ready', { timeout: 30000 })
})
