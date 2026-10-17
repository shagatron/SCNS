import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createHash } from 'node:crypto'

// Read-only RESPONSE SIMULATION from committed source-derived preparation.
// Not a cloud publication, Windows inspection, route certification or real release.
test('source-derived MUJ footprints/path context and unresolved names in a simulated public response', async ({ page }, info) => {
  const root = resolve(process.cwd(), '../data/muj')
  const source = JSON.parse(readFileSync(resolve(root, 'campus.json'), 'utf8'))
  const records = ['batch-001.json','batch-002.json','batch-003.json'].flatMap(file => JSON.parse(readFileSync(resolve(root,file),'utf8')).records) as {entity:string;external_id:string;data:Record<string,unknown>}[]
  const uuid = (s:string) => { const h=createHash('sha256').update(s).digest('hex');return `${h.slice(0,8)}-${h.slice(8,12)}-4${h.slice(13,16)}-a${h.slice(17,20)}-${h.slice(20,32)}` }
  const features = records.filter(r=>['buildings','edges'].includes(r.entity)).map(r=>({type:'Feature',id:uuid(r.external_id),geometry:r.data.footprint ?? r.data.geometry,properties:r.entity==='buildings'?{layer:'building',name:r.data.name}:{layer:'path',open:r.data.is_open,kind:r.data.kind}}))
  features.push({type:'Feature',id:uuid('source-context'),geometry:source.boundary,properties:{layer:'overlay',name:'Source extent',attribution:'© OpenStreetMap contributors · ODbL. Source visual fixture; simulated release, not Windows data.'}} as typeof features[number])
  const places: Record<string,unknown>[] = records.filter(r=>r.entity==='places').map(r=>({...r.data,id:uuid(r.external_id),aliases:[],routable:records.some(a=>a.entity==='anchors' && a.data.place_id===r.external_id)}))
  await page.route('**/api/v1/campuses',async route=>{
    const response=await route.fetch(), campuses=await response.json()
    await route.fulfill({response,json:[{...campuses[0],...source,name:`Source visual fixture (simulated release) · ${source.name}`}]})
  })
  await page.route('**/api/v1/campuses/*/map?*',async route=>{
    const response=await route.fetch(), actual=await response.json()
    await route.fulfill({response,json:{...actual,features,truncated:false}})
  })
  await page.route('**/api/v1/campuses/*/search?*',async route=>{
    const response=await route.fetch(), actual=await response.json(), params=new URL(route.request().url()).searchParams
    const q=(params.get('q')??'').toLowerCase(), kind=params.get('kind'), offset=Number(params.get('offset')??0), limit=Number(params.get('limit')??6)
    const matches=places.filter(p=>(!kind || p.kind===kind) && String(p.name).toLowerCase().includes(q))
    await route.fulfill({response,json:{...actual,items:matches.slice(offset,offset+limit),total:matches.length,offset,limit}})
  })
  await page.goto('/#explorer')
  await expect(page.locator('.outdoor-panel')).toContainText('OpenStreetMap contributors')
  await expect(page.locator('.leaflet-overlay-pane path[fill="#4b5751"]')).toHaveCount(records.filter(r=>r.entity==='buildings').length)
  await page.getByLabel('Category',{exact:true}).selectOption('entrance')
  const unresolved=records.find(r=>r.entity==='places' && r.external_id==='osm-node-10828149259')!
  await page.getByLabel('Search destinations').fill(String(unresolved.data.name))
  await expect(page.locator('#directory').getByRole('heading',{name:String(unresolved.data.name),exact:true})).toBeVisible()
  await page.getByRole('button',{name:`Map destination: ${unresolved.data.name}`,exact:true}).click()
  await expect(page.getByLabel('Destination',{exact:true})).toHaveValue(uuid(unresolved.external_id))
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  // Capture the complete map/context/attribution rather than just the tall mobile controls.
  await page.locator('.outdoor-panel').screenshot({path:`test-results/map-explorer/${info.project.name}-source-context.png`,style:'.public-navigation, .skip-link { visibility:hidden !important; }'})
})
