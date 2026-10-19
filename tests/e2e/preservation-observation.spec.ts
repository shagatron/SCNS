import { expect, test } from '@playwright/test'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

// This identical observational journey runs against archived a30810d, original
// redesign 6baeaad, and corrected code. It records differences instead of assuming
// that assertions changed with the redesign establish feature parity.
test('matched baseline preservation observation', async ({ page }, info) => {
  test.setTimeout(90000)
  const variant = process.env.SCNS_PARITY_VARIANT ?? 'corrected'
  const dir = resolve(process.env.SCNS_PARITY_OUTPUT ?? 'test-results/preservation', variant, info.project.name)
  mkdirSync(dir, { recursive: true })
  await page.setViewportSize({ width: info.project.name.startsWith('mobile') ? 390 : 1440, height: 960 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  await expect(page.getByLabel('Destination', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Find walking route' })).toBeEnabled()
  await expect(page.getByRole('button',{name:'Fit campus',exact:true})).toBeVisible()
  const observations: Record<string, unknown> = {}
  const save = () => writeFileSync(`${dir}/observations.json`, JSON.stringify(observations,null,2)+'\n')
  observations.structure = await page.evaluate(() => ({
    sections: [...document.querySelectorAll('main > section')].map(e => e.id),
    directory: document.querySelector('#directory')?.textContent,
    searchParent: document.querySelector('#search')?.closest('section[id]')?.id,
    directoryCards: document.querySelectorAll('#directory article.place-card').length,
    plannerParent: document.querySelector('#planner')?.parentElement?.className,
    source: document.querySelector<HTMLSelectElement>('#source')?.selectedOptions[0]?.text,
    profile: document.querySelector<HTMLSelectElement>('#profile')?.value,
    policy: document.querySelector<HTMLSelectElement>('#cost-mode')?.value,
    controlsOpen: document.querySelector<HTMLDetailsElement>('.route-controls')?.open,
    mapFocusOrder: [...document.querySelectorAll('.map-panel *')].filter(e => e instanceof HTMLElement && e.tabIndex >= 0).map(e => ({tag:e.tagName,role:e.getAttribute('role'),label:e.getAttribute('aria-label') ?? (e.tagName === 'DIV' ? 'Map' : e.textContent)})),
    navigation: [...document.querySelectorAll('nav[aria-label="Main navigation"] a')].map(a => [a.textContent, a.getAttribute('href')]),
  }))
  save()
  for (const id of ['intro', 'directory']) await page.locator(`#${id}`).screenshot({ path: `${dir}/${id}.png`, style: '.public-navigation, .skip-link { visibility:hidden !important; }' })
  await page.getByRole('link', { name: 'Places', exact: true }).click()
  observations.placesNavigation = await page.evaluate(() => ({ hash: location.hash, focus: document.activeElement?.id, directoryTop: document.querySelector('#directory')?.getBoundingClientRect().top, searchTop: document.querySelector('#search')?.getBoundingClientRect().top }))
  await page.getByLabel('Search destinations').fill('books')
  await expect(page.getByRole('button', { name: 'Route to Library', exact: true })).toBeVisible()
  observations.search = await page.evaluate(() => ({ directory: document.querySelector('#directory')?.textContent, focused: document.activeElement?.id, headings: [...document.querySelectorAll('article.place-card h3')].map(el => el.textContent) }))
  save()
  await page.getByRole('button', { name: 'Start at Library', exact: true }).click()
  await expect(page.getByLabel('Starting point', { exact: true })).toBeFocused()
  observations.startAction = await page.getByLabel('Starting point', { exact: true }).inputValue()
  observations.routeActionStillVisibleAfterStart = await page.getByRole('button', { name: 'Route to Library', exact: true }).isVisible()
  save()
  await page.getByLabel('Starting point', { exact: true }).selectOption({ label: 'Main Gate' })
  if (!observations.routeActionStillVisibleAfterStart) await page.getByRole('button', { name:'Browse places', exact:true }).click()
  await page.getByRole('button', { name: 'Route to Library', exact: true }).click()
  await expect(page.getByLabel('Destination', { exact: true })).toBeFocused()
  await page.getByRole('button', { name: 'Find walking route' }).click()
  await expect(page.getByText('Arrive at Library.', { exact: true })).toBeVisible()
  observations.route = await page.evaluate(() => ({ metrics: document.querySelector('.route-metrics')?.textContent, directions: document.querySelector('.directions')?.textContent, resultParent: document.querySelector('.route-results')?.parentElement?.id }))
  await page.locator('#planner').screenshot({ path:`${dir}/planner.png`,style:'.public-navigation, .skip-link { visibility:hidden !important; }' })
  await page.locator('#explorer').screenshot({ path: `${dir}/route.png`, style: '.public-navigation, .skip-link { visibility:hidden !important; }' })
  await page.getByRole('button', { name: 'Hide map', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Route directions' })).toBeVisible()
  observations.hiddenMap = await page.getByRole('region', { name: 'Route directions' }).innerText()
  await page.getByRole('button', { name: 'Show map', exact: true }).click()
  await page.getByLabel('Destination', { exact: true }).selectOption({ label: 'Quiet Garden' })
  await page.getByRole('button', { name: 'Find walking route' }).click()
  await expect(page.getByText('Route unavailable', { exact: true })).toBeVisible()
  observations.noRoute = await page.evaluate(() => ({ message: [...document.querySelectorAll('[role="alert"]')].map(e => e.textContent), errorParent: [...document.querySelectorAll('[role="alert"]')].find(e => e.textContent?.includes('Route unavailable'))?.closest('section[id]')?.id }))
  await page.locator('#explorer').screenshot({ path: `${dir}/no-route.png`, style: '.public-navigation, .skip-link { visibility:hidden !important; }' })
  await page.route('**/api/v1/campuses/*/search?*', route => {
    const p = new URL(route.request().url()).searchParams
    return p.get('q') === 'parity-error' ? route.fulfill({ status:503, json:{error:{code:'service_unavailable',message:'Synthetic directory lookup failed.'}} }) : route.continue()
  })
  await page.getByLabel('Search destinations').fill('parity-error')
  await expect(page.getByText('Synthetic directory lookup failed.', { exact: true })).toBeVisible()
  observations.searchError = await page.evaluate(() => ({ parent: [...document.querySelectorAll('[role="alert"]')].find(e => e.textContent?.includes('Synthetic directory lookup failed.'))?.closest('section[id]')?.id, focused:document.activeElement?.id }))
  await page.locator('#directory').screenshot({ path:`${dir}/search-error.png`,style:'.public-navigation, .skip-link { visibility:hidden !important; }' })
  save()
  if (variant === 'corrected') {
    // Actual runtime contract captured from archived baseline, not rewritten to
    // match the redesign. Only the explicitly requested error placement differs.
    const baseline = JSON.parse(readFileSync(resolve('../tests/fixtures/public-baseline-a30810d.json'), 'utf8')).projects[info.project.name]
    for (const key of ['structure','placesNavigation','search','startAction','routeActionStillVisibleAfterStart','route','hiddenMap','searchError']) {
      expect(observations[key], key).toEqual(baseline[key])
    }
    expect((observations.noRoute as {message:unknown}).message).toEqual(baseline.noRoute.message)
    expect((observations.noRoute as {errorParent:string}).errorParent).toBe('planner')
  }
})
