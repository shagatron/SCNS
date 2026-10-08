import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { components } from '../../api/generated'
import { ApiError } from '../../api/client'
import { adminApi, type Session } from './api'
import { ErrorMessage } from './AdminApp'

type Input = components['schemas']['MarkerInput']
type Install = components['schemas']['Installation']
type Marker = Input & { id: string; version: number; state: string; installation: Partial<Install> & { verified_by?: string; revocation_reason?: string } }
type Inventory = { release_id: string; canonical_origin: string; items: Marker[]; targets: { id: string; kind: 'outdoor' | 'indoor'; label: string; floor_label: string | null }[]; targets_truncated: boolean }
const empty: Input = { label: '', node_kind: 'outdoor', node_id: '', intended_position: '' }
const blankInstall: Install = { installer: '', actual_position: '', installed_on: '', verified_on: '', evidence: '' }

export function QRInventory({ path, session, editable }: { path: string; session: Session; editable: boolean }) {
  const endpoint = `${path}/qr-markers`
  const inventory = useQuery({ queryKey: ['admin', path, 'qr'], queryFn: () => adminApi<Inventory>(endpoint), retry: false })
  const [selected, setSelected] = useState<Marker | null>(null)
  const [input, setInput] = useState<Input>(empty)
  const [installation, setInstallation] = useState<Install>(blankInstall)
  const [key, setKey] = useState(() => crypto.randomUUID())
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [saved, setSaved] = useState('')
  const [reconciled, setReconciled] = useState(false)
  const data = inventory.data
  const unsaved = selected ? Object.entries(input).some(([field, value]) => selected[field as keyof Input] !== value) : !!(input.label || input.node_id || input.intended_position)
  const latest = data?.items.find(item => item.id === selected?.id)
  function open(marker: Marker | null) {
    setSelected(marker); setInput(marker ? { label: marker.label, node_kind: marker.node_kind, node_id: marker.node_id, intended_position: marker.intended_position } : empty)
    setInstallation(blankInstall); setReason(''); setKey(crypto.randomUUID()); setError(null); setSaved(''); setReconciled(false)
  }
  async function write(action: 'save' | 'activate' | 'revoke') {
    setBusy(true); setError(null); setSaved('')
    try {
      const body = action === 'save' ? selected ? input : { ...input, key } : action === 'activate' ? installation : { reason }
      const result = await adminApi<Marker>(`${endpoint}${selected ? `/${selected.id}${action === 'save' ? '' : `/${action}`}` : ''}`, { method: action === 'save' && selected ? 'PUT' : 'POST', body, csrf: session.csrf_token, version: selected?.version })
      if (action === 'save') { setInstallation(blankInstall); setReason('') }
      setSelected(result); setReconciled(false); setSaved(action === 'save' ? 'Marker saved as planned. Verify its installation before activating.' : action === 'activate' ? 'Installation recorded and marker activated.' : 'Marker revoked. Existing printed links cannot start routes.')
      await inventory.refetch()
    } catch (e) { setError(e); if (e instanceof ApiError && e.code === 'conflict') await inventory.refetch() }
    finally { setBusy(false) }
  }
  if (inventory.isPending) return <p role="status">Loading QR inventory…</p>
  if (!data) return <><ErrorMessage error={inventory.error} /><button onClick={() => void inventory.refetch()}>Retry QR inventory</button></>
  return <section className="admin-card"><h2>QR markers and printable signs</h2><p>Operational inventory uses published public nodes, never drafts. Moving or relabelling a sign requires explicit installation re-verification. This is a fixed confirmed start, not continuous indoor positioning.</p><p>Canonical origin: <strong>{data.canonical_origin}</strong>. Check the readable domain before scanning. Local HTTP links are for this computer’s demo only.</p>
    <button disabled={busy} onClick={() => void inventory.refetch()}>Refresh inventory</button>{editable && <button disabled={busy} onClick={() => open(null)}>New marker</button>}
    <ErrorMessage error={inventory.error} />{data.items.length === 0 && <p>No QR markers yet. Create a clearly labelled synthetic sign for a published node.</p>}
    <div className="qr-inventory">{data.items.map(marker => <button key={marker.id} disabled={busy} aria-pressed={selected?.id === marker.id} onClick={() => open(marker)}>{marker.label} · {marker.state.replaceAll('_', ' ')} · v{marker.version}</button>)}</div>
    {data.targets_truncated && <p role="alert">Target inventory exceeds 5,000 nodes. Only the first 5,000 are shown; contact the system administrator before planning further signs.</p>}
    {(editable || selected) && <>
      <h3>{selected ? `${selected.label} · ${selected.state.replaceAll('_', ' ')} · version ${selected.version}` : 'Create a planned marker'}</h3>
      {selected && <><p className="admin-id">Stable link: <a href={`/q/${selected.id}`} target="_blank" rel="noreferrer">{data.canonical_origin}/q/{selected.id}</a></p><p>Saving changes clears installation verification; revoked or retired signs require deliberate replanning.</p>
        <img className="qr-sign-preview" alt={`Printable QR sign for ${selected.label}`} src={`/api/v1/admin${endpoint}/${selected.id}/sign.svg?v=${latest?.version ?? selected.version}`} />
        <div className="admin-actions">{['svg', 'png', 'pdf'].map(format => <a key={format} href={`/api/v1/admin${endpoint}/${selected.id}/sign.${format}`} download>Download {format.toUpperCase()} sign</a>)}</div>
        {Object.keys(selected.installation).length > 0 && <details><summary>Recorded installation and revocation</summary><dl>{Object.entries(selected.installation).map(([field, value]) => <div key={field}><dt>{field.replaceAll('_', ' ')}</dt><dd>{String(value)}</dd></div>)}</dl></details>}
      </>}
      <ErrorMessage error={error} />{saved && <p role="status">{saved}</p>}
      {latest && selected && latest.version !== selected.version && <aside className="admin-notice"><p>Marker changed on the server. Your unsaved inputs are retained. Current server version: {latest.version} · {latest.label} · {latest.state} · target {latest.node_id}.</p><p>Server intended position: {latest.intended_position}</p><button disabled={busy} onClick={() => { setSelected(latest); setReconciled(true); setError(null) }}>Use latest version and keep my inputs</button><button disabled={busy} onClick={() => open(latest)}>Discard my inputs and load latest</button></aside>}
      {reconciled && <p role="status">Latest version accepted. Review retained inputs before saving or verifying.</p>}
      {unsaved && <p role="status" className="notice">Unsaved marker fields. Saving replans the sign and clears installation verification.</p>}
      <form onSubmit={e => { e.preventDefault(); void write('save') }}><fieldset disabled={!editable || busy}>
        <label>Sign label<input value={input.label} required maxLength={160} onChange={e => setInput({ ...input, label: e.target.value })} /></label>
        <label>Published target node<select required value={`${input.node_kind}:${input.node_id}`} onChange={e => { const [kind, id] = e.target.value.split(':'); setInput({ ...input, node_kind: kind as Input['node_kind'], node_id: id }) }}><option value={`${input.node_kind}:`}>Choose a published node</option>{data.targets.map(t => <option key={`${t.kind}:${t.id}`} value={`${t.kind}:${t.id}`}>{t.kind} · {t.label}{t.floor_label ? ` · ${t.floor_label}` : ''}</option>)}</select></label>
        <label>Intended installation position<textarea required minLength={10} maxLength={2000} value={input.intended_position} onChange={e => setInput({ ...input, intended_position: e.target.value })} /></label>
        {editable && <button disabled={busy || !!(latest && selected && latest.version !== selected.version)}>{busy ? 'Saving…' : selected ? 'Save changes and replan' : 'Create planned marker'}</button>}
      </fieldset></form>
      {selected && editable && <>
        <h3>Verify installation and activate</h3><p>Record the actual position, installer, dates and evidence. Verification does not certify accessibility. For synthetic signs, say explicitly that the installation is simulated.</p>
        <form onSubmit={e => { e.preventDefault(); void write('activate') }}><fieldset disabled={busy || !['planned', 'needs_verification'].includes(selected.state) || !!(latest && latest.version !== selected.version)}>
          <label>Installer<input required maxLength={160} value={installation.installer} onChange={e => setInstallation({ ...installation, installer: e.target.value })} /></label>
          <label>Actual installed position<textarea required minLength={10} maxLength={2000} value={installation.actual_position} onChange={e => setInstallation({ ...installation, actual_position: e.target.value })} /></label>
          <label>Installation date<input type="date" required value={installation.installed_on} onChange={e => setInstallation({ ...installation, installed_on: e.target.value })} /></label>
          <label>Verification date<input type="date" required value={installation.verified_on} onChange={e => setInstallation({ ...installation, verified_on: e.target.value })} /></label>
          <label>Verification evidence<textarea required minLength={10} maxLength={2000} value={installation.evidence} onChange={e => setInstallation({ ...installation, evidence: e.target.value })} /></label>
          <button>Record verification and activate</button>
        </fieldset></form>
        <form onSubmit={e => { e.preventDefault(); void write('revoke') }}><fieldset disabled={busy || selected.state === 'revoked' || !!(latest && latest.version !== selected.version)}><label>Revocation reason<textarea required minLength={10} maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></label><button>Revoke marker</button></fieldset></form>
      </>}
    </>}
  </section>
}
