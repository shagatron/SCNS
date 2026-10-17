import { useCallback, useEffect, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import type { FeatureCollection } from 'geojson'
import { circleMarker, divIcon } from 'leaflet'
import type { Campus, MapData, Place, Route } from '../../api/client'
import { iconMarkup } from '../public/PlaceIcon'
import { toLeaflet } from './coordinates'
import 'leaflet/dist/leaflet.css'

type Props = { campus: Campus; data: MapData; places: Place[]; route?: Route; selectedId?: string; onSelect: (place: Place) => void }

function FitView({ campus, route }: Pick<Props, 'campus' | 'route'>) {
  const map = useMap()
  const fit = useCallback(() => {
    const points = route?.segments.flatMap(segment => segment.kind === 'outdoor' && segment.geometry ? segment.geometry.coordinates : []) ?? []
    const bounds = points.length > 1 ? points : campus.boundary.coordinates[0]
    map.fitBounds(bounds.map(p => toLeaflet(p as [number, number])), { padding: [48, 48], maxZoom: 18, animate: false })
  }, [map, campus, route])
  useEffect(fit, [fit])
  useEffect(() => {
    // Resizing must preserve a user's pan/zoom; only new route/campus or Fit recentres.
    const observer = new ResizeObserver(() => map.invalidateSize({ pan: false }))
    observer.observe(map.getContainer())
    return () => observer.disconnect()
  }, [map])
  return <button className="map-fit" onClick={fit}>Fit {route ? 'route' : 'campus'}</button>
}

function PlacePins({ places, selectedId, onSelect }: Pick<Props, 'places' | 'selectedId' | 'onSelect'>) {
  const map = useMap()
  const [zoom, setZoom] = useState(map.getZoom())
  useMapEvents({ zoomend: () => setZoom(map.getZoom()) })
  // Hide overlapping unselected pins at campus scale; all places remain searchable.
  const occupied = new Set<string>()
  const pins = [...places].sort((a, b) => Number(b.id === selectedId) - Number(a.id === selectedId)).filter(place => {
    if (!place.point) return false
    const point = map.project(toLeaflet(place.point.coordinates as [number, number]), zoom)
    const cell = `${Math.round(point.x / 38)}:${Math.round(point.y / 38)}`
    if (occupied.has(cell) && place.id !== selectedId) return false
    occupied.add(cell); return true
  })
  return <>{pins.map(place => <Marker key={place.id} position={toLeaflet(place.point!.coordinates as [number, number])}
    title={`Select ${place.name}`} alt={place.name} keyboard
    zIndexOffset={place.id === selectedId ? 500 : 0}
    icon={divIcon({ className: `scns-pin kind-${place.kind}${place.id === selectedId ? ' selected-pin' : ''}`, html: iconMarkup(place.kind), iconSize: [36, 36], iconAnchor: [18, 18] })}
    eventHandlers={{ click: () => onSelect(place), keypress: e => { if (e.originalEvent.key === ' ') { e.originalEvent.preventDefault(); onSelect(place) } } }}>
    <Tooltip direction="top" permanent={place.id === selectedId} className="place-label">{place.name}</Tooltip>
  </Marker>)}</>
}

export default function OutdoorMap({ campus, data, places, route, selectedId, onSelect }: Props) {
  const [tileFailed, setTileFailed] = useState(false)
  const tileUrl = import.meta.env.VITE_BASEMAP_URL
  const attribution = import.meta.env.VITE_BASEMAP_ATTRIBUTION
  const first = route?.segments[0], last = route?.segments.at(-1)
  const start = first?.kind === 'outdoor' ? first.geometry?.coordinates[0] : undefined
  const end = last?.kind === 'outdoor' ? last.geometry?.coordinates.at(-1) : undefined
  const outdoor = route?.segments.filter(s => s.kind === 'outdoor' && s.geometry) ?? []
  const transitions = route?.segments.filter(s => s.kind === 'entrance_transition' && s.geometry) ?? []
  return <section className="map-panel outdoor-panel" aria-label="Outdoor campus map">
    <div className="map-caption"><span className="status-dot" /> Outdoor map <span>{campus.is_demo ? 'Synthetic · not a real campus' : 'Published geometry'}</span></div>
    <MapContainer center={toLeaflet(campus.center.coordinates as [number, number])} zoom={17} minZoom={14} maxZoom={22}
      scrollWheelZoom={false} className="campus-map">
      {tileUrl && attribution && <TileLayer url={tileUrl} attribution={attribution} eventHandlers={{ tileerror: () => setTileFailed(true) }} />}
      <GeoJSON key={data.release_id} data={data as unknown as FeatureCollection} pointToLayer={(_feature, position) => circleMarker(position, { radius: 3, color: '#818c89', fillOpacity: 0.6 })} style={feature => feature?.properties.layer === 'building'
        ? { color: '#788780', fillColor: '#4b5751', fillOpacity: 0.8, weight: 1 }
        : feature?.properties.layer === 'overlay' ? { color: '#66726b', fillColor: '#3a4540', weight: 1.5, fillOpacity: 0.3 } : { color: feature?.properties.open ? '#7b8982' : '#e6a388', weight: 3, opacity: 0.7, dashArray: feature?.properties.open ? undefined : '5 8' }} />
      <PlacePins places={places} selectedId={selectedId} onSelect={onSelect} />
      {outdoor.map(segment => <Polyline key={`halo:${segment.edge_id}`} positions={segment.geometry!.coordinates.map(p => toLeaflet(p as [number, number]))} pathOptions={{ color: '#91edc5', weight: 14, opacity: 0.16, interactive: false }} />)}
      {outdoor.map(segment => <Polyline key={segment.edge_id} positions={segment.geometry!.coordinates.map(p => toLeaflet(p as [number, number]))} pathOptions={{ color: '#9bf3ce', weight: 6, opacity: 1 }}><Tooltip>{segment.instruction}</Tooltip></Polyline>)}
      {transitions.map(s => <Polyline key={s.edge_id} positions={s.geometry!.coordinates.map(p => toLeaflet(p as [number, number]))} pathOptions={{ color: '#f0cb91', weight: 5, dashArray: '3 7' }}><Tooltip>Entrance transition · {s.instruction}</Tooltip></Polyline>)}
      {start && <CircleMarker center={toLeaflet(start as [number, number])} radius={10} pathOptions={{ color: '#17211d', fillColor: '#9bf3ce', fillOpacity: 1, weight: 3 }}><Tooltip permanent direction="bottom">Route start</Tooltip></CircleMarker>}
      {end && <CircleMarker center={toLeaflet(end as [number, number])} radius={10} pathOptions={{ color: '#17211d', fillColor: '#fff', fillOpacity: 1, weight: 3 }}><Tooltip permanent direction="bottom">Route destination</Tooltip></CircleMarker>}
      <FitView campus={campus} route={route} />
    </MapContainer>
    <div className="map-legend"><span>◉ Category place</span><span>━ Selected route</span><span>─ Published path</span><span>┄ Closed / transition</span></div>
    <p className="map-source">{campus.is_demo ? 'Original synthetic campus geometry · WGS84 coordinates near 0°, 0° · no real campus map' : 'Published outdoor geometry · WGS84 coordinates'}. Context lines do not guarantee a routable connection. Nearby pins may be hidden at this zoom; search to select any published place.</p>
    {!data.features.some(f => f.properties.layer === 'building') && <p className="map-source">No published building footprints available in this view.</p>}
    {data.truncated && <p className="map-source">Map coverage is incomplete; not every published feature is displayed.</p>}
    {[...new Set(data.features.filter(f => f.properties.layer === 'overlay').map(f => String(f.properties.attribution)))].map(text => <p className="map-source" key={text}>{text}</p>)}
    {tileFailed && <p role="status" className="notice">Background tiles are unavailable. Campus paths and text directions remain usable.</p>}
  </section>
}
