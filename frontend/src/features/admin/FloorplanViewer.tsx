import { useEffect, useState } from 'react'
import { CRS } from 'leaflet'
import { CircleMarker, ImageOverlay, MapContainer, Polyline, useMap, useMapEvents } from 'react-leaflet'
import { mapToPixel, pixelToMap, type Pixel } from './floorplanCoordinates'
import 'leaflet/dist/leaflet.css'

type Props = { url: string; width: number; height: number; label: string; primary?: Pixel[]; check?: Pixel[]; picking?: string; onPick?: (point: Pixel) => void }
function Controls({ width, height, picking, onPick }: Pick<Props, 'width' | 'height' | 'picking' | 'onPick'>) {
  const map = useMap()
  useMapEvents({ click(event) { if (!picking || !onPick) return; try { onPick(mapToPixel(event.latlng.lat, event.latlng.lng, width, height)) } catch { /* Outside-image clicks do not become coordinates. */ } } })
  useEffect(() => {
    const fit = () => { map.invalidateSize(); map.fitBounds([[0, 0], [height, width]], { padding: [16, 16], animate: false }) }
    fit(); const observer = new ResizeObserver(fit); observer.observe(map.getContainer()); return () => observer.disconnect()
  }, [map, width, height])
  return <button type="button" className="map-fit" onClick={() => map.fitBounds([[0, 0], [height, width]], { padding: [16, 16], animate: false })}>Fit plan</button>
}
export default function FloorplanViewer({ url, width, height, label, primary, check, picking, onPick }: Props) {
  const [failed, setFailed] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const inBounds = (p: Pixel) => Number.isFinite(p.x) && Number.isFinite(p.y) && p.x >= 0 && p.y >= 0 && p.x <= width && p.y <= height
  return <section className="floorplan-preview" aria-label={label}>
    <p>{label} · reference {width} × {height}px · top-left origin, x right, y down. Zoom/pan uses floor-local pixels.</p>
    {!loaded && !failed && <p role="status">Loading private floorplan preview…</p>}
    {failed && <div role="alert"><p>Cannot load the private preview. Check your session/connection; your coordinates are retained.</p><button onClick={() => { setAttempt(value => value + 1); setFailed(false); setLoaded(false) }}>Retry floorplan preview</button></div>}
    <MapContainer key={`${url}:${attempt}`} crs={CRS.Simple} center={[height / 2, width / 2]} zoom={0} minZoom={-5} maxZoom={4} scrollWheelZoom className="floorplan-map">
      <ImageOverlay url={url} bounds={[[0, 0], [height, width]]} eventHandlers={{ load: () => setLoaded(true), error: () => setFailed(true) }} />
      {[primary, check].map((points, index) => points?.length === 2 && points.every(inBounds) && <Polyline key={index} positions={points.map(p => pixelToMap(p, height))} pathOptions={{ color: index === 0 ? '#125fa1' : '#7c3fa0', weight: 3 }} />)}
      {[...(primary ?? []), ...(check ?? [])].filter(inBounds).map((point, index) => <CircleMarker key={index} center={pixelToMap(point, height)} radius={5} pathOptions={{ color: '#125fa1' }} />)}
      <Controls width={width} height={height} picking={picking} onPick={onPick} />
    </MapContainer>
    {picking && <p role="status">Tap the reference plan to set {picking}. Numeric controls are also available.</p>}
  </section>
}
