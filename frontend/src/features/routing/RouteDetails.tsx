import type { Route } from '../../api/client'

export default function RouteDetails({ route }: { route: Route }) {
  return <section className="route-details" aria-label="Route directions" tabIndex={-1}>
    <div className="eyebrow">YOUR WALK</div>
    <h2>{route.distance_m === 0 ? 'You’re already there' : 'Your route is ready'}</h2>
    <div className="route-metrics"><strong>{Math.round(route.distance_m)} <small>metres</small></strong>
      <strong>{route.estimated_duration_s === 0 ? '0' : Math.max(1, Math.ceil(route.estimated_duration_s / 60))} <small>min · estimated</small></strong></div>
    <ol className="directions">{route.segments.map(segment => <li key={segment.edge_id}>
      <span>{segment.instruction}</span><small>{Math.round(segment.distance_m)} m</small>
    </li>)}<li><span>{route.arrival_instruction}</span></li></ol>
    <details><summary>Route assumptions & data</summary>
      {route.warnings.map(warning => <p key={warning}>{warning}</p>)}
      <p>Release {route.release_id.slice(0, 8)} · generated {new Date(route.generated_at).toLocaleString()}</p>
    </details>
  </section>
}
