import { useEffect, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import type { FeatureCollection } from 'geojson'
import { circleMarker } from 'leaflet'
import type { Campus, MapData, Place, Route } from '../../api/client'
import { toLeaflet } from './coordinates'
import 'leaflet/dist/leaflet.css'

type Props = { campus: Campus; data: MapData; places: Place[]; route?: Route; onDestination: (place: Place) => void }

function FitView({ campus, route }: Pick<Props, 'campus' | 'route'>) {
  const map = useMap()
  const fit = () => {
    const points = route?.segments.flatMap(segment => segment.kind === 'outdoor' && segment.geometry ? segment.geometry.coordinates : []) ?? []
    const bounds = points.length > 1 ? points : campus.boundary.coordinates[0]
    map.fitBounds(bounds.map(p => toLeaflet(p as [number, number])), { padding: [28, 28], maxZoom: 18, animate: false })
  }
  useEffect(() => {
    const points = route?.segments.flatMap(segment => segment.kind === 'outdoor' && segment.geometry ? segment.geometry.coordinates : []) ?? []
    const bounds = points.length > 1 ? points : campus.boundary.coordinates[0]
    map.fitBounds(bounds.map(p => toLeaflet(p as [number, number])), { padding: [28, 28], maxZoom: 18, animate: false })
    const observer = new ResizeObserver(() => {
      map.invalidateSize()
      map.fitBounds(bounds.map(p => toLeaflet(p as [number, number])), { padding: [28, 28], maxZoom: 18, animate: false })
    })
    observer.observe(map.getContainer())
    return () => observer.disconnect()
  }, [map, campus, route])
  return <button className="map-fit" onClick={fit}>Fit {route ? 'route' : 'campus'}</button>
}

export default function OutdoorMap({ campus, data, places, route, onDestination }: Props) {
  const [tileFailed, setTileFailed] = useState(false)
  const tileUrl = import.meta.env.VITE_BASEMAP_URL
  const attribution = import.meta.env.VITE_BASEMAP_ATTRIBUTION
  const first = route?.segments[0], last = route?.segments.at(-1)
  const start = first?.kind === 'outdoor' ? first.geometry?.coordinates[0] : undefined
  const end = last?.kind === 'outdoor' ? last.geometry?.coordinates.at(-1) : undefined
  return <section className="map-panel" aria-label="Outdoor campus map">
    <div className="map-caption"><span className="status-dot" /> Outdoor map <span>{campus.is_demo ? 'Synthetic · not to scale on screen' : 'Published geometry'}</span></div>
    <MapContainer center={toLeaflet(campus.center.coordinates as [number, number])} zoom={17} minZoom={14} maxZoom={22}
      scrollWheelZoom={false} className="campus-map">
      {tileUrl && attribution && <TileLayer url={tileUrl} attribution={attribution} eventHandlers={{ tileerror: () => setTileFailed(true) }} />}
      <GeoJSON key={data.release_id} data={data as unknown as FeatureCollection} pointToLayer={(_feature, position) => circleMarker(position, { radius: 5, color: '#64728a', fillOpacity: 0.6 })} style={feature => feature?.properties.layer === 'building'
        ? { color: '#9c9c8c', fillColor: '#d8d8ca', fillOpacity: 1, weight: 1 }
        : feature?.properties.layer === 'overlay' ? { color: '#64728a', weight: 2, fillOpacity: 0.15 } : { color: feature?.properties.open ? '#b0b09e' : '#9d5951', weight: 5, dashArray: feature?.properties.open ? undefined : '5 8' }} />
      {places.filter(place => place.point).map(place => <CircleMarker key={place.id} center={toLeaflet(place.point!.coordinates as [number, number])} radius={6}
        pathOptions={{ color: '#153e35', fillColor: '#ffffff', fillOpacity: 1, weight: 2 }}
        eventHandlers={{ click: () => onDestination(place) }}>
        <Tooltip direction="top" permanent className="place-label">{place.name}</Tooltip>
      </CircleMarker>)}
      {route?.segments.filter(segment => segment.kind === 'outdoor' && segment.geometry).map(segment => <Polyline key={segment.edge_id}
        positions={segment.geometry!.coordinates.map(p => toLeaflet(p as [number, number]))}
        pathOptions={{ color: '#111110', weight: 6, opacity: 1 }} />)}
      {start && <CircleMarker center={toLeaflet(start as [number, number])} radius={10} pathOptions={{ color: '#111110', fillColor: '#e4fb02', fillOpacity: 1, weight: 3 }}><Tooltip permanent direction="bottom">Route start</Tooltip></CircleMarker>}
      {end && <CircleMarker center={toLeaflet(end as [number, number])} radius={10} pathOptions={{ color: '#111110', fillColor: '#fff', fillOpacity: 1, weight: 3 }}><Tooltip permanent direction="bottom">Route destination</Tooltip></CircleMarker>}
      <FitView campus={campus} route={route} />
    </MapContainer>
    <div className="map-legend"><span>● Published place</span><span>━ Selected route</span><span>─ Mapped path</span><span>┄ Closed path</span><span>Yellow: route start · White: destination</span></div>
    <p className="map-source">{campus.is_demo ? 'Original synthetic campus geometry · WGS84 coordinates near 0°, 0° · no real campus map' : 'Published outdoor geometry · WGS84 coordinates'}</p>
    {[...new Set(data.features.filter(f => f.properties.layer === 'overlay').map(f => String(f.properties.attribution)))].map(text => <p className="map-source" key={text}>{text}</p>)}
    {tileFailed && <p role="status" className="notice">Background tiles are unavailable. Campus paths and text directions remain usable.</p>}
  </section>
}
