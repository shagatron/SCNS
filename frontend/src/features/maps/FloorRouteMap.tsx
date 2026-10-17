import { useEffect, useState } from 'react'
import { CRS, divIcon } from 'leaflet'
import { iconMarkup } from '../public/placeSymbols'
import { CircleMarker, ImageOverlay, MapContainer, Marker, Polyline, Tooltip, useMap } from 'react-leaflet'
import type { components } from '../../api/generated'
import type { Place, Route } from '../../api/client'
import { pixelToMap } from '../admin/floorplanCoordinates'
import 'leaflet/dist/leaflet.css'
type Floor = components['schemas']['RouteFloor']
function Fit({ floor }: { floor: Floor }) {
  const map = useMap()
  useEffect(() => { const fit = () => { map.invalidateSize(); map.fitBounds([[0, 0], [floor.height_px, floor.width_px]], { padding: [20, 20], animate: false }) }; fit(); const observer = new ResizeObserver(() => map.invalidateSize({ pan: false })); observer.observe(map.getContainer()); return () => observer.disconnect() }, [map, floor])
  return <button className="map-fit" onClick={() => map.fitBounds([[0, 0], [floor.height_px, floor.width_px]], { padding: [20, 20], animate: false })}>Fit floor plan</button>
}
export default function FloorRouteMap({ floor, route, places, selectedId, onSelect }: { floor: Floor; route?: Route; places: Place[]; selectedId?: string; onSelect?: (place: Place) => void }) {
  const [failed, setFailed] = useState(false), [loaded, setLoaded] = useState(false), [attempt, setAttempt] = useState(0)
  const mapPoint = (p: number[]) => pixelToMap({ x: p[0], y: p[1] }, floor.height_px)
  const inBounds = (p: number[]) => p.length === 2 && p.every(Number.isFinite) && p[0] >= 0 && p[0] <= floor.width_px && p[1] >= 0 && p[1] <= floor.height_px
  const lines = route?.segments.filter(s => s.kind === 'indoor' && s.floor_id === floor.id && s.frame_id === floor.frame_id && s.polyline?.every(inBounds)) ?? []
  const transitions = route?.segments.flatMap(s => { if (['outdoor', 'indoor'].includes(s.kind)) return []; const p = s.floor_id === floor.id ? s.from_local_point : s.to_floor_id === floor.id ? s.to_local_point : null; return p && inBounds([p.x_px, p.y_px]) ? [{ s, p }] : [] }) ?? []
  return <section className="map-panel" aria-label="Indoor route map"><div className="map-caption">{floor.building_name} · {floor.label} · {floor.navigation_mode.replaceAll('_', ' ')}</div>
    <p role="status">{failed ? 'Approved floor image unavailable. Text directions remain usable.' : loaded ? `Reference ${floor.width_px} × ${floor.height_px}px · x right / y down` : 'Loading approved floor image…'}</p>{failed && <button onClick={() => { setAttempt(n => n + 1); setFailed(false); setLoaded(false) }}>Retry floor image</button>}
    <MapContainer key={`${floor.asset_url}:${attempt}`} crs={CRS.Simple} center={[floor.height_px / 2, floor.width_px / 2]} zoom={0} minZoom={-5} maxZoom={4} className="campus-map" scrollWheelZoom={false}>
      <ImageOverlay url={floor.asset_url} bounds={[[0, 0], [floor.height_px, floor.width_px]]} eventHandlers={{ load: () => setLoaded(true), error: () => setFailed(true) }} />
      {lines.map(s => <Polyline key={s.edge_id} positions={s.polyline!.map(mapPoint)} pathOptions={{ color: '#111110', weight: 6 }}><Tooltip>{s.instruction}</Tooltip></Polyline>)}
      {transitions.map(({ s, p }) => <CircleMarker key={s.edge_id} center={mapPoint([p.x_px, p.y_px])} radius={9} pathOptions={{ color: '#a24300' }}><Tooltip permanent>{s.kind === 'entrance_transition' ? 'Entrance' : s.kind} · floor transition</Tooltip></CircleMarker>)}
      {places.filter(p => p.floor_id === floor.id && p.frame_id === floor.frame_id && p.local_point && inBounds([p.local_point.x_px, p.local_point.y_px])).map(p => <Marker key={p.id} position={mapPoint([p.local_point!.x_px, p.local_point!.y_px])} title={`Select ${p.name}`} alt={p.name} keyboard icon={divIcon({ className: `scns-pin${selectedId === p.id ? ' selected-pin' : ''}`, html: iconMarkup(p.kind), iconSize: [36, 36], iconAnchor: [18, 18] })} eventHandlers={{ click: () => onSelect?.(p), keypress: e => { if ([' ', 'Enter'].includes(e.originalEvent.key)) { e.originalEvent.preventDefault(); onSelect?.(p) } } }}><Tooltip permanent={selectedId === p.id}>{p.room_code} · {p.name}</Tooltip></Marker>)}
      {route?.segments.slice(0, 1).filter(s => s.kind === 'indoor' && s.floor_id === floor.id && s.polyline?.length).map(s => <CircleMarker key={`start:${s.edge_id}`} center={mapPoint(s.polyline![0])} radius={10} pathOptions={{ color: '#111110', fillColor: '#e4fb02', fillOpacity: 1 }}><Tooltip permanent>Route start</Tooltip></CircleMarker>)}
      {route?.segments.slice(-1).filter(s => s.kind === 'indoor' && s.floor_id === floor.id && s.polyline?.length).map(s => <CircleMarker key={`end:${s.edge_id}`} center={mapPoint(s.polyline!.at(-1)!)} radius={10} pathOptions={{ color: '#111110', fillColor: '#fff', fillOpacity: 1 }}><Tooltip permanent>Route destination</Tooltip></CircleMarker>)}
      <Fit floor={floor} />
    </MapContainer><p className="map-source">{floor.attribution} · {floor.metres_per_pixel === null ? 'Scale unknown; no metric claim' : `${floor.metres_per_pixel}m/reference-pixel`}. Transition markers link floors; no line crosses coordinate frames.</p>
  </section>
}
