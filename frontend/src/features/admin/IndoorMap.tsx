import { useEffect, useState } from 'react'
import { CRS } from 'leaflet'
import { CircleMarker, ImageOverlay, MapContainer, Polyline, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import { mapToPixel, pixelToMap } from './floorplanCoordinates'
import { point, type Indoor, type Point, type Selection } from './indoorState'
import 'leaflet/dist/leaflet.css'
type Props = { graph: Indoor; url: string; selected: Selection; tool: string; select: (s: Selection) => void; pick: (p: Point) => void; vertex: (i: number) => void }
function Controls({ graph, tool, pick }: Pick<Props, 'graph' | 'tool' | 'pick'>) {
  const map = useMap(), w = graph.floor.width_px!, h = graph.floor.height_px!
  useMapEvents({ click(e) { if (tool === 'select') return; try { const p = mapToPixel(e.latlng.lat, e.latlng.lng, w, h); pick([p.x, p.y]) } catch { /* Outside-plan coordinates are never saved. */ } } })
  useEffect(() => { const fit = () => { map.invalidateSize(); map.fitBounds([[0, 0], [h, w]], { padding: [16, 16], animate: false }) }; fit(); const observer = new ResizeObserver(fit); observer.observe(map.getContainer()); return () => observer.disconnect() }, [map, w, h])
  return <button type="button" className="map-fit" onClick={() => map.fitBounds([[0, 0], [h, w]], { padding: [16, 16], animate: false })}>Fit indoor plan</button>
}
export default function IndoorMap(props: Props) {
  const { graph, selected, select, vertex, url } = props, h = graph.floor.height_px!, w = graph.floor.width_px!
  const [opacity, setOpacity] = useState(.65), [status, setStatus] = useState('Loading private plan…'), [attempt, setAttempt] = useState(0)
  const bounds = (p: number[]) => p.length === 2 && p.every(Number.isFinite) && p[0] >= 0 && p[0] <= w && p[1] >= 0 && p[1] <= h
  const mapped = (p: number[]) => pixelToMap({ x: p[0], y: p[1] }, h)
  const active = selected?.entity === 'edges' ? graph.edges[selected.id] : undefined
  return <div className="graph-map-panel"><label>Plan opacity<input type="range" min="0" max="1" step="0.05" value={opacity} onChange={e => setOpacity(Number(e.target.value))} /></label><p role="status">{status}</p>{status.startsWith('Cannot') && <button onClick={() => { setAttempt(n => n + 1); setStatus('Loading private plan…') }}>Retry indoor plan</button>}
    <MapContainer key={`${url}:${attempt}`} crs={CRS.Simple} center={[h / 2, w / 2]} zoom={0} minZoom={-5} maxZoom={4} className="graph-map" scrollWheelZoom>
      <ImageOverlay url={url} opacity={opacity} bounds={[[0, 0], [h, w]]} eventHandlers={{ load: () => setStatus(`Reference ${w} × ${h}px · x right / y down`), error: () => setStatus('Cannot load private plan. Your edits are retained.') }} />
      {Object.entries(graph.edges).filter(([, e]) => e.polyline.length >= 2 && e.polyline.every(bounds)).map(([id, e]) => <Polyline key={id} bubblingMouseEvents={false} positions={e.polyline.map(mapped)} pathOptions={{ color: selected?.id === id ? '#a24300' : e.visibility === 'restricted' ? '#88438d' : '#146158', weight: selected?.id === id ? 7 : 4, dashArray: e.is_open ? undefined : '6,6' }} eventHandlers={{ click: () => select({ entity: 'edges', id }) }}><Tooltip>{e.kind} · {e.from_node_id.slice(0, 8)} → {e.to_node_id.slice(0, 8)} · {e.accessibility_status}</Tooltip></Polyline>)}
      {Object.entries(graph.nodes).filter(([, n]) => bounds(point(n))).map(([id, n]) => <CircleMarker key={id} bubblingMouseEvents={false} center={mapped(point(n))} radius={n.kind === 'door' ? 7 : 5} pathOptions={{ color: selected?.id === id ? '#a24300' : n.visibility === 'restricted' ? '#88438d' : '#163e69', fillOpacity: .8 }} eventHandlers={{ click: () => select({ entity: 'nodes', id }) }}><Tooltip>{n.kind} · {n.label} · {n.evidence || 'Source unknown'} · verified {n.verified_on || 'unknown'}</Tooltip></CircleMarker>)}
      {Object.entries(graph.rooms).filter(([, r]) => bounds(point(r))).map(([id, r]) => <CircleMarker key={id} bubblingMouseEvents={false} center={mapped(point(r))} radius={9} pathOptions={{ color: selected?.id === id ? '#a24300' : r.visibility === 'restricted' ? '#88438d' : '#49631c', fillOpacity: .2 }} eventHandlers={{ click: () => select({ entity: 'rooms', id }) }}><Tooltip permanent>{r.code} · {r.name}</Tooltip></CircleMarker>)}
      {Object.values(graph.access).map(a => { const r = graph.rooms[a.room_id], n = graph.nodes[a.node_id]; return r && n && bounds(point(r)) && bounds(point(n)) && <Polyline key={`${a.room_id}:${a.node_id}`} positions={[mapped(point(r)), mapped(point(n))]} pathOptions={{ color: '#637261', weight: 2, dashArray: '3,5' }}><Tooltip>Explicit door relationship; dotted link is not a walking path</Tooltip></Polyline> })}
      {active?.polyline.map((p, i) => bounds(p) && i > 0 && i < active.polyline.length - 1 && <CircleMarker key={`v${i}`} bubblingMouseEvents={false} center={mapped(p)} radius={6} pathOptions={{ color: '#a24300' }} eventHandlers={{ click: () => vertex(i) }}><Tooltip>Interior vertex {i}</Tooltip></CircleMarker>)}
      <Controls {...props} />
    </MapContainer><p>Green labels are destinations; blue nodes are topology; purple is restricted. Arrows/directions are stored endpoints. Dotted room–door links are relationships, not traversable room-centre paths. Crossing lines and snapped coordinates do not connect automatically.</p>
  </div>
}
