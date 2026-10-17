import { expect, test, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Branding-response simulation over actual isolated synthetic published releases.
// No actual MUJ/Windows release, source approval, physical campus or GPS claim.
const longName = 'Manipal University Jaipur — Limited OpenStreetMap academic preview; unresolved entrances and unverified accessibility'
async function brand(page: Page) {
  let mujId = '', demoId = ''
  await page.route('**/api/v1/campuses', async route => {
    const response = await route.fetch(), all = await response.json()
    const demo = all.find((c: {code:string}) => c.code === 'DEMO') ?? all[0]
    const other = all.find((c: {id:string}) => c.id !== demo.id)
    if (!other) throw new Error('Existing isolated second release fixture required')
    mujId = other.id; demoId = demo.id
    await route.fulfill({ response, json: [demo, { ...other, code: 'MUJ', is_demo: false, name: longName }] })
  })
  await page.goto('/')
  await expect(page.getByLabel('Explore campus', {exact:true})).toBeEnabled()
  return { mujId, demoId }
}
function output(project: string) {
  const dir = resolve(process.env.SCNS_HOMEPAGE_OUTPUT ?? 'test-results/muj-homepage', project)
  mkdirSync(dir, {recursive:true}); return dir
}
async function settled(page:Page) {
  await page.evaluate(() => document.fonts.ready)
  await expect(page.getByRole('button',{name:'Find walking route',exact:true})).toBeEnabled()
}
async function captureWorkflows(page:Page, dir:string, prefix:string) {
  await settled(page)
  for (const id of ['intro','directory']) await page.locator(`#${id}`).screenshot({path:`${dir}/${prefix}-${id}.png`,style:'.public-navigation,.skip-link{visibility:hidden!important}'})
  const structure = await page.evaluate(() => ({
    sections:[...document.querySelectorAll('main > section')].map(e=>e.id),
    navigation:[...document.querySelectorAll('nav[aria-label="Main navigation"] a')].map(e=>[e.textContent,e.getAttribute('href')]),
    directory:document.querySelector('#directory')?.textContent,
    source:document.querySelector<HTMLSelectElement>('#source')?.value,
    preference:document.querySelector<HTMLSelectElement>('#profile')?.value,
    policy:document.querySelector<HTMLSelectElement>('#cost-mode')?.value,
  }))
  await page.getByLabel('Search destinations').fill('books')
  await page.getByRole('button',{name:'Start at Library',exact:true}).click()
  await expect(page.getByLabel('Starting point',{exact:true})).toBeFocused()
  await page.getByLabel('Starting point',{exact:true}).selectOption({label:'Main Gate'})
  await page.getByRole('button',{name:'Route to Library',exact:true}).click()
  await expect(page.getByLabel('Destination',{exact:true})).toBeFocused()
  await page.getByRole('button',{name:'Find walking route',exact:true}).click()
  await expect(page.getByText('Arrive at Library.',{exact:true})).toBeVisible()
  await page.locator('#planner').screenshot({path:`${dir}/${prefix}-planner.png`,style:'.public-navigation,.skip-link{visibility:hidden!important}'})
  const result = { metrics:await page.locator('.route-metrics').innerText(), directions:await page.locator('.directions').innerText() }
  await page.getByRole('button',{name:'Hide map',exact:true}).click()
  await expect(page.getByRole('region',{name:'Route directions'})).toBeVisible()
  await page.getByRole('button',{name:'Show map',exact:true}).click()
  await page.getByLabel('Destination',{exact:true}).selectOption({label:'Quiet Garden'})
  await page.getByRole('button',{name:'Find walking route',exact:true}).click()
  await expect(page.getByText('Route unavailable',{exact:true})).toBeVisible()
  await page.locator('#explorer').screenshot({path:`${dir}/${prefix}-no-route.png`,style:'.public-navigation,.skip-link{visibility:hidden!important}'})
  const error = await page.locator('#planner [role="alert"]').innerText()
  await page.route('**/api/v1/campuses/*/search?*', route => new URL(route.request().url()).searchParams.get('q')==='homepage-error' ? route.fulfill({status:503,json:{error:{code:'service_unavailable',message:'Synthetic directory lookup failed.'}}}) : route.continue())
  await page.getByLabel('Search destinations').fill('homepage-error')
  await expect(page.getByText('Synthetic directory lookup failed.',{exact:true})).toBeVisible()
  await page.locator('#directory').screenshot({path:`${dir}/${prefix}-search-error.png`,style:'.public-navigation,.skip-link{visibility:hidden!important}'})
  return {structure,result,error}
}

test('MUJ-only original assets, five-width crop, controls, contrast and matching parent workflows',async({page,browser},info)=>{
  test.setTimeout(150000)
  const dir=output(info.project.name)
  await page.emulateMedia({reducedMotion:'reduce'})
  const {mujId,demoId}=await brand(page)
  await expect(page.locator('.muj-hero-photo')).toHaveCount(0)
  const assetRequests:string[]=[]
  page.on('request',r=>{if(r.url().includes('/branding/muj/'))assetRequests.push(r.url())})
  // Demo never requests university assets; campus change is the original selector.
  await page.reload();await settled(page);expect(assetRequests).toEqual([])
  await page.getByLabel('Explore campus',{exact:true}).selectOption(mujId)
  await expect(page.getByAltText('Manipal University Jaipur emblem')).toBeVisible()
  const observations=[]
  for(const width of [320,360,390,768,1440]){
    await page.setViewportSize({width,height:960})
    await page.locator('#intro').scrollIntoViewIfNeeded()
    await settled(page)
    await expect.poll(()=>page.locator('.muj-hero-photo img').evaluate((im:HTMLImageElement)=>im.complete&&im.naturalWidth>0)).toBeTruthy()
    await expect.poll(()=>page.getByAltText('Manipal University Jaipur emblem').evaluate((im:HTMLImageElement)=>im.complete&&im.naturalWidth===250)).toBeTruthy()
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
    const crop=await page.locator('.muj-hero-photo img').evaluate((im:HTMLImageElement)=>{
      const b=im.getBoundingClientRect(),scale=Math.max(b.width/im.naturalWidth,b.height/im.naturalHeight)
      const mobile=im.naturalWidth===296, x0=mobile?80:300,x1=mobile?220:440
      const left=b.x+(b.width-im.naturalWidth*scale)/2
      return {width:b.width,domeLeft:left+x0*scale-b.x,domeRight:left+x1*scale-b.x,finialY:52*scale,height:b.height,current:im.currentSrc}
    })
    expect(crop.domeLeft).toBeGreaterThanOrEqual(0);expect(crop.domeRight).toBeLessThanOrEqual(crop.width)
    expect(crop.finialY).toBeGreaterThan(0);expect(crop.finialY).toBeLessThan(crop.height)
    expect(crop.current).toContain(width<=760?'campus-mobile.webp':'campus-736.webp')
    const logo=await page.getByAltText('Manipal University Jaipur emblem').boundingBox()
    expect(logo!.width/logo!.height).toBeCloseTo(250/289,2)
    expect(await page.locator('.opening-note').evaluate(el=>getComputedStyle(el).color)).toBe('rgb(17, 17, 16)')
    expect(await page.locator('html').evaluate(el=>getComputedStyle(el).scrollBehavior)).toBe('auto')
    const axe=await new AxeBuilder({page}).include('#intro').withTags(['wcag2a','wcag2aa']).analyze()
    expect(axe.violations).toEqual([])
    await page.locator('#intro').screenshot({path:`${dir}/muj-${width}.png`,style:'.public-navigation,.skip-link{visibility:hidden!important}'})
    observations.push({width,crop,logo})
  }
  await page.setViewportSize({width:info.project.name.startsWith('mobile')?390:1440,height:960})
  await page.goto(`/?campus=${mujId}`);const after=await captureWorkflows(page,dir,'muj-after')
  if(process.env.SCNS_HOMEPAGE_BASELINE_URL){
    const context=await browser.newContext({viewport:page.viewportSize()!,deviceScaleFactor:info.project.name.startsWith('mobile')?2.75:1,reducedMotion:'reduce'})
    try {
      const old=await context.newPage();const base=process.env.SCNS_HOMEPAGE_BASELINE_URL
      await old.route('**/api/v1/campuses',async route=>{const r=await route.fetch(),all=await r.json();await route.fulfill({response:r,json:[all.find((c:{id:string})=>c.id===demoId),{...all.find((c:{id:string})=>c.id===mujId),code:'MUJ',is_demo:false,name:longName}]})})
      await old.goto(`${base}/?campus=${mujId}`)
      await expect(old.locator('.muj-hero-photo')).toHaveCount(0)
      const before=await captureWorkflows(old,dir,'muj-before');expect(after).toEqual(before)
      writeFileSync(`${dir}/matched-muj.json`,JSON.stringify({before,after,qualification:'Matched parent/current software fixture with simulated MUJ branding metadata; not Windows or real MUJ release.'},null,2))
    } finally {await context.close()}
  }
  writeFileSync(`${dir}/branding.json`,JSON.stringify(observations,null,2))
  await page.getByLabel('Explore campus',{exact:true}).selectOption(demoId)
  await expect(page.getByText('Synthetic demo.',{exact:true})).toBeVisible()
  await expect(page.locator('.muj-hero-photo')).toHaveCount(0)
})

test('asset failures and delayed loading retain focus, layout and all hero controls at reduced mobile height',async({page},info)=>{
  const dir=output(info.project.name)
  await page.emulateMedia({reducedMotion:'reduce'})
  const {mujId}=await brand(page)
  await page.setViewportSize({width:360,height:500}) // viewport pressure, not a physical keyboard
  let release:()=>void=()=>{}
  const delay=new Promise<void>(resolve=>{release=resolve})
  await page.route('**/branding/muj/**',async route=>{await delay;await route.abort()})
  await page.getByLabel('Explore campus',{exact:true}).selectOption(mujId)
  const action=page.getByRole('link',{name:'Explore campus',exact:true})
  await action.focus()
  await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))))
  const before=await page.locator('#intro').boundingBox()
  release()
  await expect(page.locator('.muj-hero-photo')).toHaveAttribute('data-photo-status','unavailable')
  await expect(page.getByText('University emblem unavailable')).toBeVisible()
  expect(await page.locator('#intro').boundingBox()).toEqual(before)
  await expect(action).toBeFocused()
  await expect(page.getByLabel('Explore campus',{exact:true})).toBeEnabled()
  await expect(page.getByRole('button',{name:'Find walking route',exact:true})).toBeEnabled()
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
  await page.locator('#intro').screenshot({path:`${dir}/asset-failure-360.png`,style:'.public-navigation,.skip-link{visibility:hidden!important}'})
  await page.goto('/admin')
  await expect(page.getByRole('heading',{name:'Admin sign in'})).toBeVisible()
  await expect(page.locator('.public-app')).toHaveCount(0)
  await page.screenshot({path:`${dir}/admin-login.png`})
})
