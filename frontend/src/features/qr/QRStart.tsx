import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { components } from '../../api/generated'
import App from '../../app/App'

type Marker = components['schemas']['MarkerResolution']
export type ConfirmedQR = Marker & { state: 'active'; label: string; node_label: string }

export default function QRStart() {
  const id = window.location.pathname.slice(3)
  const marker = useQuery({ queryKey: ['qr', id], queryFn: () => api<Marker>(`/qr/${encodeURIComponent(id)}`, { cache: 'no-store' }), retry: false, staleTime: 0, refetchInterval: 15000, refetchOnWindowFocus: true })
  const { refetch } = marker
  const [confirmation, setConfirmation] = useState('')
  useEffect(() => {
    const refresh = () => { setConfirmation(''); void refetch() }
    window.addEventListener('qr-marker-stale', refresh)
    window.addEventListener('campus-release-stale', refresh)
    window.addEventListener('offline', refresh)
    return () => { window.removeEventListener('qr-marker-stale', refresh); window.removeEventListener('campus-release-stale', refresh); window.removeEventListener('offline', refresh) }
  }, [refetch])
  const value = marker.data
  const receipt = value ? `${value.version}:${value.release_id}` : ''
  const active = value?.state === 'active' && value.label && value.node_label && !marker.error
  if (active && confirmation === receipt) return <><aside className="notice" role="status">QR start confirmed: {value.label}. This is a fixed marker, not continuous tracking. <button onClick={() => setConfirmation('')}>Confirm location again</button> <a href="/">Choose a manual start</a></aside><App key={receipt} qrStart={value as ConfirmedQR} /></>
  return <main className="qr-landing"><a href="/">← Choose a manual start</a><h1>Start from a QR marker</h1>
    {marker.isPending && <p role="status">Checking the current marker and published map…</p>}
    {marker.error && <div role="alert" className="error-box"><p>{marker.error.message}</p><p>A connection is required to verify this marker. Previous confirmation is not reused.</p></div>}
    {value && !marker.error && <><p className="demo-banner">{value.is_demo ? 'Synthetic demo: invented locations, not real-world navigation.' : 'Check the readable domain and physical location label on the sign.'}</p><p>{value.message}</p>
      {active && <><h2>{value.label}</h2><p>Published node: {value.node_label}{value.floor_label ? ` · ${value.floor_label}` : ''}</p><p>Installation verified: {value.verified_on}</p><button className="primary-button" disabled={marker.isFetching || !navigator.onLine} onClick={() => setConfirmation(receipt)}>I am at this marker now</button></>}
      {!active && <p role="status">Marker status: {value.state.replaceAll('_', ' ')}. It cannot start a route.</p>}
    </>}
    <p>Scanning opens this label. It does not establish your position until you confirm. Reloading requires a fresh confirmation.</p><button disabled={marker.isFetching} onClick={() => { setConfirmation(''); void refetch() }}>Check marker again</button>
  </main>
}
