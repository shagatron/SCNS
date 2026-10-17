import { useEffect, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import type { FeatureCollection } from 'geojson'
import { circleMarker, divIcon } from 'leaflet'
import type { Campus, MapData, Place, Route } from '../../api/client'
import { iconMarkup } from '../public/placeSymbols'
import { outdoorTransitions } from './routePresentation'
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
  return <section className="map-panel outdoor-panel" aria-label="Outdoor campus map">
    <div className="map-caption"><span className="status-dot" /> Outdoor map <span>{campus.is_demo ? 'Synthetic · not to scale on screen' : 'Published geometry'}</span></div>
    <MapContainer center={toLeaflet(campus.center.coordinates as [number, number])} zoom={17} minZoom={14} maxZoom={22}
      scrollWheelZoom={false} className="campus-map">
      {tileUrl && attribution && <TileLayer url={tileUrl} attribution={attribution} eventHandlers={{ tileerror: () => setTileFailed(true) }} />}
      <GeoJSON key={data.release_id} data={data as unknown as FeatureCollection} pointToLayer={(_feature, position) => circleMarker(position, { radius: 5, color: '#818c89', fillOpacity: 0.6 })} style={feature => feature?.properties.layer === 'building'
        ? { color: '#788780', fillColor: '#4b5751', fillOpacity: 0.8, weight: 1 }
        : feature?.properties.layer === 'overlay' ? { color: '#66726b', fillColor: '#3a4540', weight: 2, fillOpacity: 0.3 } : { color: feature?.properties.open ? '#7b8982' : '#e6a388', weight: 5, dashArray: feature?.properties.open ? undefined : '5 8' }} />
      {places.filter(place => place.point).map(place => <Marker key={place.id} position={toLeaflet(place.point!.coordinates as [number, number])}
        title={`Map destination: ${place.name}`} alt={place.name} keyboard={false}
        icon={divIcon({ className: `scns-pin kind-${place.kind}`, html: iconMarkup(place.kind), iconSize: [30, 30], iconAnchor: [15, 15] })}
        eventHandlers={{ click: () => onDestination(place) }}>
        <Tooltip direction="top" permanent className="place-label">{place.name}</Tooltip>
      </Marker>)}
      {route?.segments.filter(segment => segment.kind === 'outdoor' && segment.geometry).map(segment => <Polyline key={`halo:${segment.edge_id}`}
        positions={segment.geometry!.coordinates.map(p => toLeaflet(p as [number, number]))}
        pathOptions={{ color: '#91edc5', weight: 14, opacity: 0.16, interactive: false }} />)}
      {route?.segments.filter(segment => segment.kind === 'outdoor' && segment.geometry).map(segment => <Polyline key={segment.edge_id}
        positions={segment.geometry!.coordinates.map(p => toLeaflet(p as [number, number]))}
        pathOptions={{ color: '#9bf3ce', weight: 6, opacity: 1 }} />)}
      {start && <CircleMarker center={toLeaflet(start as [number, number])} radius={10} pathOptions={{ color: '#17211d', fillColor: '#9bf3ce', fillOpacity: 1, weight: 3 }}><Tooltip permanent direction="bottom">Route start</Tooltip></CircleMarker>}
      {end && <CircleMarker center={toLeaflet(end as [number, number])} radius={10} pathOptions={{ color: '#17211d', fillColor: '#fff', fillOpacity: 1, weight: 3 }}><Tooltip permanent direction="bottom">Route destination</Tooltip></CircleMarker>}
      {outdoorTransitions(route).map(t => <CircleMarker key={`transition:${t.id}`} center={toLeaflet(t.point as [number, number])} radius={9} pathOptions={{ color: '#17211b', fillColor: '#f0cb91', fillOpacity: 1, weight: 3 }}><Tooltip permanent direction="right">Entrance transition · {t.instruction}</Tooltip></CircleMarker>)}
      <FitView campus={campus} route={route} />
    </MapContainer>
    <div className="map-legend"><span>● Published place</span><span>━ Selected route</span><span>─ Mapped path</span><span>┄ Closed path</span><span>Mint: route start · White: destination</span></div>
    <p className="map-source">{campus.is_demo ? 'Original synthetic campus geometry · WGS84 coordinates near 0°, 0° · no real campus map' : 'Published outdoor geometry · WGS84 coordinates'}</p>
    {[...new Set(data.features.filter(f => f.properties.layer === 'overlay').map(f => String(f.properties.attribution)))].map(text => <p className="map-source" key={text}>{text}</p>)}
    {tileFailed && <p role="status" className="notice">Background tiles are unavailable. Campus paths and text directions remain usable.</p>}
  </section>
}
