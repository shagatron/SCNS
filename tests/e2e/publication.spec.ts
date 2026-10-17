import { expect, test, type Browser, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test.use({ trace: 'off', screenshot: 'off', video: 'off' })

async function login(page: Page, role: string, campus: string) {
  await page.goto('/admin')
  await page.getByLabel('Username', { exact: true }).fill(`browser-${role}`)
  await page.getByLabel('Password', { exact: true }).fill(process.env.SCNS_E2E_PASSWORD!)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Admin dashboard' })).toBeVisible()
  await page.getByRole('combobox', { name: 'Assigned campus' }).selectOption({ label: campus })
  await page.getByRole('button', { name: 'Review and releases', exact: true }).click()
}

async function warnings(page: Page) {
  await page.getByRole('textbox', { name: 'Reason after reviewing all displayed warnings', exact: true }).fill('Reviewed all synthetic coverage and unknown accessibility warnings; this is software test data only.')
  await page.getByRole('button', { name: /Acknowledge all \d+ warnings with this reason/ }).click()
}

async function extraPage(browser: Browser, testPage: Page) {
  const context = await browser.newContext({ viewport: testPage.viewportSize() ?? undefined })
  return { context, page: await context.newPage() }
}

test('independent review publishes coherent public data, stale client recovers and explicit rollback retains history', async ({ page, browser }) => {
  test.setTimeout(120000)
  const viewport = test.info().project.name.startsWith('mobile') ? 'mobile' : 'desktop'
  const campus = `Synthetic publication fixture ${viewport}`
  const reviewer = await extraPage(browser, page)
  const publicUser = await extraPage(browser, page)
  try {
    await login(page, 'owner', campus)
    const create = page.waitForResponse(r => r.url().endsWith('/drafts') && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Create draft from published release' }).click()
    const draft = await (await create).json()
    const base = `/api/v1/admin/campuses/${draft.campus_id}/drafts/${draft.id}`
    const originalRelease = await (await page.request.get(`/api/v1/campuses/${draft.campus_id}/release`)).json()
    // Make an observable catalog change through the existing UI, then return to review.
    await page.getByRole('button', { name: 'Draft catalog', exact: true }).click()
    await page.getByRole('button', { name: 'Places', exact: true }).click()
    await page.getByRole('button', { name: 'Edit LIB · Library', exact: true }).click()
    await page.getByLabel('Name', { exact: true }).fill(`Synthetic Reviewed Library ${viewport}`)
    await page.getByRole('button', { name: 'Save draft record' }).click()
    await expect(page.getByRole('status')).toContainText('Draft saved')
    await page.getByRole('button', { name: 'Review and releases', exact: true }).click()
    await page.getByRole('textbox', { name: 'Source title', exact: true }).fill('Synthetic reviewed vectors')
    await page.getByRole('textbox', { name: 'Source provenance', exact: true }).fill('Original invented synthetic fixture; private provenance never public.')
    await page.getByRole('textbox', { name: 'Public attribution', exact: true }).fill('Synthetic software demonstration only')
    await page.getByLabel('Optional private GeoJSON original', { exact: false }).setInputFiles({ name: 'synthetic.geojson', mimeType: 'application/geo+json', buffer: Buffer.from(JSON.stringify({ type: 'FeatureCollection', features: [
      { type: 'Feature', geometry: { type: 'Point', coordinates: [0.001, 0.001] }, properties: { label: 'Approved synthetic overlay', public: true, internal_note: 'NEVER-PUBLIC-ORIGINAL' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [0.005, 0.005] }, properties: { label: 'PRIVATE-GEOMETRY-LABEL', public: false } },
    ] })) })
    await page.getByRole('checkbox', { name: 'Propose a sanitized outdoor display overlay' }).check()
    await expect(page.getByText('synthetic.geojson', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Register source for independent review', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Synthetic reviewed vectors', exact: true })).toBeVisible()
    // Fresh anonymous planner remains on the earlier release throughout source/review work.
    await publicUser.page.goto('/')
    await publicUser.page.getByRole('combobox', { name: 'Explore campus' }).selectOption({ label: campus })
    await publicUser.page.getByRole('combobox', { name: 'Destination', exact: true }).selectOption({ label: 'Library' })
    await publicUser.page.getByRole('button', { name: 'Find walking route' }).click()
    await expect(publicUser.page.getByRole('status').filter({ hasText: 'Route ready' })).toBeVisible()
    await login(reviewer.page, 'reviewer_publisher', campus)
    await reviewer.page.getByText('Inspect exact public derivative', { exact: true }).click()
    await expect(reviewer.page.getByRole('article').locator('pre').filter({ hasText: 'Approved synthetic overlay' })).toBeVisible()
    await expect(reviewer.page.locator('pre').filter({ hasText: 'PRIVATE-GEOMETRY-LABEL' })).toHaveCount(0)
    reviewer.page.on('dialog', dialog => void dialog.accept())
    await reviewer.page.getByRole('button', { name: 'Approve source Synthetic reviewed vectors', exact: true }).click()
    await expect(reviewer.page.getByText('Rights: synthetic · Approved', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Refresh review packet', exact: true }).click()
    await page.getByRole('combobox', { name: 'Evidence start', exact: true }).selectOption({ label: 'Main Gate' })
    await page.getByRole('combobox', { name: 'Evidence destination', exact: true }).selectOption({ label: `Synthetic Reviewed Library ${viewport}` })
    await page.getByRole('textbox', { name: 'Route evidence reason', exact: true }).fill('Expected stored synthetic Main Gate/library route in both profiles; no field survey.')
    await page.getByRole('combobox', { name: 'Expected standard route', exact: true }).selectOption('false')
    await page.getByRole('button', { name: 'Run authoritative validation', exact: true }).click()
    await expect(page.getByText(/1 blocking errors · \d+ warnings/)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Submit exact validated version for review', exact: true })).toBeDisabled()
    await expect(page.getByRole('textbox', { name: 'Route evidence reason', exact: true })).toHaveValue('Expected stored synthetic Main Gate/library route in both profiles; no field survey.')
    await page.getByRole('combobox', { name: 'Expected standard route', exact: true }).selectOption('true')
    await page.getByRole('button', { name: 'Run authoritative validation', exact: true }).click()
    await expect(page.getByText(/0 blocking errors · \d+ warnings/)).toBeVisible()
    await expect(page.getByText('shortest: PASS', { exact: false })).toBeVisible()
    await warnings(page)
    await page.getByRole('button', { name: 'Submit exact validated version for review', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Review submission: submitted', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Approve exact reviewed content', exact: true })).toBeDisabled()
    await reviewer.page.getByRole('button', { name: 'Refresh review packet', exact: true }).click()
    await expect(reviewer.page.getByRole('heading', { name: 'Review submission: submitted', exact: true })).toBeVisible()
    await reviewer.page.getByRole('textbox', { name: 'Review decision notes', exact: true }).fill('Reject first submission: route coverage needs a fresh explicit expectation review.')
    await reviewer.page.getByRole('button', { name: 'Reject and return to draft', exact: true }).click()
    await expect(reviewer.page.getByRole('status').filter({ hasText: 'Revision state:' })).toContainText('draft')
    await page.getByRole('button', { name: 'Refresh review packet', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Submit exact validated version for review', exact: true })).toBeDisabled()
    await page.getByRole('button', { name: 'Run authoritative validation', exact: true }).click()
    await expect(page.getByText(/0 blocking errors · \d+ warnings/)).toBeVisible()
    await warnings(page)
    await page.getByRole('button', { name: 'Submit exact validated version for review', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Review submission: submitted', exact: true })).toBeVisible()
    await reviewer.page.getByRole('button', { name: 'Refresh review packet', exact: true }).click()
    await expect(reviewer.page.getByRole('heading', { name: 'Review submission: submitted', exact: true })).toBeVisible()
    await warnings(reviewer.page)
    await reviewer.page.getByRole('textbox', { name: 'Review decision notes', exact: true }).fill('Independent review of changes, rights, public projection, route evidence and material warnings.')
    await reviewer.page.getByRole('button', { name: 'Approve exact reviewed content', exact: true }).click()
    await expect(reviewer.page.getByRole('heading', { name: 'Review submission: approved', exact: true })).toBeVisible()
    const packet = await (await reviewer.page.request.get(base + '/review')).json()
    const releaseBefore = await (await reviewer.page.request.get(`/api/v1/campuses/${draft.campus_id}/release`)).json()
    expect(releaseBefore.id).toBe(originalRelease.id)
    const a11y = await new AxeBuilder({ page: reviewer.page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
    expect(a11y.violations).toEqual([])
    expect(await reviewer.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await reviewer.page.getByRole('button', { name: 'Prepare publication', exact: true }).click()
    await reviewer.page.getByRole('checkbox', { name: 'I reviewed the consequences and the exact approved content' }).check()
    const publishedResponse = reviewer.page.waitForResponse(r => r.url().endsWith('/publish') && r.request().method() === 'POST')
    await reviewer.page.getByRole('button', { name: 'Confirm publish immutable release', exact: true }).click()
    const published = await (await publishedResponse).json()
    expect(published.release_id).not.toBe(originalRelease.id)
    expect(packet.submissions[0].checksum).toBe(packet.checksum)
    await expect(reviewer.page.getByRole('link', { name: /Download approved public release/ })).toBeVisible()
    // An established stale planner request triggers current-release reload and clears old results.
    let failMetadataRefresh = true
    await publicUser.page.route(`**/api/v1/campuses/${draft.campus_id}/release`, route => failMetadataRefresh ? route.abort() : route.continue())
    await publicUser.page.getByRole('button', { name: 'Find walking route' }).click()
    await expect(publicUser.page.getByRole('status').filter({ hasText: 'The campus release changed' })).toBeVisible()
    await expect(publicUser.page.getByRole('status').filter({ hasText: 'Refreshing campus data; previous route results are hidden.' })).toBeVisible()
    await expect(publicUser.page.getByText('Cannot reach campus data. Check your connection and try again.', { exact: true })).toBeVisible()
    await expect(publicUser.page.getByRole('combobox', { name: 'Destination', exact: true })).toHaveCount(0)
    failMetadataRefresh = false
    if (viewport === 'mobile') {
      // Exercise actual periodic recovery after the forced stale fetch failed,
      // without clicking Retry; cached pre-publication data must stay hidden.
      await expect(publicUser.page.getByRole('combobox', { name: 'Destination', exact: true })).toBeVisible({ timeout: 35000 })
    } else {
      // Polling can win the Retry click while Playwright waits for stability.
      // In either case require coherent recovery, never just a vanished error.
      await publicUser.page.getByRole('alert').filter({ hasText: 'Cannot reach campus data.' }).getByRole('button', { name: 'Try again', exact: true }).click({ timeout: 5000 }).catch(async () => {
        await expect(publicUser.page.getByRole('combobox', { name: 'Destination', exact: true })).toBeVisible()
      })
    }
    await expect(publicUser.page.getByRole('combobox', { name: 'Destination', exact: true })).toHaveValue('')
    await expect(publicUser.page.getByRole('heading', { name: /Your walking route/ })).toHaveCount(0)
    await publicUser.page.getByRole('combobox', { name: 'Destination', exact: true }).selectOption({ label: `Synthetic Reviewed Library ${viewport}` })
    await publicUser.page.getByRole('button', { name: 'Find walking route' }).click()
    await expect(publicUser.page.getByText(`Arrive at Synthetic Reviewed Library ${viewport}.`, { exact: true })).toBeVisible()
    const live = await (await reviewer.page.request.get(`/api/v1/campuses/${draft.campus_id}/release`)).json()
    const artifact = await reviewer.page.request.get(live.artifact_url)
    expect(artifact.status()).toBe(200)
    expect(await artifact.text()).not.toContain('private provenance')
    expect(await artifact.text()).not.toContain('NEVER-PUBLIC-ORIGINAL')
    expect(await artifact.text()).not.toContain('PRIVATE-GEOMETRY-LABEL')
    expect(await artifact.text()).toContain('Approved synthetic overlay')
    await expect(publicUser.page.locator('.map-panel .leaflet-marker-pane img')).toHaveCount(0) // approved point vectors never depend on missing marker PNG files
    expect(await publicUser.page.locator('.map-panel path[stroke="#66726b"]').count()).toBeGreaterThan(0)
    await reviewer.page.getByRole('textbox', { name: 'Rollback reason', exact: true }).fill('Restore earlier synthetic release following isolated acceptance test.')
    await reviewer.page.getByRole('button', { name: 'Prepare rollback', exact: true }).click()
    await reviewer.page.getByRole('checkbox', { name: 'I understand public navigation will use the earlier release' }).check()
    await reviewer.page.getByRole('button', { name: 'Confirm rollback to earlier release', exact: true }).click()
    await expect(reviewer.page.getByRole('status').filter({ hasText: 'Rollback completed' })).toBeVisible()
    expect((await (await reviewer.page.request.get(`/api/v1/campuses/${draft.campus_id}/release`)).json()).id).toBe(originalRelease.id)
    await expect(reviewer.page.getByRole('link', { name: /Download approved public release/ })).toBeVisible()
  } finally { await reviewer.context.close(); await publicUser.context.close() }
})
