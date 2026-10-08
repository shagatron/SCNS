import { useClosures } from '../features/closures/useClosures'
import { lazy, Suspense, useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { api, ApiError, calculateRoute, type Campus, type MapData, type Place, type Release, type Search } from '../api/client'
import type { components } from '../api/generated'
import type { ConfirmedQR } from '../features/qr/QRStart'
import RouteDetails from '../features/routing/RouteDetails'

const FloorRouteMap = lazy(() => import('../features/maps/FloorRouteMap'))
const OutdoorMap = lazy(() => import('../features/maps/OutdoorMap'))
const formSchema = z.object({ source: z.uuid(), destination: z.uuid(), profile: z.enum(['shortest', 'step_free', 'fastest']) })

function subscribeOnline(onChange: () => void) {
  window.addEventListener('online', onChange)
  window.addEventListener('offline', onChange)
  return () => { window.removeEventListener('online', onChange); window.removeEventListener('offline', onChange) }
}

function Failure({ error, retry }: { error: Error; retry: () => void }) {
  return <div className="error-box" role="alert"><p>{error.message}</p><button onClick={retry}>Try again</button></div>
}

export default function App({ qrStart }: { qrStart?: ConfirmedQR }) {
  const online = useSyncExternalStore(subscribeOnline, () => navigator.onLine)
  const campuses = useQuery({ queryKey: ['campuses'], queryFn: () => api<Campus[]>('/campuses') })
  const health = useQuery({ queryKey: ['health'], queryFn: () => api('/health/ready'), retry: false })
  const [campusId, setCampusId] = useState(() => qrStart?.campus_id ?? new URLSearchParams(window.location.search).get('campus') ?? '')
  const campus = campuses.data?.find(c => c.id === campusId) ?? campuses.data?.[0]
  return <>
    <a className="skip-link" href="#planner">Skip to route planner</a>
    <header className="site-header"><a className="brand" href="#"><span className="brand-mark" aria-hidden="true">↗</span><span>Campus<span className="brand-light">ways</span><small>SMART CAMPUS NAVIGATION</small></span></a>
      <nav aria-label="Main navigation"><a href="#planner">Explore</a><a href="#directory">Directory</a><a href="#about">About the data</a></nav>
      <span className="demo-pill">SYNTHETIC DEMO</span>
    </header>
    <main>
      <div className="page-intro"><div><p className="eyebrow">A LITTLE LESS LOST. A LOT MORE CAMPUS.</p><h1>Find your way around.</h1><p>Choose a place. Plan your walk. Explore what’s nearby.</p></div>
        <div className="campus-control"><label htmlFor="campus">Explore campus</label><select id="campus" disabled={!!qrStart} value={campus?.id ?? ''} onChange={e => setCampusId(e.target.value)}>
          {campuses.data?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select><span className="connection"><i className={online && health.isSuccess ? 'status-dot' : 'status-dot offline'} />{!online ? 'Offline · connection needed for new routes' : health.isSuccess ? 'Campus service connected' : 'Checking campus service…'}</span></div>
      </div>
      <aside className="demo-banner"><span aria-hidden="true">ⓘ</span><p><strong>This is a synthetic campus.</strong> All locations, coordinates, and paths are invented for demonstration. Do not use them for real-world navigation.</p></aside>
      {campuses.isPending && <p role="status" className="loading">Loading campus…</p>}
      {campuses.error && <Failure error={campuses.error} retry={() => void campuses.refetch()} />}
      {campuses.data?.length === 0 && <section className="empty-state"><h2>No published campus yet</h2><p>Prepare an authorized map and verified paths, or explicitly seed the synthetic demo using the setup guide.</p></section>}
      {campus && <CampusExplorer key={campus.id} campus={campus} online={online} qrStart={qrStart} />}
      <section id="about" className="about"><div><p className="eyebrow">KNOW YOUR MAP</p><h2>A demo with clear boundaries.</h2></div>
        <p>These outdoor paths demonstrate graph-based navigation. Distances follow the synthetic paths; walking times are estimates. Reviewed indoor floors and verified connectors can support floor-to-floor and outdoor routes. Static availability and time estimates are not live lift monitoring. Live restrictions can be recorded by authorized campus operators; an estimated end never confirms reopening. Official campus data is not provided.</p>
        <details><summary>Preparing official campus data</summary><p>Gather permitted overview maps, building names, surveyed entrances, path connections, and accessibility evidence. Upload spaces and versioned templates are documented in the repository’s data guide. Real data must enter a new campus draft and be reviewed before publication.</p></details>
      </section>
    </main>
    <footer><span>Campusways <span aria-hidden="true">↗</span></span><p>Made for a more walkable campus. Demo data only.</p><a href="/api/v1/health/ready">API health</a></footer>
  </>
}

function CampusExplorer({ campus, online, qrStart }: { campus: Campus; online: boolean; qrStart?: ConfirmedQR }) {
  const cache = useQueryClient()
  const release = useQuery({ retry: false, queryKey: ['release', campus.id], queryFn: () => api<Release>(`/campuses/${campus.id}/release`), refetchInterval: online ? 30000 : false })
  const [seen, setSeen] = useState<string | null>(null)
  const [changed, setChanged] = useState(false)
  if (release.data && seen !== release.data.id) { setSeen(release.data.id); if (seen) setChanged(true) }
  const [recovering, setRecovering] = useState(false)
  const recoveryDataTimestamp = useRef(0)
  const [epoch, setEpoch] = useState(0)
  const refreshRelease = useCallback(async () => {
    recoveryDataTimestamp.current = cache.getQueryState(['release', campus.id])?.dataUpdatedAt ?? 0
    setChanged(true); setRecovering(true)
    try {
      await cache.fetchQuery({ queryKey: ['release', campus.id], queryFn: () => api<Release>(`/campuses/${campus.id}/release`), staleTime: 0, retry: false })
    } catch { /* Query error remains visible; keep stale results hidden until retry succeeds. */ }
  }, [cache, campus.id])
  useEffect(() => {
    // A successful periodic/focus fetch must also finish a failed stale refresh.
    // Cached metadata from before recovery must never reveal the old planner.
    if (recovering && !release.error && release.dataUpdatedAt > recoveryDataTimestamp.current) {
      setEpoch(value => value + 1); setRecovering(false)
    }
  }, [recovering, release.error, release.dataUpdatedAt])
  useEffect(() => {
    const refresh = () => { void refreshRelease() }
    window.addEventListener('campus-release-stale', refresh)
    return () => window.removeEventListener('campus-release-stale', refresh)
  }, [refreshRelease])
  const id = release.data?.id
  const initial = useQuery({ queryKey: ['places', campus.id, id], enabled: !!id, retry: false, queryFn: ({ signal }) => api<Search>(`/campuses/${campus.id}/search?limit=100&expected_release_id=${id}`, { signal }) })
  return <>
    {changed && <p role="status" className="notice">The campus release changed. Previous route results and selections were cleared; choose destinations and calculate a route on the current map.</p>}
    {release.error && <Failure error={release.error} retry={() => void refreshRelease()} />}
    {recovering && <p role="status">Refreshing campus data; previous route results are hidden.</p>}
    {initial.error && !recovering && <Failure error={initial.error} retry={() => void initial.refetch()} />}
    {!initial.data && !initial.error && <p role="status" className="loading">Loading destinations for the current release…</p>}
    {qrStart && release.data && qrStart.release_id !== release.data.id && <p role="status" className="notice">The published map changed. <button onClick={() => window.dispatchEvent(new Event('qr-marker-stale'))}>Recheck and confirm the QR marker</button></p>}
    {!recovering && (!qrStart || qrStart.release_id === release.data?.id) && initial.data && release.data && initial.data.release_id === release.data.id && <Planner key={`${release.data.id}:${epoch}`} campus={campus} initial={initial.data} online={online} release={release.data} qrStart={qrStart?.release_id === release.data.id ? qrStart : undefined} />}
  </>
}

function Planner({ campus, initial, online, release, qrStart }: { campus: Campus; initial: Search; online: boolean; release: Release; qrStart?: ConfirmedQR }) {
  const [params] = useState(() => new URLSearchParams(window.location.search))
  const linked = !qrStart && params.get('campus') === campus.id && params.get('release') === release.id
  const qrValue = qrStart ? `qr:${qrStart.id}` : ''
  const [source, setSource] = useState(qrValue || ((linked && z.uuid().safeParse(params.get('from')).success ? params.get('from') : null) ?? initial.items.find(p => p.code === 'GATE')?.id ?? initial.items[0]?.id ?? ''))
  const [destination, setDestination] = useState(linked && z.uuid().safeParse(params.get('to')).success ? params.get('to')! : '')
  const [profile, setProfile] = useState<'shortest' | 'step_free' | 'fastest'>(linked && ['shortest', 'step_free', 'fastest'].includes(params.get('profile') ?? '') ? params.get('profile') as 'shortest' | 'step_free' | 'fastest' : 'shortest')
  const [costMode, setCostMode] = useState<'metric' | 'directions_only'>(linked && params.get('mode') === 'directions_only' ? 'directions_only' : 'metric')
  const [view, setView] = useState(linked ? params.get('view') ?? 'outdoor' : 'outdoor')
  const floors = useQuery({ queryKey: ['floors', campus.id, release.id], retry: false, queryFn: () => api<components['schemas']['FloorsOut']>(`/campuses/${campus.id}/floors?expected_release_id=${release.id}`) })
  const linkedPlaces = useQuery({ queryKey: ['linked-places', campus.id, release.id, source, destination], enabled: linked && !!source && !!destination, retry: false, queryFn: () => Promise.all([source, destination].map(id => api<Place>(`/campuses/${campus.id}/places/${id}?expected_release_id=${release.id}`))) })
  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [offset, setOffset] = useState(0)
  const [formError, setFormError] = useState('')
  const [mapVisible, setMapVisible] = useState(true)
  const [selectedPlaces, setSelectedPlaces] = useState<Place[]>([])
  const queryClient = useQueryClient()
  const directory = useQuery({ retry: false, queryKey: ['directory', campus.id, release.id, q, category, offset], queryFn: ({ signal }) => api<Search>(`/campuses/${campus.id}/search?${new URLSearchParams({ q, kind: category, offset: String(offset), limit: '6', expected_release_id: release.id })}`, { signal }) })
  const positions = campus.boundary.coordinates[0]
  const bbox = [Math.min(...positions.map(p => p[0])), Math.min(...positions.map(p => p[1])), Math.max(...positions.map(p => p[0])), Math.max(...positions.map(p => p[1]))].join(',')
  const map = useQuery({ queryKey: ['map', campus.id, release.id], retry: false, queryFn: ({ signal }) => api<MapData>(`/campuses/${campus.id}/map?bbox=${bbox}&zoom=17&expected_release_id=${release.id}`, { signal }) })
  const closures = useClosures(campus.id, online)
  useEffect(() => { if (closures.data && closures.data.release_id !== release.id) window.dispatchEvent(new Event('campus-release-stale')) }, [closures.data, release.id])
  const [staleRouteId, setStaleRouteId] = useState<string | null>(null)
  const route = useMutation({ mutationFn: calculateRoute, onError(error) {
    if (error instanceof ApiError && ['stale_marker', 'qr_unavailable'].includes(error.code)) window.dispatchEvent(new Event('qr-marker-stale'))
    if (error instanceof ApiError && error.code === 'stale_closures') void closures.refetch()
    if (error instanceof ApiError && error.code === 'stale_release') {
      void queryClient.invalidateQueries({ queryKey: ['release', campus.id] })
      void queryClient.invalidateQueries({ queryKey: ['map', campus.id] })
      void queryClient.invalidateQueries({ queryKey: ['places', campus.id] })
      void queryClient.invalidateQueries({ queryKey: ['directory', campus.id] })
    }
  } })
  const routeUnsafe = !!route.data && (!closures.fresh || (route.data.restriction_window_end != null && new Date(route.data.restriction_window_end).getTime() <= closures.clock) || (route.data.next_closure_change_at != null && new Date(route.data.next_closure_change_at).getTime() <= closures.clock) || closures.data?.release_id !== route.data.release_id || closures.data?.closure_overlay_version !== route.data.closure_overlay_version || !!closures.data?.unresolved_count || (closures.data?.next_change_at != null && new Date(closures.data.next_change_at).getTime() <= closures.clock) || (route.data.valid_until != null && new Date(route.data.valid_until).getTime() <= closures.clock && closures.dataUpdatedAt < new Date(route.data.valid_until).getTime()))
  if (routeUnsafe && route.data && staleRouteId !== route.data.id) setStaleRouteId(route.data.id)
  const visibleRoute = route.data && !routeUnsafe && staleRouteId !== route.data.id ? route.data : undefined
  const choices = [...new Map([...initial.items, ...(linkedPlaces.data ?? []), ...selectedPlaces].map(place => [place.id, place])).values()]
  const updateLink = (nextView: string) => { const url = new URL(window.location.href); url.search = new URLSearchParams({ campus: campus.id, release: release.id, from: source, to: destination, profile, mode: costMode, view: nextView, routed: '1' }).toString(); window.history.replaceState(null, '', url) }
  const showView = (next: string) => { setView(next); if (route.data) updateLink(next) }
  function clear() { route.reset(); setFormError(''); const url = new URL(window.location.href); url.search = new URLSearchParams({ campus: campus.id }).toString(); window.history.replaceState(null, '', url) }
  const reloaded = useRef(false)
  useEffect(() => { if (!reloaded.current && linked && params.get('routed') === '1' && linkedPlaces.data && online && closures.fresh && closures.data?.release_id === release.id) { reloaded.current = true; route.mutate({ campus_id: campus.id, source: { kind: 'place', place_id: source }, destination: { kind: 'place', place_id: destination }, profile, cost_mode: costMode, expected_release_id: release.id, expected_closure_overlay_version: closures.data?.closure_overlay_version }) } }, [linked, linkedPlaces.data, online, params, campus.id, source, destination, profile, costMode, release.id, route, closures.fresh, closures.data])
  function choose(place: Place) {
    if (route.isPending) return
    setSelectedPlaces(current => [...current.filter(p => p.id !== place.id), place])
    setDestination(place.id); clear()
    document.getElementById('destination')?.focus()
  }
  function submit(event: React.FormEvent) {
    event.preventDefault()
    const parsed = formSchema.safeParse({ source: qrStart && source === qrValue ? qrStart.id : source, destination, profile })
    if (!parsed.success) { setFormError('Choose both a starting point and a destination.'); return }
    if (!closures.fresh || (route.data.restriction_window_end != null && new Date(route.data.restriction_window_end).getTime() <= closures.clock) || (route.data.next_closure_change_at != null && new Date(route.data.next_closure_change_at).getTime() <= closures.clock) || closures.data?.release_id !== release.id) { setFormError('Check current operational restrictions before routing. Manual and QR selections remain available.'); return }
    setFormError('')
    route.mutate({ campus_id: campus.id, source: qrStart && source === qrValue ? { kind: 'qr', marker_id: qrStart.id, expected_marker_version: qrStart.version, confirmed: true } : { kind: 'place', place_id: source }, destination: { kind: 'place', place_id: destination }, profile, cost_mode: costMode, expected_release_id: release.id, expected_closure_overlay_version: closures.data.closure_overlay_version }, { onSuccess(result) { const next = result.segments[0]?.floor_id ?? 'outdoor'; setView(next); updateLink(next) } })
  }
  return <>
    <div className="explorer-grid">
      <section id="planner" className="planner-card" aria-labelledby="plan-heading">
        <div className="section-title"><span className="eyebrow">LET’S GET YOU THERE</span><span aria-hidden="true">↗</span></div><h2 id="plan-heading">Plan your walk</h2><p className="muted">Your next destination is a few steps away.</p>
        <aside className="notice" aria-label="Operational restrictions"><p>{closures.fresh ? `Live restrictions checked · overlay v${closures.data?.closure_overlay_version}` : 'Current closures unavailable. A connection and successful check are required for a new route.'}</p><button type="button" disabled={!online || closures.isFetching} onClick={() => void closures.refetch()}>Check restrictions</button>{closures.error && <p role="alert">{closures.error.message}</p>}{closures.data?.unresolved_count ? <p role="alert">A retained restriction needs operator review; routing is paused.</p> : null}{closures.data?.items.map(item => <p key={item.id}>{item.label} · {item.state} · {item.reason}. Estimated end {item.estimated_end_at ? new Date(item.estimated_end_at).toLocaleString() : 'unknown'}; operator verification required.</p>)}</aside>
        <form onSubmit={submit}>
          <fieldset disabled={route.isPending}>
            <label htmlFor="source">Starting point</label><select id="source" value={source} onChange={e => { setSource(e.target.value); clear() }}><option value="">Choose a starting point</option>{qrStart && <option value={qrValue}>Confirmed QR · {qrStart.label} · {qrStart.node_label}{qrStart.floor_label ? ` · ${qrStart.floor_label}` : ''}</option>}{choices.map(p => <option key={p.id} value={p.id}>{p.name}{p.floor_label ? ` · ${p.building_name} · ${p.floor_label}` : ''}</option>)}</select>
            <div className="swap-row"><span className="connector-line" /><button type="button" disabled={source === qrValue} className="text-button" onClick={() => { setSource(destination); setDestination(source); clear() }} aria-label="Swap start and destination">⇅ Swap</button></div>
            <label htmlFor="destination">Destination</label><select id="destination" value={destination} onChange={e => { setDestination(e.target.value); clear() }}><option value="">Where would you like to go?</option>{choices.map(p => <option key={p.id} value={p.id}>{p.name}{p.floor_label ? ` · ${p.building_name} · ${p.floor_label}` : ''}</option>)}</select>
            <label htmlFor="profile">Route preference</label><select id="profile" value={profile} onChange={e => { setProfile(e.target.value as typeof profile); clear() }}><option value="shortest">Shortest walking route</option><option value="step_free">Step-free · synthetic verification only</option><option value="fastest" disabled={costMode === 'directions_only'}>Fastest · supported baseline estimates</option></select>
            <label htmlFor="cost-mode">Distance policy</label><select id="cost-mode" value={costMode} onChange={e => { setCostMode(e.target.value as typeof costMode); if (e.target.value === 'directions_only' && profile === 'fastest') setProfile('shortest'); clear() }}><option value="metric">Verified metric paths</option><option value="directions_only">Directions only · unknown distance allowed</option></select>
            <button type="submit" className="primary-button" disabled={!online || !closures.fresh}>{route.isPending ? 'Finding your route…' : 'Find walking route'} <span aria-hidden="true">→</span></button>
          </fieldset>
          {formError && <p role="alert" className="error-text">{formError}</p>}
        </form>
        {route.data && !visibleRoute && <p role="alert" className="notice">Previous route hidden: restrictions changed or current closure information is unavailable. Your selections are retained. Check restrictions and calculate again before walking.</p>}
        {route.isPending && <p role="status">Calculating a route through mapped paths…</p>}
        {route.error && <div role="alert" className="error-box"><strong>Route unavailable</strong><p>{route.error.message}</p></div>}
        {visibleRoute && <><div role="status" className="sr-only">Route ready. {visibleRoute.distance_m == null ? 'Distance unknown.' : `${Math.round(visibleRoute.distance_m)} metres.`}</div><RouteDetails route={visibleRoute} onView={showView} /><button className="secondary-button" onClick={clear}>Clear route</button></>}
        {!route.data && !route.error && <div className="planner-hint"><span aria-hidden="true">◎</span><p>Start from a known landmark.<br /><small>Reviewed public routes · no sign-in needed</small></p></div>}
      </section>
      <div className="map-column"><div className="map-toolbar"><span>{campus.name} <span className="muted">/ {view === 'outdoor' ? 'Outdoor' : floors.data?.floors.find(f => f.id === view)?.label ?? 'Floor'}</span></span><button className="text-button" onClick={() => setMapVisible(!mapVisible)}>{mapVisible ? 'Hide map' : 'Show map'}</button></div>
        <label htmlFor="public-floor">Building and floor view</label><select id="public-floor" value={view} onChange={e => showView(e.target.value)}><option value="outdoor">Outdoor campus</option>{floors.data?.floors.map(f => <option key={f.id} value={f.id}>{f.building_name} · {f.label} · {f.navigation_mode.replaceAll('_', ' ')}</option>)}</select>
        {floors.error && <Failure error={floors.error} retry={() => void floors.refetch()} />}{linkedPlaces.error && <Failure error={linkedPlaces.error} retry={() => void linkedPlaces.refetch()} />}
        {params.get('release') && !linked && <p role="status" className="notice">The shared route belongs to a different release. Choose destinations on the current release; the previous route has not been reused.</p>}
        {mapVisible && view !== 'outdoor' && floors.data?.floors.find(f => f.id === view) && <Suspense fallback={<p>Loading floor route viewer…</p>}><FloorRouteMap key={view} floor={floors.data.floors.find(f => f.id === view)!} route={visibleRoute} places={choices} /></Suspense>}
        {mapVisible && view === 'outdoor' && <>{map.error && <Failure error={map.error} retry={() => void map.refetch()} />}
          {map.data && <Suspense fallback={<p className="loading">Loading map…</p>}><OutdoorMap campus={campus} data={map.data} places={initial.items} route={visibleRoute} onDestination={choose} /></Suspense>}
          {map.isPending && <p role="status" className="loading">Loading campus paths…</p>}</>}
        {!mapVisible && <p className="empty-state">Map hidden. Plan your walk and follow the text directions.</p>}
        <div className="map-footnote"><span>↗ Routes follow mapped paths</span><span>{`Demo release ${release.version}`}</span></div>
      </div>
    </div>
    <section id="directory" className="directory" aria-labelledby="directory-heading"><div className="directory-header"><div><p className="eyebrow">FIND YOUR NEXT STOP</p><h2 id="directory-heading">Explore the campus</h2></div><p className="muted">Buildings, everyday essentials, and quiet corners.</p></div>
      <div className="directory-controls"><div><label htmlFor="search">Search destinations</label><input id="search" type="search" placeholder="Try library, coffee, or a building code" value={q} maxLength={120} onChange={e => { setQ(e.target.value); setOffset(0) }} /></div>
        <div><label htmlFor="category">Category</label><select id="category" value={category} onChange={e => { setCategory(e.target.value); setOffset(0) }}><option value="">All places</option>{['building', 'library', 'cafe', 'water', 'washroom', 'entrance', 'garden', 'help', 'room', 'office', 'laboratory', 'facility', 'indoor_destination'].map(kind => <option key={kind} value={kind}>{kind[0].toUpperCase() + kind.slice(1)}</option>)}</select></div></div>
      {directory.isPending && <p role="status">Searching destinations…</p>}
      {directory.error && <Failure error={directory.error} retry={() => void directory.refetch()} />}
      <div className="places-grid">{directory.data?.items.map(place => <article className="place-card" key={place.id}><div className={`place-icon icon-${place.kind}`} aria-hidden="true">{({ library: '▤', cafe: '☕', water: '◉', garden: '❋', entrance: '↗' } as Record<string, string>)[place.kind] ?? '▦'}</div>
        <div className="place-card-body"><p className="eyebrow">{place.kind}</p><h3>{place.name}</h3><p>{place.building_name ?? 'Outdoor destination'}</p><details><summary>Place details</summary><p>{place.description}</p><p>Code: {place.code} · Accessibility: unknown until surveyed.</p></details>
          {place.floor_label && <p>Floor: {place.floor_label} · Room {place.room_code}</p>}
          {!place.routable && <p className="unavailable">{place.navigation_mode === 'indoor_catalog_only' ? 'Indoor catalog only · no reviewed routing capability or eligible door' : 'Entrance not mapped · routing unavailable'}</p>}
          <button disabled={route.isPending} className="text-button" onClick={() => choose(place)} aria-label={`Route to ${place.name}`}>Route here <span aria-hidden="true">↗</span></button>
          <button disabled={route.isPending} className="text-button start-here" onClick={() => { setSelectedPlaces(current => [...current, place]); setSource(place.id); clear(); document.getElementById('source')?.focus() }} aria-label={`Start at ${place.name}`}>Start here</button>
        </div></article>)}</div>
      {directory.data?.total === 0 && <p className="empty-state">No matching places. Try another name, alias, or category.</p>}
      {directory.data && <div className="pagination"><span aria-live="polite">{directory.data.total} public destinations{directory.data.total > 0 ? ` · showing ${offset + 1}–${Math.min(offset + 6, directory.data.total)}` : ''}</span><button disabled={offset === 0} onClick={() => setOffset(offset - 6)}>Previous</button><button disabled={offset + 6 >= directory.data.total} onClick={() => setOffset(offset + 6)}>Next</button></div>}
    </section>
  </>
}
