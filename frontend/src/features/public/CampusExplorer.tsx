import type { ReactNode } from 'react'
import { useClosures } from '../closures/useClosures'
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { api, ApiError, calculateRoute, type Campus, type MapData, type Place, type Release, type Search } from '../../api/client'
import type { components } from '../../api/generated'
import type { ConfirmedQR } from '../qr/QRStart'
import RouteDetails from '../routing/RouteDetails'
import '../../styles/public.css'
import '../../styles/explorer.css'
import MapFailureBoundary from '../maps/MapFailureBoundary'
import { ExplorerPlaces, ExplorerPlaceCard } from './ExplorerPlaces'
import OutdoorLocation, { type GPSStart } from '../location/OutdoorLocation'

const FloorRouteMap = lazy(() => import('../maps/FloorRouteMap'))
const OutdoorMap = lazy(() => import('../maps/OutdoorMap'))
const formSchema = z.object({ source: z.uuid(), destination: z.uuid(), profile: z.enum(['shortest', 'step_free', 'fastest']) })

import { CampusOverview, HowNavigationWorks } from './PublicExperience'
import { focusPlanner } from './focusPlanner'

function Failure({ error, retry }: { error: Error; retry: () => void }) {
  return <div className="error-box" role="alert"><p>{error.message}</p><button onClick={retry}>Try again</button></div>
}

type CampusControl = { campuses?: Campus[]; onCampus?: (id: string) => void; locked?: boolean }

export default function CampusExplorer({ campus, online, qrStart, qrNotice, ...campusControl }: { campus: Campus; online: boolean; qrStart?: ConfirmedQR; qrNotice?: ReactNode } & CampusControl) {
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
  const plannerReady = !!(!recovering && (!qrStart || qrStart.release_id === release.data?.id) && initial.data && release.data && initial.data.release_id === release.data.id)
  const unavailable = !!(release.error || initial.error || (qrStart && release.data && qrStart.release_id !== release.data.id))
  return <>
    <div id={plannerReady ? undefined : 'explorer'} data-explorer-ready={!plannerReady && unavailable ? '' : undefined} tabIndex={-1} className={plannerReady ? 'release-notices' : 'editorial-section explorer-availability'}>
    {!plannerReady && <h2>{unavailable ? 'Explorer unavailable' : 'Opening the explorer'}</h2>}
    {changed && <p role="status" className="notice">The campus release changed. Previous route results and selections were cleared; choose destinations and calculate a route on the current map.</p>}
    {release.error && <Failure error={release.error} retry={() => void refreshRelease()} />}
    {recovering && <p role="status">Refreshing campus data; previous route results are hidden.</p>}
    {initial.error && !recovering && <Failure error={initial.error} retry={() => void initial.refetch()} />}
    {!initial.data && !initial.error && !release.error && <p role="status" className="loading">Loading destinations for the current release…</p>}
    {qrStart && release.data && qrStart.release_id !== release.data.id && <p role="status" className="notice">The published map changed. <button onClick={() => window.dispatchEvent(new Event('qr-marker-stale'))}>Recheck and confirm the QR marker</button></p>}
    </div>
    {!recovering && (!qrStart || qrStart.release_id === release.data?.id) && initial.data && release.data && initial.data.release_id === release.data.id && <Planner key={`${release.data.id}:${epoch}`} campus={campus} initial={initial.data} online={online} release={release.data} qrStart={qrStart?.release_id === release.data.id ? qrStart : undefined} qrNotice={qrNotice} {...campusControl} />}
  </>
}

