import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ErrorMessage } from './AdminApp'
import { adminApi } from './api'
import { warningReasons } from './publicationState'
import type { Session } from './api'

export type Diagnostic = { id: string; severity: 'error' | 'warning'; code: string; message: string; entity: string; ids: string[] }
type Source = { id: string; title: string; rights: string; provenance: string; attribution: string; uploader_id: string; approved_by: string | null; original_checksum: string | null; derivative: object | null }
type Evidence = { source: string; target: string; profile: string; expected_found: boolean; reason: string; passed: boolean; actual?: { found: boolean; distance_m: number | null; edge_ids: string[] }; error?: string }
type Validation = { id: string; edit_version: number; checksum: string; report: { errors: number; warnings: number; diagnostics: Diagnostic[]; imports: object[] }; evidence: Evidence[] }
type Submission = { id: string; status: string; validation_id: string; submitter_id: string; checksum: string; edit_version: number; acknowledgements: Record<string, string>; decisions: { decision: string; actor_id: string; notes: string; created_at: string }[] }
export type ReviewPacket = { id: string; status: string; edit_version: number; checksum: string; sources: Record<string, Source>; places: { id: string; name: string }[]; validations: Validation[]; submissions: Submission[]; diff: { entity: string; id: string; before: object | null; after: object | null }[]; public_counts: Record<string, number>; limits: string }
type History = { active_release_id: string | null; releases: { id: string; revision_id: string; version: number; publication_order: number; published_at: string; checksum: string; artifact_checksum: string | null; legacy_demo: boolean; publisher_id: string | null }[] }

