import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import type { components } from '../../api/generated'
import { adminApi, type Session } from './api'
import { ErrorMessage } from './AdminApp'

type TargetKind = components['schemas']['ClosureCreate']['target_kind']
type Target = { id: string; kind: TargetKind; label: string }
type Entry = { id: string; target_kind: TargetKind; target_id: string; label: string; reason: string; starts_at: string; estimated_end_at: string | null; state: 'closed' | 'unresolved' | 'reopened'; reopen_evidence: string | null }
type Inventory = { release_id: string; closure_overlay_version: number; items: Entry[]; targets: Target[]; targets_truncated: boolean }
const localNow = () => { const d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16) }
export function Closures({ path, session, editable }: { path: string; session: Session; editable: boolean }) {
  const endpoint = `${path}/closures`
  const inventory = useQuery({ queryKey: ['admin', path, 'closures'], queryFn: () => adminApi<Inventory>(endpoint), retry: false })
  const [selected, setSelected] = useState<Entry | null>(null)
  const [captured, setCaptured] = useState<number | null>(null)
  const [target, setTarget] = useState('')
  const [reason, setReason] = useState('')
  const [starts, setStarts] = useState(localNow)
  const [ends, setEnds] = useState('')
  const [evidence, setEvidence] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [key, setKey] = useState(() => crypto.randomUUID())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [saved, setSaved] = useState('')
  const [uncertain, setUncertain] = useState(false)
  const [lastAction, setLastAction] = useState<'create' | 'reopen' | 'rebind'>('create')
  const data = inventory.data
  const version = captured ?? data?.closure_overlay_version ?? 0
  const stale = !!data && version !== data.closure_overlay_version
  function open(item: Entry | null) {
    setSelected(item); setCaptured(data?.closure_overlay_version ?? 0); setTarget(item ? `${item.target_kind}:${item.target_id}` : ''); setReason(''); setStarts(localNow()); setEnds(''); setEvidence(''); setConfirmed(false); setKey(crypto.randomUUID()); setError(null); setSaved(''); setUncertain(false)
  }
  function changed() { if (captured === null) setCaptured(data?.closure_overlay_version ?? 0); setKey(crypto.randomUUID()); setUncertain(false); setSaved('') }
  async function write(action: 'create' | 'reopen' | 'rebind') {
    setLastAction(action); setBusy(true); setError(null); setSaved('')
    try {
      const [kind, id] = target.split(':')
      const decision = { key, evidence, confirmed }
      const body = action === 'create' ? { key, target_kind: kind, target_id: id, reason, starts_at: new Date(starts).toISOString(), estimated_end_at: ends ? new Date(ends).toISOString() : null, reopening_policy: 'operator_verified' } : action === 'rebind' ? { ...decision, target_kind: kind, target_id: id } : decision
      await adminApi(`${endpoint}${selected ? `/${selected.id}/${action}` : ''}`, { method: 'POST', body, csrf: session.csrf_token, version, headers: { 'If-Match': `"${version}"` } })
      setUncertain(false); setCaptured(null); setSelected(null); setTarget(''); setReason(''); setEvidence(''); setConfirmed(false); setKey(crypto.randomUUID()); setSaved(action === 'create' ? 'Restriction recorded. Routes use the live overlay; drafts were not published.' : action === 'rebind' ? 'Target reconciled. Restriction remains closed.' : 'Operator-verified reopening recorded. Other restrictions remain in force.')
      await inventory.refetch()
    } catch (e) { setError(e); if (e instanceof ApiError && e.code === 'conflict') await inventory.refetch(); if (e instanceof ApiError && e.code === 'network_error') setUncertain(true) }
    finally { setBusy(false) }
  }
  if (inventory.isPending) return <p role="status">Loading operational restrictions…</p>
  if (!data) return <><ErrorMessage error={inventory.error} /><button onClick={() => void inventory.refetch()}>Retry restrictions</button></>
  return <section className="admin-card"><h2>Closures and lift outages</h2><p>Live overlay v{data.closure_overlay_version} uses published paths, independently of drafts. Estimated end dates never reopen a path or repair a lift. Reopening needs explicit operator verification. Synthetic data is software evidence only.</p>
    <button disabled={busy} onClick={() => void inventory.refetch()}>Refresh restrictions</button>{editable && <button disabled={busy || uncertain} onClick={() => open(null)}>New restriction</button>}
    <ErrorMessage error={inventory.error} /><ErrorMessage error={error} />{saved && <p role="status">{saved}</p>}
    {uncertain && <><p role="alert">Response uncertain. Retry the unchanged request using the same key; check history before editing fields or starting another operation.</p><button disabled={busy} onClick={() => void write(lastAction)}>Retry unchanged operation</button></>}
    {!data.items.length && <p>No operational restrictions recorded.</p>}
    <div className="qr-inventory">{data.items.map(item => <button key={item.id} disabled={busy || uncertain} aria-pressed={selected?.id === item.id} onClick={() => open(item)}>{item.label} · {item.state}</button>)}</div>
    {selected && <><h3>{selected.label} · {selected.state}</h3><p>{selected.reason}</p><p>Starts {new Date(selected.starts_at).toLocaleString()}. Estimated end {selected.estimated_end_at ? new Date(selected.estimated_end_at).toLocaleString() : 'unknown'}; operator verification required.</p>{selected.reopen_evidence && <p>Reopening evidence: {selected.reopen_evidence}</p>}{selected.state === 'unresolved' && <p role="alert">Target changed or disappeared during publication/rollback. Routing fails safely until an operator rebinds this restriction or explicitly resolves the incident. Restoring a map never automatically resolves it.</p>}</>}
    {stale && <aside className="admin-notice"><p>Restrictions changed. Your input is retained. Form overlay v{version}; server v{data.closure_overlay_version}. Compare the history before proceeding.</p><button disabled={busy} onClick={() => { setCaptured(data.closure_overlay_version); setError(null) }}>Use latest overlay and keep my inputs</button><button disabled={busy || uncertain} onClick={() => open(selected ? data.items.find(i => i.id === selected.id) ?? null : null)}>Discard my inputs and load latest</button></aside>}
    {editable && selected?.state !== 'reopened' && <>
      {data.targets_truncated && <p role="alert">Only the first 5,000 published targets are shown. Contact the administrator if yours is missing.</p>}
      <form onSubmit={e => { e.preventDefault(); void write(selected ? 'rebind' : 'create') }}><fieldset disabled={busy || stale || uncertain}>
        <label>Published restriction target<select required value={target} onChange={e => { changed(); setTarget(e.target.value) }}><option value="">Choose a published path or connector</option>{data.targets.map(t => <option key={`${t.kind}:${t.id}`} value={`${t.kind}:${t.id}`}>{t.kind} · {t.label}</option>)}</select></label>
        {!selected && <><label>Public restriction reason<textarea required minLength={10} maxLength={1000} value={reason} onChange={e => { changed(); setReason(e.target.value) }} /></label><label>Restriction start (your device local time)<input required type="datetime-local" value={starts} onChange={e => { changed(); setStarts(e.target.value) }} /></label><label>Estimated end (informational only)<input type="datetime-local" value={ends} onChange={e => { changed(); setEnds(e.target.value) }} /></label><button>Record restriction</button></>}
        {selected && <><label>Target reconciliation evidence<textarea required minLength={10} maxLength={2000} value={evidence} onChange={e => { changed(); setEvidence(e.target.value) }} /></label><label><input required type="checkbox" checked={confirmed} onChange={e => { changed(); setConfirmed(e.target.checked) }} />I confirm this physical target and keep the restriction closed</label><button>Reconcile target and keep closed</button></>}
      </fieldset></form>
      {selected && <form onSubmit={e => { e.preventDefault(); void write('reopen') }}><fieldset disabled={busy || stale || uncertain}><label>Reopening verification evidence<textarea required minLength={10} maxLength={2000} value={evidence} onChange={e => { changed(); setEvidence(e.target.value) }} /></label><label><input required type="checkbox" checked={confirmed} onChange={e => { changed(); setConfirmed(e.target.checked) }} />I explicitly verified reopening or cancellation of this incident</label><button>Verify and reopen</button></fieldset></form>}
    </>}
    {!editable && <p>Read-only operational history. Campus operations or system administrator permission is required to change restrictions.</p>}
  </section>
}
