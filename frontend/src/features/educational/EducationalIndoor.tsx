import { lazy, Suspense, useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { components } from '../../api/generated'
import MapFailureBoundary from '../maps/MapFailureBoundary'
import './educational.css'

const FloorRouteMap = lazy(() => import('../maps/FloorRouteMap'))
type Demo = components['schemas']['DemoData']
type DemoRoute = components['schemas']['DemoRoute']
const qualification = 'Demonstration layout — not an actual MUJ floorplan.'
const endpoint = '/educational/indoor-school'
function initial() { return new URLSearchParams(window.location.search) }

export default function EducationalIndoor({ embedded = false }: { embedded?: boolean }) {
  const key = (name: string) => embedded ? `demo_${name}` : name
  const Body = embedded ? 'div' : 'main'
  const Title = embedded ? 'h3' : 'h1'
  const [source, setSource] = useState(() => initial().get(key('from')) ?? '')
  const [destination, setDestination] = useState(() => initial().get(key('to')) ?? '')
  const [floorId, setFloorId] = useState(() => initial().get(key('floor')) ?? '')
  const [showMap, setShowMap] = useState(true)
  const [request, setRequest] = useState<{source: string; destination: string} | null>(() => initial().get(key('route')) === '1' ? {source: initial().get(key('from')) ?? '', destination: initial().get(key('to')) ?? ''} : null)
  const layout = useQuery({queryKey: ['educational-indoor'], queryFn: ({signal}) => api<Demo>(endpoint, {signal}), retry: false})
  const data = layout.data
  const from = data?.rooms.find(r => r.id === source) ?? data?.rooms[0]
  const to = data?.rooms.find(r => r.id === destination) ?? data?.rooms[1] ?? data?.rooms[0]
  const floor = data?.floors.find(f => f.id === floorId) ?? data?.floors[0]
  const validRequest = !!data?.rooms.some(r => r.id === request?.source) && !!data?.rooms.some(r => r.id === request?.destination)
  const route = useQuery({
    queryKey: ['educational-indoor-route', data?.version, request], enabled: !!data && !!request && validRequest,
    queryFn: ({signal}) => api<DemoRoute>(endpoint + '/routes', {method: 'POST', signal, headers: {'Content-Type': 'application/json'}, body: JSON.stringify({source_id: request!.source, destination_id: request!.destination, expected_version: data!.version})}),
    retry: false, staleTime: Infinity,
  })
  const ready = !!request && validRequest && route.isSuccess
  const savedCampus = initial().get('returnCampus')
  const back = savedCampus && /^[a-f0-9-]{36}$/i.test(savedCampus) ? `/?campus=${encodeURIComponent(savedCampus)}#intro` : '/'
  function remember(start: string, end: string, floor: string, routed: boolean) {
    const params = initial()
    params.set(key('from'), start); params.set(key('to'), end); params.set(key('floor'), floor)
    if (routed) params.set(key('route'), '1'); else params.delete(key('route'))
    const url = new URL(window.location.href)
    url.search = params.toString()
    window.history.replaceState(null, '', url)
  }
  function selectFloor(id: string) { setFloorId(id); if (from && to) remember(from.id, to.id, id, !!request) }
  function changeRoom(value: string, start: boolean) {
    if (start) setSource(value); else setDestination(value)
    setRequest(null)
    remember(start ? value : from!.id, start ? to!.id : value, floor!.id, false)
  }
  function calculate(event: FormEvent) {
    event.preventDefault()
    if (!data || !from || !to) return
    setFloorId(from.floor_id)
    remember(from.id, to.id, from.floor_id, true)
    if (request?.source === from.id && request.destination === to.id) void route.refetch()
    else setRequest({source: from.id, destination: to.id})
  }
  return <div className={embedded ? "indoor-demo integrated-demo" : "public-app indoor-demo"}>
    {!embedded && <a className="skip-link" href="#demo-planner">Skip to demonstration planner</a>}
    {!embedded && <header className="demo-header"><a href={back}>← Return to campus explorer</a><span>SCNS / EDUCATIONAL PREVIEW</span></header>}
    <Body className="demo-body">
      <section className="demo-intro" aria-labelledby="demo-heading"><p className="section-index">A SEPARATE, FICTIONAL BUILDING</p><Title id="demo-heading">Indoor navigation demo</Title><p className="demo-qualification"><strong>{qualification}</strong></p><p>Explore an original two-floor learning building. Generic rooms, an authored corridor graph and Demo Stairs show how indoor directions work. Nothing here changes MUJ’s published campus map.</p><p>Directions only · fewest eligible traversals. No measured distance, scale or ETA. Accessibility is unknown; no verified step-free route is offered.</p></section>
      {layout.isPending && <p role="status">Loading demonstration rooms and floors…</p>}
      {layout.isError && <section role="alert" className="error-box"><h2>Demonstration unavailable</h2><p>{layout.error.message}</p><button onClick={() => void layout.refetch()}>Retry demonstration</button></section>}
      {data && (!data.rooms.length || !data.floors.length) && <section className="empty-state"><h2>No demonstration rooms available</h2><p>The campus explorer remains available. Reload the demonstration to try again.</p><button onClick={() => void layout.refetch()}>Reload demonstration</button></section>}
      {data && from && to && floor && <>
        <section id="demo-planner" tabIndex={-1} className="demo-planner" aria-labelledby="demo-planner-title"><h2 id="demo-planner-title">Choose your demo journey</h2>
          <form onSubmit={calculate}><fieldset disabled={!!request && route.isFetching}><legend>Demonstration rooms</legend><div className="demo-selects"><div><label htmlFor="demo-source">Start room</label><select id="demo-source" value={from.id} onChange={e => changeRoom(e.target.value, true)}>{data.rooms.map(r => <option key={r.id} value={r.id}>{r.name} · {data.floors.find(f => f.id === r.floor_id)?.label}</option>)}</select></div><div><label htmlFor="demo-destination">Destination room</label><select id="demo-destination" value={to.id} onChange={e => changeRoom(e.target.value, false)}>{data.rooms.map(r => <option key={r.id} value={r.id}>{r.name} · {data.floors.find(f => f.id === r.floor_id)?.label}</option>)}</select></div></div><button className="demo-calculate" type="submit">{request && route.isFetching ? 'Calculating demo route…' : 'Find demo directions'}</button></fieldset></form>
          {!request && <p role="status">Choose rooms, then calculate. Try Demo Classroom A → Demo Library first.</p>}
          {request && !validRequest && <p role="alert">Saved demonstration rooms are unavailable. Choose rooms and calculate again.</p>}
          {request && validRequest && route.isFetching && <p role="status">Computing a route over the authored graph…</p>}
          {request && validRequest && route.isError && <div role="alert" className="error-box"><h3>Demo route unavailable</h3><p>{route.error.message}</p><p>Your selections are retained. Correct them above or retry.</p><button onClick={() => void route.refetch()}>Retry demo route</button></div>}
        </section>
        <section className="demo-viewer" aria-labelledby="demo-viewer-title"><h2 id="demo-viewer-title">Explore the two floors</h2><p className="demo-qualification">{qualification}</p><div className="demo-floor-controls"><div className="demo-floor-field"><label htmlFor="demo-floor">View demonstration floor</label><select id="demo-floor" value={floor.id} onChange={e => selectFloor(e.target.value)}>{data.floors.map(f => <option key={f.id} value={f.id}>{f.label}</option>)}</select></div><button onClick={() => setShowMap(v => !v)}>{showMap ? 'Hide demonstration map' : 'Show demonstration map'}</button></div><p>Zoom with + / −; drag to pan. Keyboard: focus the map, use arrow keys to pan and + / − to zoom. “Fit floor plan” restores the whole floor.</p>
          {showMap && <MapFailureBoundary message="Text directions remain usable. Reloading requests this educational viewer again; the campus explorer is unchanged."><Suspense fallback={<p role="status">Loading demonstration viewer…</p>}><FloorRouteMap key={floor.id} educational floor={floor} places={data.rooms} route={ready ? route.data : undefined} /></Suspense></MapFailureBoundary>}
          {ready && !route.data.segments.some(s => s.floor_id === floor.id || s.to_floor_id === floor.id) && <p role="status">No route section on this floor. Choose a floor shown in the directions.</p>}
        </section>
        {ready && <section className="demo-directions" aria-label="Demonstration directions"><p className="section-index">COMPUTED WITH DIJKSTRA</p><h2>Computed demonstration route</h2><p><strong>{from.name} → {to.name}</strong></p><p>{route.data.traversal_count} authored traversals · Directions only. The objective is fewest eligible traversals, not shortest distance or fastest travel.</p><p><strong>Distance unknown · ETA unavailable</strong></p>{!route.data.segments.length && <p>Start and destination are the same demo room. No traversal is needed; no measured distance is asserted.</p>}
          <ol>{route.data.segments.map(s => <li key={s.edge_id}><p>{s.instruction}</p><div>{[...new Set([s.floor_id, s.to_floor_id])].filter(Boolean).map(id => <button key={id} onClick={() => selectFloor(id!)}>Show {data.floors.find(f => f.id === id)?.label}</button>)}</div></li>)}<li><p>{route.data.arrival_instruction}</p></li></ol>
        </section>}
        <section className="demo-explanation"><h2>What the demonstration computes</h2><p>{data.source}</p><p>Rooms and corridor junctions are graph nodes. Each authored connection is stored in both directions; the stair edge changes floors without drawing a line between coordinate frames. Dijkstra adds one unit per traversal and chooses a least-cost path. The disconnected room deliberately has no edges.</p><p>Illustration pixels are not physical measurements. There are no live closures, outdoor links, GPS, QR starts or claimed accessibility evidence in this isolated graph. Use the unchanged campus explorer for those existing features.</p><p>Version: {data.version}. Original schematics, not copied architectural drawings. This educational preview is not an institutional plan or an approved campus release.</p></section>
      </>}
    </Body>{!embedded && <footer><a href={back}>Return to campus explorer</a><p>{qualification}</p></footer>}
  </div>
}
