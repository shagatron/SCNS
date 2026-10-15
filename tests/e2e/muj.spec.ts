import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

test.use({ trace: 'off', screenshot: 'off', video: 'off', actionTimeout: 15000 })
test('real MUJ staged geography, draft route and unpublished isolation', async ({ page }) => {
  test.setTimeout(180000)
  const origin = 'http://127.0.0.1:5174'
  const password = process.env.SCNS_E2E_PASSWORD
  if (!password) throw new Error('Use isolated browser runner')
  const before = await (await page.request.get('/api/v1/campuses')).json()
  const demo = before.find((c: {code: string}) => c.code === 'DEMO')
  const login = await page.request.post('/api/v1/admin/login', { headers: { Origin: origin }, data: { username: 'browser-owner', password } })
  expect(login.status()).toBe(200)
  const session = await login.json()
  const headers = { Origin: origin, 'X-CSRF-Token': session.csrf_token }
  const setup = await page.request.post(`/api/v1/admin/campuses/${demo.id}/muj-setup`, { headers })
  expect(setup.status(), await setup.text()).toBe(201)
  const { campus_id: campus } = await setup.json()
  // Each viewport owns an independent additional empty draft; never races another preview.
  const created = await page.request.post(`/api/v1/admin/campuses/${campus}/drafts`, { headers })
  expect(created.status()).toBe(201)
  const draft = await created.json()
  const path = `/api/v1/admin/campuses/${campus}/drafts/${draft.id}`
  const root = resolve(process.cwd(), '../data/muj')
  const options = readFileSync(resolve(root, 'options.json')).toString('base64')
  for (const filename of ['batch-001.json', 'batch-002.json', 'batch-003.json']) {
    const uploaded = await page.request.post(`${path}/imports?filename=${filename}`, { headers: { ...headers, 'Content-Type': 'application/octet-stream', 'X-Import-Options': options, 'Idempotency-Key': `${draft.id}-${filename}` }, data: readFileSync(resolve(root, filename)) })
    expect(uploaded.status(), await uploaded.text()).toBe(201)
    const job = await uploaded.json(), jobPath = `/api/v1/admin/campuses/${campus}/imports/${job.id}`
    await expect.poll(async () => (await (await page.request.get(jobPath)).json()).state, { timeout: 60000 }).toBe('preview_ready')
    const preview = await (await page.request.get(jobPath)).json()
    expect(preview.counts.invalid).toBe(0); expect(preview.counts.conflict).toBe(0)
    expect((await page.request.post(`${jobPath}/validate`, { headers })).status()).toBe(200)
    expect((await page.request.post(`${jobPath}/apply`, { headers: { ...headers, 'If-Match': `"${preview.preview_version}"` } })).status()).toBe(200)
  }
  // Normal UI sign in obtains the new campus grant; no private screenshot/trace or password logging.
  await page.goto('/admin')
  await page.getByRole('button', {name:'Sign out',exact:true}).click()
  await expect(page.getByRole('heading',{name:'Admin sign in'})).toBeVisible()
  await page.getByLabel('Username',{exact:true}).fill('browser-owner')
  await page.getByLabel('Password',{exact:true}).fill(password)
  await page.getByRole('button',{name:'Sign in',exact:true}).click()
  await page.getByRole('combobox',{name:'Assigned campus',exact:true}).selectOption(campus)
  await page.getByRole('combobox',{name:'Selected draft',exact:true}).selectOption(draft.id)
  await page.getByRole('button',{name:'Outdoor graph',exact:true}).click()
  await expect(page.getByLabel('Visual outdoor draft graph')).toBeVisible()
  const graph = await (await page.request.get(`${path}/graph`)).json()
  const positions = Object.values(graph.nodes).map((n: unknown) => (n as {point:{coordinates:number[]}}).point.coordinates)
  expect(positions.length).toBe(283)
  expect(positions.every(p => p[0] > 75.55 && p[0] < 75.57 && p[1] > 26.83 && p[1] < 26.85)).toBe(true)
  const svg = page.locator('.graph-map .leaflet-overlay-pane svg path')
  expect(await svg.count()).toBeGreaterThan(300)
  await page.getByRole('combobox',{name:'Draft route start',exact:true}).selectOption({label:'Hostel Entrance'})
  await page.getByRole('combobox',{name:'Draft route destination',exact:true}).selectOption({label:'GHS Entrance'})
  const routeResponse = page.waitForResponse(r=>r.url().includes('/graph/route-test?'))
  await page.getByRole('button',{name:'Compute draft test route'}).click()
  const route = await (await routeResponse).json()
  expect(route.found).toBe(true); expect(route.distance_m).toBeGreaterThan(0)
  await expect(page.getByLabel('Graph quality')).toContainText(`${route.distance_m.toFixed(2)}m`)
  await page.getByRole('button',{name:'Validate saved graph'}).click()
  await expect(page.getByLabel('Graph quality')).toContainText('0 errors')
  await page.getByLabel('Visual outdoor draft graph').screenshot({path:`test-results/muj-${test.info().project.name}-geometry.png`})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
  expect(await (await page.request.get('/api/v1/campuses')).json()).toEqual(before)
  expect((await page.request.get(`/api/v1/campuses/${campus}/release`)).status()).toBe(404)
})
