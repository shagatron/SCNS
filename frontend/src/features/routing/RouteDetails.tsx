import type { Route } from '../../api/client'

export default function RouteDetails({ route, onView }: { route: Route; onView?: (view: string) => void }) {
  const names = new Map(route.floors?.map(f => [f.id, `${f.building_name} · ${f.label}`]))
  return <section className="route-details" aria-label="Route directions" tabIndex={-1}>
    <div className="eyebrow">YOUR WALK</div>
    <h2>{route.distance_m === 0 ? 'You’re already there' : 'Your route is ready'}</h2>
    {route.cost_mode === 'directions_only' && <p className="notice">Directions only · fewest eligible traversals. This is not a shortest-distance or fastest route.</p>}
    <div className="route-metrics"><strong>{route.distance_m == null ? 'Distance unknown' : <>{Math.round(route.distance_m)} <small>metres</small></>}</strong>
      <strong>{route.estimated_duration_s == null ? 'ETA unavailable' : <>{route.estimated_duration_s === 0 ? '0' : Math.max(1, Math.ceil(route.estimated_duration_s / 60))} <small>min · estimated</small></>}</strong></div>
    {route.distance_m == null && <p>Known distance subtotal: {route.known_distance_m?.toFixed(2) ?? '0'}m. Unknown sections are not counted as zero.</p>}
    <ol className="directions">{route.segments.map(segment => <li key={segment.edge_id}>
      <span>{segment.instruction}</span><small>{segment.distance_m == null ? 'Distance unknown' : `${Math.round(segment.distance_m)} m`}</small>
      {onView && <div>{segment.kind === 'outdoor' || segment.kind === 'entrance_transition' ? <button onClick={() => onView('outdoor')}>Show outdoor section</button> : null}{segment.floor_id && <button onClick={() => onView(segment.floor_id!)}>Show {names.get(segment.floor_id) ?? 'departure floor'}</button>}{segment.to_floor_id && segment.to_floor_id !== segment.floor_id && <button onClick={() => onView(segment.to_floor_id!)}>Show {names.get(segment.to_floor_id) ?? 'arrival floor'}</button>}</div>}
    </li>)}<li><span>{route.arrival_instruction}</span></li></ol>
    <details><summary>Route assumptions & data</summary>
      {route.warnings.map(warning => <p key={warning}>{warning}</p>)}
      <p>Release {route.release_id.slice(0, 8)} · generated {new Date(route.generated_at).toLocaleString()}</p>
    </details>
  </section>
}
