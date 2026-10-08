import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { components } from '../../api/generated'

type Observation = components['schemas']['GPSObservation']
type Match = components['schemas']['LocationMatch']
export type GPSStart = components['schemas']['GPSSource']
export default function OutdoorLocation({ campus, release, overlay, profile, ready, onConfirm, onInvalidate }: {
  campus: string; release: string; overlay: number; profile: 'shortest' | 'step_free' | 'fastest'; ready: boolean
  onConfirm: (source: GPSStart, expires: string) => void; onInvalidate: () => void
}) {
  const [pending, setPending] = useState(false), [error, setError] = useState('')
  const [value, setValue] = useState<{ observation: Observation; match: Match } | null>(null)
  const [selected, setSelected] = useState('')
  const generation = useRef(0)
  useEffect(() => () => { generation.current++ }, [])
  useEffect(() => {
    if (!value) return
    const invalidate = () => { generation.current++; setValue(null); setPending(false); onInvalidate(); setError('Location confirmation ended. Request a fresh fix or choose a manual/QR start.') }
    const timer = window.setTimeout(invalidate, Math.max(0, new Date(value.match.expires_at).getTime() - Date.now()))
    let disposed = false, permission: PermissionStatus | undefined
    if (navigator.permissions) void navigator.permissions.query({ name: 'geolocation' }).then(status => {
      if (disposed) return; permission = status
      status.onchange = () => { if (status.state === 'denied') invalidate() }
      if (status.state === 'denied') invalidate()
    }).catch(() => { /* The actual location request remains authoritative. */ })
    return () => { disposed = true; window.clearTimeout(timer); if (permission) permission.onchange = null }
  }, [value, onInvalidate])
  async function request() {
    const current = ++generation.current
    onInvalidate(); setValue(null); setError(''); setPending(true)
    if (!window.isSecureContext || !navigator.geolocation) { setError('Outdoor location is unavailable in this browser/context. Choose a manual/QR start.'); setPending(false); return }
    try {
      const policy = await api<components['schemas']['LocationPolicy']>('/location-policy', { cache: 'no-store' })
      if (generation.current !== current) return
      navigator.geolocation.getCurrentPosition(async position => {
        if (generation.current !== current) return
        try {
          const { latitude, longitude, accuracy } = position.coords, age = Date.now() - position.timestamp
          if (![latitude, longitude, accuracy, position.timestamp].every(Number.isFinite) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180 || accuracy <= 0) throw new Error('Invalid location from the browser. Choose a manual/QR start.')
          if (accuracy > policy.max_accuracy_m) throw new Error(`Accuracy ±${Math.round(accuracy)}m exceeds the ${policy.max_accuracy_m}m limit. Try again outdoors or choose a manual/QR start.`)
          if (age < -10000 || age > policy.max_age_seconds * 1000) throw new Error('Location is stale or the device clock is incorrect. Request a fresh fix.')
          const observation = { latitude, longitude, accuracy_m: accuracy, observed_at: new Date(position.timestamp).toISOString() }
          const match = await api<Match>('/outdoor-location-match', { method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ campus_id: campus, observation, profile, expected_release_id: release, expected_closure_overlay_version: overlay }) })
          if (generation.current !== current) return
          setValue({ observation, match }); setSelected(match.candidates[0].node_id)
        } catch (failure) { if (generation.current === current) setError(failure instanceof Error ? failure.message : 'Location unavailable. Choose a manual/QR start.') }
        finally { if (generation.current === current) setPending(false) }
      }, failure => {
        if (generation.current !== current) return
        setError(({ 1: 'Location permission denied.', 2: 'Location unavailable.', 3: 'Location request timed out.' } as Record<number, string>)[failure.code] + ' Choose a manual/QR start or try again.'); setPending(false)
      }, { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 })
    } catch (failure) { if (generation.current === current) { setError(failure instanceof Error ? failure.message : 'Location unavailable.'); setPending(false) } }
  }
  return <aside className="location-start" aria-label="Optional outdoor location">
    <button type="button" disabled={!ready || pending} onClick={() => void request()}>{pending ? 'Checking outdoor location…' : 'Use my location'}</button>
    <p className="muted">Optional outdoor fix. No indoor floor inference or continuous tracking. Manual and QR starts remain available.</p>
    {pending && <p role="status">Waiting for browser permission and a fresh location…</p>}
    {error && <p className="error-text" role="alert">{error}</p>}
    {value && <><p>Reported accuracy radius ±{value.match.accuracy_m}m; this is uncertainty, not proof of your position.</p>
      <label htmlFor="location-landmark">Confirm a labelled outdoor landmark</label><select id="location-landmark" value={selected} onChange={e => setSelected(e.target.value)}>{value.match.candidates.map(c => <option key={c.node_id} value={c.node_id}>{c.label} · approximately {Math.round(c.approach_distance_m)}m away</option>)}</select>
      <p>Only confirm if you are physically at this landmark. The straight-line approach is unverified and excluded from route distance/ETA. Do not cross walls or fences toward a suggestion.</p>
      <button type="button" disabled={!ready} onClick={() => onConfirm({ kind: 'gps', ...value.observation, confirmed: true, confirmed_node_id: selected }, value.match.expires_at)}>I am at this landmark now</button>
      <button type="button" onClick={() => { generation.current++; setValue(null); onInvalidate() }}>Discard location</button></>}
  </aside>
}
