import { useEffect, useMemo } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Polyline, Tooltip, useMapEvents } from 'react-leaflet'
import type { GeoJsonObject } from 'geojson'
import { DomEvent } from 'leaflet'
import { toLeaflet } from '../maps/coordinates'
import type { Graph, Layer, Position } from './graphState'
import 'leaflet/dist/leaflet.css'

function Controls({ graph, click }: { graph: Graph; click: (point: Position) => void }) {
  const boundaryKey = JSON.stringify(graph.campus.boundary.coordinates[0])
  const bounds = useMemo(() => JSON.parse(boundaryKey) as Position[], [boundaryKey])
  const map = useMapEvents({ click: e => click([e.latlng.lng, e.latlng.lat]) })
  useEffect(() => {
    map.fitBounds(bounds.map(toLeaflet), { padding: [20, 20], animate: false })
    const observer = new ResizeObserver(() => map.invalidateSize())
    observer.observe(map.getContainer()); return () => observer.disconnect()
  }, [map, bounds])
  return <button className="map-fit" onClick={e => { e.stopPropagation(); map.fitBounds(bounds.map(toLeaflet), { padding: [20, 20], animate: false }) }}>Fit draft campus</button>
}
export default function GraphMap({ graph, selected, select, click, vertex, route }: { graph: Graph; selected: { layer: Layer; id: string } | null; select: (layer: Layer, id: string) => void; click: (point: Position) => void; vertex: (n: number) => void; route: string[] }) {
  const first = graph.campus.boundary.coordinates[0][0]
  return <section aria-label="Visual outdoor draft graph" className="graph-map-panel"><MapContainer className="graph-map" center={toLeaflet(first)} zoom={17} minZoom={12} maxZoom={24} scrollWheelZoom={false}>
    <GeoJSON data={graph.campus.boundary as GeoJsonObject} style={{ color: '#728878', weight: 2, fillOpacity: 0.06 }} />
    {Object.entries(graph.edges).map(([id, edge]) => <Polyline key={id} positions={edge.geometry.coordinates.map(p => toLeaflet(p as Position))} pathOptions={{ color: route.includes(id) ? '#803fb4' : selected?.layer === 'edges' && graph.edges[selected.id]?.physical_path_id === edge.physical_path_id ? '#126e58' : edge.is_open ? '#627d8d' : '#a13636', weight: selected?.id === id ? 7 : 4, dashArray: edge.visibility === 'restricted' ? '6 6' : undefined }} eventHandlers={{ click: e => { DomEvent.stopPropagation(e.originalEvent); select('edges', id) } }}><Tooltip>{graph.nodes[edge.from_node_id]?.label} → {graph.nodes[edge.to_node_id]?.label} · {edge.accessibility_status} · {edge.is_open ? 'open in draft' : 'closed in draft'}</Tooltip></Polyline>)}
    {Object.entries(graph.places).map(([id, place]) => <CircleMarker key={id} center={toLeaflet(place.point.coordinates)} radius={3} pathOptions={{ color: '#815126', fillOpacity: 1 }}><Tooltip>{place.name} · Place</Tooltip></CircleMarker>)}
    {Object.entries(graph.anchors).map(([id, anchor]) => graph.nodes[anchor.node_id]?.point && <CircleMarker key={id} center={toLeaflet(graph.nodes[anchor.node_id].point.coordinates as Position)} radius={11} pathOptions={{ color: '#a16d21', fillOpacity: 0, weight: 2 }} eventHandlers={{ click: e => { DomEvent.stopPropagation(e.originalEvent); select('anchors', id) } }}><Tooltip>Entrance: {graph.places[anchor.place_id]?.name} · {anchor.accessibility_status}</Tooltip></CircleMarker>)}
    {Object.entries(graph.nodes).filter(([, node]) => node.point).map(([id, node]) => <CircleMarker key={id} center={toLeaflet(node.point.coordinates as Position)} radius={selected?.id === id ? 8 : 5} pathOptions={{ color: node.visibility === 'restricted' ? '#8d3141' : '#153e35', fillColor: '#fff', fillOpacity: 1, weight: 2 }} eventHandlers={{ click: e => { DomEvent.stopPropagation(e.originalEvent); select('nodes', id) } }}><Tooltip>{node.label} · Node · {node.visibility}</Tooltip></CircleMarker>)}
    {selected?.layer === 'edges' && graph.edges[selected.id]?.geometry.coordinates.map((p, n) => <CircleMarker key={`vertex-${n}`} center={toLeaflet(p as Position)} radius={4} pathOptions={{ color: '#1434aa', fillColor: '#fff', fillOpacity: 1 }} eventHandlers={{ click: e => { DomEvent.stopPropagation(e.originalEvent); vertex(n) } }}><Tooltip>Vertex {n + 1}</Tooltip></CircleMarker>)}
    <Controls graph={graph} click={click} />
  </MapContainer><p>● Node · brown ring: entrance anchor · line: stored directed path · dashed: restricted · purple: draft test route. Select a feature on the map or in the lists.</p></section>
}
