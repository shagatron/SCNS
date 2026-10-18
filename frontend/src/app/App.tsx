import { useState, useSyncExternalStore, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type Campus } from '../api/client'
import type { ConfirmedQR } from '../features/qr/QRStart'
import CampusExplorer from '../features/public/CampusExplorer'
import { CampusOpening, PublicMotion, PublicNavigation } from '../features/public/PublicExperience'
import '../styles/public.css'

function subscribeOnline(onChange: () => void) {
  window.addEventListener('online', onChange); window.addEventListener('offline', onChange)
  return () => { window.removeEventListener('online', onChange); window.removeEventListener('offline', onChange) }
}
export default function App({ qrStart, qrNotice }: { qrStart?: ConfirmedQR; qrNotice?: ReactNode }) {
  const online = useSyncExternalStore(subscribeOnline, () => navigator.onLine)
  const campuses = useQuery({ queryKey: ['campuses'], queryFn: () => api<Campus[]>('/campuses') })
  const health = useQuery({ queryKey: ['health'], queryFn: () => api('/health/ready'), retry: false })
  const [campusId, setCampusId] = useState(() => qrStart?.campus_id ?? new URLSearchParams(window.location.search).get('campus') ?? '')
  const campus = campuses.data?.find(c => c.id === campusId) ?? campuses.data?.[0]
  return <div className="public-app">
    <a className="skip-link" href="#planner" onClick={event => {
      const panel = document.querySelector<HTMLElement>('#indoor-demo-panel:not([hidden])')
      const demo = panel?.querySelector<HTMLElement>('#demo-planner') ?? panel
      if (demo) { event.preventDefault(); demo.focus(); demo.scrollIntoView({ block: 'start' }) }
    }}>Skip to route planner</a><PublicNavigation />
    <main>
      <CampusOpening campus={campus} campuses={campuses.data} locked={!!qrStart} onCampus={setCampusId} online={online} connected={health.isSuccess} unavailable={health.isError} />
      {campuses.isPending && <section id="explorer" className="editorial-section" role="status"><h2>Loading campus…</h2><p>The explorer will use the current published map.</p></section>}
      {campuses.error && <section id="explorer" data-explorer-ready className="editorial-section"><div className="error-box" role="alert"><h2>Campus data unavailable</h2><p>{campuses.error.message}</p><button onClick={() => void campuses.refetch()}>Try again</button></div></section>}
      {campuses.data?.length === 0 && <section id="explorer" data-explorer-ready className="editorial-section empty-state"><h2>No published campus yet</h2><p>Prepare an authorized map and verified paths. Counts and destinations appear only when a release is available.</p></section>}
      {campus && <CampusExplorer key={campus.id} campus={campus} online={online} qrStart={qrStart} qrNotice={qrNotice} />}
      <section id="about" tabIndex={-1} className="editorial-section about" aria-labelledby="about-heading"><div><p className="section-index">05 — KNOW YOUR MAP</p><h2 id="about-heading" className="display-heading">Clear paths.<br />Clear limits.</h2></div><div><p>{campus?.is_demo ? 'This campus is entirely synthetic. Its locations, paths, dimensions and accessibility evidence are invented. Do not use it for real-world navigation.' : 'Use the selected campus’s published map and its stated source and accessibility limitations.'}</p><p>Distances follow stored paths; walking times are estimates. Reviewed indoor floors and connectors support floor-to-floor and outdoor routes. Static availability and estimates are not live lift monitoring. Operators can record live restrictions; an estimated end never confirms reopening.</p><details><summary>Preparing official campus data</summary><p>Gather permitted overview maps, building names, surveyed entrances, path connections and accessibility evidence. Versioned templates and private uploads are documented in the repository. Real data must enter a new campus draft and pass independent review before publication.</p></details></div></section>
      <PublicMotion direct={!!qrStart || new URLSearchParams(window.location.search).has('routed') || new URLSearchParams(window.location.search).get('explorer') === 'indoor-demo'} />
    </main>
    <footer><a className="public-wordmark" href="#intro">scns<span aria-hidden="true">↗</span></a><p>Smart Campus Navigation / Graphs into directions.</p><a href="/api/v1/health/ready">API health ↗</a></footer>
  </div>
}