function Planner({ campus, initial, online, release, qrStart, qrNotice, campuses, onCampus, locked }: { campus: Campus; initial: Search; online: boolean; release: Release; qrStart?: ConfirmedQR; qrNotice?: ReactNode } & CampusControl) {
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
  const [selected, setSelected] = useState<Place | undefined>()
  const [panelExpanded, setPanelExpanded] = useState(true)
  const [planning, setPlanning] = useState(true)
  const selectionTrigger = useRef<HTMLElement | null>(null)
  useEffect(() => {
    const open = () => { setPlanning(true); setPanelExpanded(true) }
    window.addEventListener('explorer-open-planner', open)
    return () => window.removeEventListener('explorer-open-planner', open)
  }, [])
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
  const gpsValue = '__gps__'
  const locationContext = `${campus.id}:${release.id}:${closures.data?.closure_overlay_version}:${profile}:${costMode}:${online && closures.fresh ? 'ready' : 'unavailable'}`
  const [locationEpoch, setLocationEpoch] = useState(0)
  const [gps, setGPS] = useState<{ context: string; source: GPSStart; expires: string } | null>(null)
  const validGPS = gps && gps.context === locationContext && new Date(gps.expires).getTime() > closures.clock ? gps.source : undefined
  if (gps && !validGPS) setGPS(null)
  const discardGPS = useCallback(() => { setGPS(null) }, [])

  useEffect(() => { if (closures.data && closures.data.release_id !== release.id) window.dispatchEvent(new Event('campus-release-stale')) }, [closures.data, release.id])
  const [staleRouteId, setStaleRouteId] = useState<string | null>(null)
  const route = useMutation({ mutationFn: calculateRoute, gcTime: 0, onError(error) {
    if (source === gpsValue && error instanceof ApiError && error.code.startsWith('location_')) { setFormError(error.message); discardGPS(); setLocationEpoch(n => n + 1) }
    if (error instanceof ApiError && ['stale_marker', 'qr_unavailable'].includes(error.code)) window.dispatchEvent(new Event('qr-marker-stale'))
    if (error instanceof ApiError && error.code === 'stale_closures') void closures.refetch()
    if (error instanceof ApiError && error.code === 'stale_release') {
      void queryClient.invalidateQueries({ queryKey: ['release', campus.id] })
      void queryClient.invalidateQueries({ queryKey: ['map', campus.id] })
      void queryClient.invalidateQueries({ queryKey: ['places', campus.id] })
      void queryClient.invalidateQueries({ queryKey: ['directory', campus.id] })
    }
  } })
  useEffect(() => { if (!validGPS && route.variables?.source.kind === 'gps') route.reset() }, [validGPS, route])
  const routeUnsafe = !!route.data && (source === gpsValue && !validGPS || !closures.fresh || (route.data.restriction_window_end != null && new Date(route.data.restriction_window_end).getTime() <= closures.clock) || (route.data.next_closure_change_at != null && new Date(route.data.next_closure_change_at).getTime() <= closures.clock) || closures.data?.release_id !== route.data.release_id || closures.data?.closure_overlay_version !== route.data.closure_overlay_version || !!closures.data?.unresolved_count || (closures.data?.next_change_at != null && new Date(closures.data.next_change_at).getTime() <= closures.clock) || (route.data.valid_until != null && new Date(route.data.valid_until).getTime() <= closures.clock && closures.dataUpdatedAt < new Date(route.data.valid_until).getTime()))
  if (routeUnsafe && route.data && staleRouteId !== route.data.id) setStaleRouteId(route.data.id)
  const visibleRoute = route.data && !routeUnsafe && staleRouteId !== route.data.id ? route.data : undefined
  const choices = [...new Map([...initial.items, ...(linkedPlaces.data ?? []), ...selectedPlaces].map(place => [place.id, place])).values()]
  const updateLink = (nextView: string) => { const url = new URL(window.location.href); if (source === gpsValue) { url.search = new URLSearchParams({ campus: campus.id, view: nextView }).toString(); window.history.replaceState(null, '', url); return } url.search = new URLSearchParams({ campus: campus.id, release: release.id, from: source, to: destination, profile, mode: costMode, view: nextView, routed: '1' }).toString(); window.history.replaceState(null, '', url) }
  const showView = (next: string) => { setView(next); if (route.data) updateLink(next) }
  function clear() { route.reset(); setFormError(''); const url = new URL(window.location.href); url.search = new URLSearchParams({ campus: campus.id }).toString(); window.history.replaceState(null, '', url) }
  const reloaded = useRef(false)
  useEffect(() => { if (!reloaded.current && linked && params.get('routed') === '1' && linkedPlaces.data && online && closures.fresh && !closures.isFetching && closures.data?.release_id === release.id) { reloaded.current = true; route.mutate({ campus_id: campus.id, source: { kind: 'place', place_id: source }, destination: { kind: 'place', place_id: destination }, profile, cost_mode: costMode, expected_release_id: release.id, expected_closure_overlay_version: closures.data?.closure_overlay_version }) } }, [linked, linkedPlaces.data, online, params, campus.id, source, destination, profile, costMode, release.id, route, closures.fresh, closures.isFetching, closures.data])
  function selectPlace(place: Place) {
    selectionTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setSelected(place); setPanelExpanded(true)
    setSelectedPlaces(current => [...current.filter(p => p.id !== place.id), place])
  }
  function closePlace() {
    setSelected(undefined)
    requestAnimationFrame(() => {
      const trigger = selectionTrigger.current
      if (trigger?.isConnected) trigger.focus()
      else document.getElementById('search')?.focus()
    })
  }
  function startAt(place: Place) {
    setSelectedPlaces(current => [...current.filter(p => p.id !== place.id), place]); setGPS(null); setLocationEpoch(n => n + 1); setSource(place.id); clear(); setPlanning(true); setPanelExpanded(true); setSelected(undefined); focusPlanner('source')
  }
  function choose(place: Place) {
    if (route.isPending) return
    setSelectedPlaces(current => [...current.filter(p => p.id !== place.id), place])
    setDestination(place.id); clear(); setPlanning(true); setPanelExpanded(true); setSelected(undefined)
    focusPlanner('destination')
  }
  function submit(event: React.FormEvent) {
    event.preventDefault()
    if (source === gpsValue && !validGPS) { setFormError('Request location again or choose a manual/QR starting point.'); return }
    const parsed = formSchema.safeParse({ source: validGPS && source === gpsValue ? validGPS.confirmed_node_id : qrStart && source === qrValue ? qrStart.id : source, destination, profile })
    if (!parsed.success) { setFormError('Choose both a starting point and a destination.'); return }
    if (!closures.fresh || closures.isFetching || closures.data?.release_id !== release.id) { setFormError('Check current operational restrictions before routing. Manual and QR selections remain available.'); return }
    setFormError('')
    route.mutate({ campus_id: campus.id, source: source === gpsValue && validGPS ? validGPS : qrStart && source === qrValue ? { kind: 'qr', marker_id: qrStart.id, expected_marker_version: qrStart.version, confirmed: true } : { kind: 'place', place_id: source }, destination: { kind: 'place', place_id: destination }, profile, cost_mode: costMode, expected_release_id: release.id, expected_closure_overlay_version: closures.data.closure_overlay_version }, { onSuccess(result) { setPanelExpanded(true); const next = result.segments[0]?.floor_id ?? 'outdoor'; setView(next); updateLink(next) } })
  }
  return <>
    <CampusOverview initial={initial} map={!map.error ? map.data : undefined} floors={!floors.error ? floors.data : undefined} />
    <HowNavigationWorks />
    <section id="directory" tabIndex={-1} className="directory editorial-section" aria-labelledby="directory-heading"><div className="directory-header"><div><p className="eyebrow">03 — YOUR NEXT STOP</p><h2 id="directory-heading" className="display-heading" data-reveal>Places worth<br />finding.</h2></div><p className="muted">Browse the published directory. Choose a place to begin or a destination to reach.</p></div>
      <a className="explore-action" href="#explorer">Browse the map directory <span aria-hidden="true">↗</span></a>
    </section>
    <section id="explorer" data-explorer-ready tabIndex={-1} className="editorial-section explorer-section map-workspace" aria-labelledby="explorer-heading">
      <div className="explorer-heading"><div><p className="section-index">04 — THE INTERACTIVE EXPLORER</p><h2 id="explorer-heading" className="display-heading">Your way through.</h2></div><p>{campus.name}{campus.is_demo ? ' · Synthetic data only' : ' · Published campus map'}<br />Choose a known start. Check restrictions before walking.</p></div>
    {qrNotice && <div className="qr-confirmed">{qrNotice}</div>}
    <aside className="workspace-status" aria-label="Route safety and connection">
        {!online && <p role="status">Offline. New routes paused; previously displayed text is not live guidance.</p>}
        <aside className="notice restriction-status" aria-label="Operational restrictions"><p>{closures.fresh ? `Live restrictions checked · overlay v${closures.data?.closure_overlay_version}` : 'Current closures unavailable. A connection and successful check are required for a new route.'}</p><button type="button" disabled={!online || closures.isFetching} onClick={() => void closures.refetch()}>Check restrictions</button>{closures.error && <p role="alert">{closures.error.message}</p>}{closures.data?.unresolved_count ? <p role="alert">A retained restriction needs operator review; routing is paused.</p> : null}{closures.data?.items.map(item => <p key={item.id}>{item.label} · {item.state} · {item.reason}. Estimated end {item.estimated_end_at ? new Date(item.estimated_end_at).toLocaleString() : 'unknown'}; operator verification required.</p>)}</aside>
        {source === gpsValue && <p role="status" className="notice">{validGPS ? 'Outdoor landmark confirmed. Route distance begins at that landmark; request a fresh fix when confirmation expires.' : 'Location confirmation expired or context changed. Request location again or choose a manual/QR start.'}</p>}
        {route.data && !visibleRoute && <p role="alert" className="notice">Previous route hidden: restrictions changed or current closure information is unavailable. Your selections are retained. Check restrictions and calculate again before walking.</p>}
        {route.isPending && <p role="status" className="loading">Calculating a route through mapped paths…</p>}
        {route.error && <div role="alert" className="error-box"><strong>Route unavailable</strong><p>{route.error.message}</p></div>}
        {!panelExpanded && visibleRoute && <p role="status">Route ready · {visibleRoute.distance_m == null ? 'Distance unknown' : `${Math.round(visibleRoute.distance_m)}m`} · {visibleRoute.estimated_duration_s == null ? 'ETA unavailable' : `${Math.ceil(visibleRoute.estimated_duration_s / 60)}min estimated`}. Expand panel for directions and assumptions.</p>}
    </aside>
    <div className="explorer-grid">
      <aside className="explorer-sidebar" aria-label="Campus navigation workspace">
        <div className="workspace-brand"><span aria-hidden="true">↗</span><strong>scns<span> / explorer</span></strong><button className="panel-toggle" aria-expanded={panelExpanded} aria-controls="explorer-panel" onClick={() => setPanelExpanded(!panelExpanded)}>{panelExpanded ? 'Collapse panel' : 'Expand panel'}</button></div>
        {onCampus && <div className="explorer-campus"><label htmlFor="explorer-campus">Explorer campus</label><select id="explorer-campus" value={campus.id} disabled={locked} onChange={e => onCampus(e.target.value)}>{campuses?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>}
              <div className="directory-controls"><div><label htmlFor="search">Search destinations</label><input id="search" type="search" placeholder="Try library, coffee, or a building code" value={q} maxLength={120} onChange={e => { setQ(e.target.value); setOffset(0); setPlanning(false); setPanelExpanded(true) }} /></div>
        <div><label htmlFor="category">Category</label><select id="category" value={category} onChange={e => { setCategory(e.target.value); setOffset(0); setPlanning(false); setPanelExpanded(true) }}><option value="">All places</option>{['building', 'library', 'cafe', 'water', 'washroom', 'entrance', 'garden', 'help', 'room', 'office', 'laboratory', 'facility', 'indoor_destination'].map(kind => <option key={kind} value={kind}>{kind[0].toUpperCase() + kind.slice(1)}</option>)}</select></div></div>
      {directory.isPending && <p role="status">Searching destinations…</p>}
      {directory.error && <Failure error={directory.error} retry={() => void directory.refetch()} />}
        <div className="explorer-mode"><button aria-pressed={!planning} onClick={() => { setPlanning(false); setPanelExpanded(true); requestAnimationFrame(() => document.getElementById('search')?.focus()) }}>Browse places</button><button aria-pressed={planning} onClick={() => { setPlanning(true); setPanelExpanded(true); focusPlanner('destination') }}>Plan route</button></div>
        <div id="explorer-panel" hidden={!panelExpanded}>
      <div hidden={planning}><ExplorerPlaces data={directory.data} selected={selected?.id} pending={route.isPending} onSelect={selectPlace} onRoute={choose} onStart={startAt} /></div>
      {directory.data?.total === 0 && <p className="empty-state">No matching places. Try another name, alias, or category.</p>}
      {directory.data && <div className="pagination"><span aria-live="polite">{directory.data.total} public destinations{directory.data.total > 0 ? ` · showing ${offset + 1}–${Math.min(offset + 6, directory.data.total)}` : ''}</span><button hidden={planning} disabled={offset === 0} onClick={() => setOffset(offset - 6)}>Previous</button><button hidden={planning} disabled={offset + 6 >= directory.data.total} onClick={() => setOffset(offset + 6)}>Next</button></div>}

      <section id="planner" tabIndex={-1} className="planner-card" aria-labelledby="plan-heading">
        <div className="section-title"><span className="eyebrow">ROUTE / START → DESTINATION</span><span aria-hidden="true">↗</span></div><h2 id="plan-heading">Plan your walk</h2><p className="muted">Routes follow eligible stored paths, never straight-line shortcuts.</p>
        <details className="route-controls" open={planning} onToggle={e => setPlanning(e.currentTarget.open)}><summary>Route controls <span aria-hidden="true">＋ / −</span></summary>
        <OutdoorLocation key={`${locationContext}:${locationEpoch}`} campus={campus.id} release={release.id} overlay={closures.data?.closure_overlay_version ?? 0} profile={profile} ready={online && closures.fresh && !closures.isFetching && !route.isPending} onInvalidate={discardGPS} onConfirm={(start, expires) => { setGPS({ context: locationContext, source: start, expires }); setSource(gpsValue); clear() }} />
        <form onSubmit={submit}>
          <fieldset className="planner-fields" disabled={route.isPending}>
            <div className="planner-field"><label htmlFor="source">Starting point</label><select id="source" value={source} onChange={e => { setSource(e.target.value); setGPS(null); setLocationEpoch(n => n + 1); clear() }}><option value="">Choose a starting point</option>{source === gpsValue && <option value={gpsValue}>Outdoor location · {validGPS ? 'confirmed landmark' : 'confirmation required'}</option>}{qrStart && <option value={qrValue}>Confirmed QR · {qrStart.label} · {qrStart.node_label}{qrStart.floor_label ? ` · ${qrStart.floor_label}` : ''}</option>}{choices.map(p => <option key={p.id} value={p.id}>{p.name}{p.floor_label ? ` · ${p.building_name} · ${p.floor_label}` : ''}</option>)}</select></div>
            <div className="swap-row"><span className="connector-line" /><button type="button" disabled={source === qrValue || source === gpsValue} className="text-button" onClick={() => { setSource(destination); setDestination(source); clear() }} aria-label="Swap start and destination">⇅ Swap</button></div>
            <div className="planner-field"><label htmlFor="destination">Destination</label><select id="destination" value={destination} onChange={e => { setDestination(e.target.value); clear() }}><option value="">Where would you like to go?</option>{choices.map(p => <option key={p.id} value={p.id}>{p.name}{p.floor_label ? ` · ${p.building_name} · ${p.floor_label}` : ''}</option>)}</select></div>
            <div className="planner-field"><label htmlFor="profile">Route preference</label><select id="profile" aria-describedby="routing-policy" value={profile} onChange={e => { setProfile(e.target.value as typeof profile); clear() }}><option value="shortest">{costMode === 'directions_only' ? 'Fewest eligible traversals' : 'Shortest walking route'}</option><option value="step_free">Step-free · {campus.is_demo ? 'synthetic verification only' : 'verified access only'}</option><option value="fastest" disabled={costMode === 'directions_only'}>Fastest · supported baseline estimates</option></select></div>
            <div className="planner-field"><label htmlFor="cost-mode">Distance policy</label><select id="cost-mode" aria-describedby="routing-policy" value={costMode} onChange={e => { setCostMode(e.target.value as typeof costMode); if (e.target.value === 'directions_only' && profile === 'fastest') setProfile('shortest'); clear() }}><option value="metric">Metric · stored path distances</option><option value="directions_only">Directions only · unknown distance allowed</option></select></div>
            <button type="submit" className="primary-button" disabled={!online || !closures.fresh || closures.isFetching || (source === gpsValue && !validGPS)}>{route.isPending ? 'Finding your route…' : 'Find walking route'} <span aria-hidden="true">→</span></button>
          </fieldset>
          <p id="routing-policy" className="muted">{costMode === 'directions_only' ? 'Directions only minimises eligible traversals, not distance or time. Displayed distances describe the selected route. Step-free still requires verified access; live restrictions still apply.' : 'Metric routes use stored path distances or supported time estimates. Outdoor lengths, including OSM data, may be estimated; metric eligibility is not field verification.'}</p>
          {formError && <p role="alert" className="error-text">{formError}</p>}
        </form></details>
        {!route.data && !route.error && <div className="planner-hint"><span aria-hidden="true">◎</span><p>Start from a known landmark.<br /><small>Reviewed public routes · no sign-in needed</small></p></div>}
      </section>
    <div className="route-results">
        {visibleRoute && <><div role="status" className="sr-only">Route ready. {visibleRoute.distance_m == null ? 'Distance unknown.' : `${Math.round(visibleRoute.distance_m)} metres.`}</div><RouteDetails route={visibleRoute} onView={showView} /><button className="secondary-button" onClick={() => { clear(); discardGPS(); setLocationEpoch(n => n + 1); if (source === gpsValue) setSource('') }}>Clear route</button></>}
    </div>
      </div></aside>
      <div className="map-column"><div className="map-toolbar"><span>{campus.name} <span className="muted">/ {view === 'outdoor' ? 'Outdoor' : floors.data?.floors.find(f => f.id === view)?.label ?? 'Floor'}</span></span><button className="text-button" onClick={() => setMapVisible(!mapVisible)}>{mapVisible ? 'Hide map' : 'Show map'}</button></div>
        <div className="view-controls"><label htmlFor="public-floor">Building and floor view</label><select id="public-floor" value={view} onChange={e => showView(e.target.value)}><option value="outdoor">Outdoor campus</option>{floors.data?.floors.map(f => <option key={f.id} value={f.id}>{f.building_name} · {f.label} · {f.navigation_mode.replaceAll('_', ' ')}</option>)}</select></div>
        {floors.error && <Failure error={floors.error} retry={() => void floors.refetch()} />}{linkedPlaces.error && <Failure error={linkedPlaces.error} retry={() => void linkedPlaces.refetch()} />}
        {params.get('release') && !linked && <p role="status" className="notice">The shared route belongs to a different release. Choose destinations on the current release; the previous route has not been reused.</p>}
        <MapFailureBoundary key={view}>
        {mapVisible && view !== 'outdoor' && floors.data?.floors.find(f => f.id === view) && <Suspense fallback={<p className="loading" role="status">Loading floor route viewer…</p>}><FloorRouteMap key={view} floor={floors.data.floors.find(f => f.id === view)!} route={visibleRoute} places={choices} selectedId={selected?.id} onSelect={selectPlace} /></Suspense>}
        {mapVisible && view === 'outdoor' && <>{map.error && <Failure error={map.error} retry={() => void map.refetch()} />}
          {map.data && <Suspense fallback={<p className="loading" role="status">Loading map…</p>}><OutdoorMap campus={campus} data={map.data} places={choices} route={visibleRoute} selectedId={selected?.id} onSelect={selectPlace} /></Suspense>}
          {map.isPending && <p role="status" className="loading">Loading campus paths…</p>}</>}
        </MapFailureBoundary>
        {!mapVisible && <p className="empty-state">Map hidden. Plan your walk and follow the text directions.</p>}
        {selected && <ExplorerPlaceCard place={selected} pending={route.isPending} onClose={closePlace} onRoute={() => choose(selected)} onStart={() => startAt(selected)} />}
        <div className="map-footnote"><span>↗ Routes follow mapped paths</span><span>{`Published release ${release.version}`}</span></div>
      </div>
    </div>
</section>


  </>
}