export function Publication({ path, campusPath, session, permissions }: { path: string; campusPath: string; session: Session; permissions: string[] }) {
  const cache = useQueryClient()
  const packet = useQuery({ queryKey: ['admin', path, 'review'], queryFn: () => adminApi<ReviewPacket>(`${path}/review`), retry: false })
  const history = useQuery({ queryKey: ['admin', campusPath, 'releases'], queryFn: () => adminApi<History>(`${campusPath}/releases`), retry: false })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [message, setMessage] = useState('')
  const [acknowledgements, setAcknowledgements] = useState<Record<string, string>>({})
  const [reason, setReason] = useState('')
  const [notes, setNotes] = useState('')
  const [source, setSource] = useState({ title: '', rights: 'synthetic', provenance: '', attribution: '', display_overlay: false })
  const [original, setOriginal] = useState<object | null>(null)
  const [filename, setFilename] = useState('')
  const [routeSource, setRouteSource] = useState('')
  const [routeTarget, setRouteTarget] = useState('')
  const [standard, setStandard] = useState('true')
  const [stepFree, setStepFree] = useState('true')
  const [routeReason, setRouteReason] = useState('')
  const [maximum, setMaximum] = useState('')
  const [publish, setPublish] = useState<{ key: string; submission_id: string; expected_release_id: string | null; version: number } | null>(null)
  const allowed = (permission: string) => permissions.includes(permission)
  const data = packet.data
  const run = data?.validations.find(v => v.edit_version === data.edit_version && v.checksum === data.checksum)
  const submission = data?.submissions.find(s => ['submitted', 'approved', 'published'].includes(s.status))
  const reviewRun = data?.validations.find(v => v.id === submission?.validation_id)
  const visibleRun = data?.status === 'draft' ? run ?? data.validations[0] : reviewRun
  const warnings = visibleRun?.report.diagnostics.filter(d => d.severity === 'warning') ?? []
  const acknowledged = warnings.every(d => (acknowledgements[d.id]?.trim().length ?? 0) >= 10)
  const ownSubmission = submission?.submitter_id === session.user_id
  async function action(url: string, body?: unknown, method = 'POST', version = data?.edit_version) {
    setBusy(true); setError(null); setMessage('')
    try {
      await adminApi(url, { method, body, csrf: session.csrf_token, version })
      setMessage('Action saved. Public navigation changes only on confirmed publication or rollback.')
      await packet.refetch(); await history.refetch()
      await cache.invalidateQueries({ queryKey: ['admin'] })
      return true
    } catch (e) { setError(e); return false } finally { setBusy(false) }
  }
  if (packet.isPending) return <p role="status">Loading review packet…</p>
  if (!data) return <section className="admin-card"><ErrorMessage error={packet.error} /><button onClick={() => void packet.refetch()}>Retry review packet</button></section>
  return <section className="admin-card publication-workspace"><h2>Validation and review</h2>
    <p role="status">Revision state: <strong>{data.status}</strong> · edit version {data.edit_version}</p><p className="admin-id">Reviewed content SHA-256: {data.checksum}</p>
    <p>Changes remain private until an independent reviewer approves this exact version and confirms publication. Returning to draft invalidates approval and route evidence. Synthetic evidence is never a physical accessibility certification.</p>
    {packet.isFetching && <p role="status">Refreshing the current review version…</p>}
    <ErrorMessage error={error} />{message && <p className="admin-success" role="status">{message}</p>}
    <button disabled={busy || packet.isFetching} onClick={() => void packet.refetch()}>Refresh review packet</button><small>Refresh preserves your form input. Resolve stale versions using the latest packet before retrying.</small>
    <details><summary>Changes from parent release ({data.diff.length})</summary>{data.diff.map(d => <details key={`${d.entity}:${d.id}`}><summary>{d.entity} · {d.id} · {d.before ? d.after ? 'updated' : 'removed' : 'added'}</summary><pre tabIndex={0}>{JSON.stringify({ before: d.before, after: d.after }, null, 2)}</pre></details>)}{!data.diff.length && <p>No entity changes.</p>}</details>
    <details><summary>Approved public projection counts</summary><pre tabIndex={0}>{JSON.stringify(data.public_counts, null, 2)}</pre><p>Restricted rows, originals, source notes, reviewer identities/decisions and internal evidence are excluded.</p></details>
    <h3>Source rights and public derivatives</h3><p>Outdoor JSON/GeoJSON only in this milestone. Private originals are stored in the protected database. A reviewer must inspect rights and the sanitized derivative; only features explicitly marked <code>properties.public=true</code> can enter it. Image/PDF floorplans follow in Milestone 3.</p>
    {Object.values(data.sources).map(s => <article className="import-detail" key={s.id}><h4>{s.title}</h4><p>Rights: {s.rights} · {s.approved_by ? 'Approved' : 'Awaiting independent source review'}</p><p>Provenance: {s.provenance}</p><p>Attribution: {s.attribution}</p><small>Original checksum: {s.original_checksum ?? 'Metadata-only source'}</small>
      {s.derivative && <details><summary>Inspect exact public derivative</summary><pre tabIndex={0}>{JSON.stringify(s.derivative, null, 2)}</pre></details>}
      {s.original_checksum && <a href={`/api/v1/admin${path}/sources/${s.id}/original`} download>Download private original {s.title}</a>}
      <div className="admin-actions">{allowed('source_approve') && !s.approved_by && <button disabled={busy || packet.isFetching || data.status !== 'draft' || s.uploader_id === session.user_id} onClick={() => { if (window.confirm(`Approve the recorded rights and exact derivative for ${s.title}? The private original remains inaccessible publicly.`)) void action(`${path}/sources/${s.id}/approve`) }}>Approve source {s.title}</button>}
      {allowed('catalog_edit') && <button disabled={busy || packet.isFetching || data.status !== 'draft'} onClick={() => { if (window.confirm('Remove this draft source and its private original? Existing immutable releases retain their copies.')) void action(`${path}/sources/${s.id}`, undefined, 'DELETE') }}>Remove source {s.title}</button>}</div>
    </article>)}
    {allowed('catalog_edit') && data.status === 'draft' && <form onSubmit={async e => { e.preventDefault(); if (await action(`${path}/sources`, { ...source, original })) { setSource({ title: '', rights: 'synthetic', provenance: '', attribution: '', display_overlay: false }); setOriginal(null); setFilename('') } }}><fieldset disabled={busy || packet.isFetching}><legend>Register a draft source</legend><div className="admin-form-grid">
      <label>Source title<input required value={source.title} maxLength={160} onChange={e => setSource({ ...source, title: e.target.value })} /></label>
      <label>Source rights<select value={source.rights} onChange={e => setSource({ ...source, rights: e.target.value })}><option value="synthetic">Synthetic demo only</option><option value="authorized">Authorized for this public audience</option><option value="restricted">Restricted original · never public</option></select></label>
      <label>Source provenance<textarea required minLength={10} maxLength={4000} value={source.provenance} onChange={e => setSource({ ...source, provenance: e.target.value })} /></label>
      <label>Public attribution<input required maxLength={500} value={source.attribution} onChange={e => setSource({ ...source, attribution: e.target.value })} /></label>
      <label>Optional private GeoJSON original<input type="file" accept=".json,.geojson" onChange={async e => { const file = e.target.files?.[0]; setOriginal(null); setFilename(''); setError(null); if (!file) return; try { if (file.size > 5 * 1024 * 1024) throw new Error('Original exceeds 5MiB.'); const value: unknown = JSON.parse(await file.text()); if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Original must be a JSON object.'); setOriginal(value); setFilename(file.name) } catch (err) { setError(err) } }} /><small>{filename || 'No original selected'}</small></label>
      <label className="graph-checkbox"><input type="checkbox" checked={source.display_overlay} onChange={e => setSource({ ...source, display_overlay: e.target.checked })} />Propose a sanitized outdoor display overlay</label>
    </div><button>Register source for independent review</button></fieldset></form>}
    {allowed('review_submit') && data.status === 'draft' && <form onSubmit={e => { e.preventDefault(); const from = routeSource || data.places[0]?.id; const to = routeTarget || data.places.find(p => p.id !== from)?.id; void action(`${path}/validations`, { routes: [{ profile: 'shortest', expected_found: standard === 'true' }, { profile: 'step_free', expected_found: stepFree === 'true' }].map(r => ({ ...r, source: from, target: to, maximum_distance_m: maximum ? Number(maximum) : null, reason: routeReason })) }) }}><fieldset disabled={busy || packet.isFetching}><legend>Expected-route evidence and whole-draft validation</legend><p>Runs Dijkstra on stored public-eligible draft data; it never changes the active release. Expected no-route results require an explicit coverage reason.</p><div className="admin-form-grid">
      <label>Evidence start<select value={routeSource || data.places[0]?.id || ''} onChange={e => setRouteSource(e.target.value)}>{data.places.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <label>Evidence destination<select value={routeTarget || data.places.find(p => p.id !== (routeSource || data.places[0]?.id))?.id || ''} onChange={e => setRouteTarget(e.target.value)}>{data.places.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <label>Expected standard route<select value={standard} onChange={e => setStandard(e.target.value)}><option value="true">Route found</option><option value="false">No route · documented gap</option></select></label>
      <label>Expected step-free route<select value={stepFree} onChange={e => setStepFree(e.target.value)}><option value="true">Route found</option><option value="false">No verified route · documented gap</option></select></label>
      <label>Optional maximum distance in metres<input type="number" min="0.01" step="any" max="100000" value={maximum} onChange={e => setMaximum(e.target.value)} /></label>
      <label>Route evidence reason<textarea required minLength={10} maxLength={2000} value={routeReason} onChange={e => setRouteReason(e.target.value)} /></label>
    </div><button disabled={data.places.length < 2}>Run authoritative validation</button></fieldset></form>}
    {visibleRun ? <><h3>Validation evidence</h3><p>{visibleRun.report.errors} blocking errors · {visibleRun.report.warnings} warnings · validation {visibleRun.id}</p>{data.status === 'draft' && !run && <p role="status">This validation is stale. Run authoritative validation again before submission.</p>}
      <ol className="graph-diagnostics">{visibleRun.report.diagnostics.map(d => <li key={d.id}><strong>{d.severity}: {d.code}</strong><p>{d.message}</p><small>{d.entity} · {d.ids.join(', ')}</small>{d.severity === 'warning' && <label>Reason for warning {d.id}<textarea minLength={10} maxLength={2000} value={acknowledgements[d.id] ?? ''} onChange={e => setAcknowledgements({ ...acknowledgements, [d.id]: e.target.value })} /></label>}</li>)}</ol>
      {warnings.length > 0 && <div><label>Reason after reviewing all displayed warnings<textarea value={reason} minLength={10} maxLength={2000} onChange={e => setReason(e.target.value)} /></label><button disabled={reason.trim().length < 10 || busy} onClick={() => setAcknowledgements(warningReasons(visibleRun.report.diagnostics, reason))}>Acknowledge all {warnings.length} warnings with this reason</button><p>Individual warning reasons can be edited above. Reviewer acknowledgement is a separate decision.</p></div>}
      <details open><summary>Computed route acceptance evidence</summary>{visibleRun.evidence.map((e, i) => <div key={i}><p>{e.profile}: {e.passed ? 'PASS' : 'FAIL'} · {e.actual?.found ? `${e.actual.distance_m?.toFixed(2)}m / ${e.actual.edge_ids.length} stored edges` : 'No eligible route'}</p><p>{e.reason}</p>{e.error && <p>{e.error}</p>}</div>)}</details>
      <details><summary>Imported batch provenance</summary><pre tabIndex={0}>{JSON.stringify(visibleRun.report.imports, null, 2)}</pre></details>
    </> : <p>No validation yet. Register/review sources and compute route evidence.</p>}
    {allowed('review_submit') && data.status === 'draft' && <button disabled={busy || packet.isFetching || !run || !!run.report.errors || !acknowledged} onClick={() => void action(`${path}/submissions`, { validation_id: run?.id, acknowledgements })}>Submit exact validated version for review</button>}
    {submission && <section className="import-detail"><h3>Review submission: {submission.status}</h3><p className="admin-id">{submission.id} · SHA-256 {submission.checksum}</p>
      <details><summary>Submitter warning acknowledgements</summary><pre tabIndex={0}>{JSON.stringify(submission.acknowledgements, null, 2)}</pre></details>
      {data.status === 'review' && <><label>Review decision notes<textarea value={notes} minLength={10} maxLength={4000} onChange={e => setNotes(e.target.value)} /></label><div className="admin-actions">
        {allowed('review_decide') && submission.status === 'submitted' && <button disabled={busy || ownSubmission || !acknowledged || notes.trim().length < 10} onClick={() => void action(`${path}/submissions/${submission.id}/decision`, { decision: 'approve', notes, acknowledgements })}>Approve exact reviewed content</button>}
        {allowed('review_decide') && <button disabled={busy || notes.trim().length < 10} onClick={() => void action(`${path}/submissions/${submission.id}/decision`, { decision: 'reject', notes })}>Reject and return to draft</button>}
        {allowed('review_submit') && ownSubmission && <button disabled={busy || notes.trim().length < 10} onClick={() => void action(`${path}/submissions/${submission.id}/decision`, { decision: 'withdraw', notes })}>Withdraw and return to draft</button>}
      </div>{ownSubmission && <p>You submitted this revision; an independent reviewer must approve/publish. Server checks every contributor, including system administrators.</p>}
      {submission.status === 'approved' && allowed('release_publish') && <button disabled={busy || ownSubmission || !history.data} onClick={() => setPublish({ submission_id: submission.id, expected_release_id: history.data!.active_release_id, version: data.edit_version, key: crypto.randomUUID() })}>Prepare publication</button>}</>}
      {submission.decisions.map(d => <article key={`${d.created_at}:${d.decision}`}><p>{d.decision} · {d.actor_id} · {new Date(d.created_at).toLocaleString()}</p><p>{d.notes}</p></article>)}
    </section>}
    <details><summary>Review and validation history</summary>{data.submissions.map(s => <p key={s.id}>{s.id} · {s.status} · version {s.edit_version}</p>)}{data.validations.map(v => <p key={v.id}>{v.id} · validated version {v.edit_version} · {v.report.errors} errors / {v.report.warnings} warnings</p>)}</details>
    {publish && <form className="graph-conflicts" onSubmit={async e => { e.preventDefault(); if (await action(`${path}/publish`, { key: publish.key, submission_id: publish.submission_id, expected_release_id: publish.expected_release_id }, 'POST', publish.version)) { setPublish(null); setMessage('Publication completed. Public search, directory, map and routes now use the new immutable release.') } }}><h3>Confirm publication</h3><p className="admin-id">Current public release: {publish.expected_release_id ?? 'none'}<br />New revision: {data.id} · approved version {publish.version}</p><p>Freezes this approved revision permanently and atomically replaces public search, directory, map and routing. Private originals/restricted records remain excluded. An error retains the previous active release.</p><label className="graph-checkbox"><input type="checkbox" required />I reviewed the consequences and the exact approved content</label><div className="admin-actions"><button disabled={busy || packet.isFetching}>Confirm publish immutable release</button><button type="button" disabled={busy || packet.isFetching} onClick={() => setPublish(null)}>Cancel publication</button></div></form>}
    <small>{data.limits}</small>
  </section>
}

export function ReleaseHistory({ path, session, canPublish }: { path: string; session: Session; canPublish: boolean }) {
  const cache = useQueryClient()
  const history = useQuery({ queryKey: ['admin', path, 'releases'], queryFn: () => adminApi<History>(`${path}/releases`), retry: false })
  const [target, setTarget] = useState('')
  const [reason, setReason] = useState('')
  const [prepared, setPrepared] = useState<{ target_release_id: string; expected_release_id: string; key: string; reason: string } | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const active = history.data?.releases.find(r => r.id === history.data?.active_release_id)
  const eligible = history.data?.releases.filter(r => active && r.publication_order < active.publication_order) ?? []
  return <section className="admin-card"><h2>Release history and rollback</h2><p>History is preserved. Rollback switches the public pointer to an earlier immutable release. Live closures are not implemented; overlay version remains zero.</p><ErrorMessage error={error ?? history.error} />{history.isPending && <p role="status">Loading release history…</p>}<button disabled={busy} onClick={() => void history.refetch()}>Refresh release history</button>{message && <p role="status">{message}</p>}
    <ol className="import-history">{history.data?.releases.map(r => <li key={r.id}><strong>Release {r.version} · publication {r.publication_order} {r.id === active?.id ? '· active' : ''}</strong><p className="admin-id">{r.id} · {new Date(r.published_at).toLocaleString()}<br />Content checksum: {r.checksum}<br />Public artifact: {r.artifact_checksum ?? 'Legacy trusted synthetic seed (no artifact)'}</p>{r.artifact_checksum && <a href={`/api/v1/campuses/${path.split('/')[2]}/artifacts/${r.id}/${r.artifact_checksum}.json`} download>Download approved public release {r.version}</a>}</li>)}</ol>
    {canPublish && eligible.length > 0 && <form onSubmit={e => { e.preventDefault(); if (active) setPrepared({ target_release_id: target || eligible[0].id, expected_release_id: active.id, key: crypto.randomUUID(), reason }) }}><fieldset disabled={busy}><legend>Prepare an explicit rollback</legend><label>Earlier release<select value={target || eligible[0].id} onChange={e => setTarget(e.target.value)}>{eligible.map(r => <option key={r.id} value={r.id}>Release {r.version} · {r.id}</option>)}</select></label><label>Rollback reason<textarea required minLength={10} maxLength={4000} value={reason} onChange={e => setReason(e.target.value)} /></label><button>Prepare rollback</button></fieldset></form>}
    {prepared && <form className="graph-conflicts" onSubmit={async e => { e.preventDefault(); setBusy(true); setError(null); try { await adminApi(`${path}/rollback`, { method: 'POST', body: prepared, csrf: session.csrf_token }); setPrepared(null); setMessage('Rollback completed; release history retained.'); await cache.invalidateQueries({ queryKey: ['admin'] }) } catch (err) { setError(err) } finally { setBusy(false) } }}><h3>Confirm rollback</h3><p className="admin-id">Replace {prepared.expected_release_id} with {prepared.target_release_id}</p><p>{prepared.reason}</p><label className="graph-checkbox"><input type="checkbox" required />I understand public navigation will use the earlier release</label><button disabled={busy}>Confirm rollback to earlier release</button><button type="button" disabled={busy} onClick={() => setPrepared(null)}>Cancel rollback</button></form>}
  </section>
}
