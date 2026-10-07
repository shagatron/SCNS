import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { adminApi, type Dashboard } from './api'
import { ErrorMessage } from './AdminApp'

type Options = { schema_version?: string; format: string; entity: string; campus_code: string; timezone: string; units?: string; source_rights: string; provenance: string; policy: string; mapping: Record<string, string> }
type Row = { row: number; entity: string; external_id: string; action: string; errors: string[]; warnings: string[]; before?: unknown; after?: unknown; data?: unknown }
type Job = { id: string; revision_id: string; filename: string; byte_size: number; checksum: string; uploader_id: string; applier_id: string | null; state: string; attempts: number; options: Options; preview_version: number | null; failure: string | null; counts: Record<string, number> | null; rows: Row[]; total_rows: number; history: { state: string; at: string; actor_id: string | null }[]; created_at: string; updated_at: string }
const entities = ['buildings', 'places', 'departments', 'department_places', 'aliases', 'anchors', 'frames', 'nodes', 'edges']
const fields = ['external_id', 'existing_id', 'campus_code', 'code', 'name', 'kind', 'description', 'visibility', 'point', 'footprint', 'geometry', 'building_id', 'frame_id', 'label', 'place_id', 'node_id', 'department_id', 'place_ids', 'value', 'language', 'from_node_id', 'to_node_id', 'physical_path_id', 'distance_status', 'accessibility_status', 'accessibility_evidence', 'evidence', 'is_open']
function Mapping({ value, onChange }: { value: Record<string, string>; onChange: (value: Record<string, string>) => void }) {
  const entries = Object.entries(value)
  return <fieldset><legend>Field mapping (optional)</legend><p>Matching field names map automatically. For renamed columns, choose a target field and enter its source column. Geometry cells contain quoted JSON. References use external IDs or existing draft UUIDs.</p>
    {entries.map(([target, source], index) => <div className="import-mapping" key={index}>
      <label>Target field {index + 1}<select value={target} onChange={e => { const copy = { ...value }; delete copy[target]; copy[e.target.value] = source; onChange(copy) }}>{fields.map(field => <option key={field} disabled={field !== target && field in value}>{field}</option>)}</select></label>
      <label>Source column {index + 1}<input value={source} maxLength={160} required onChange={e => onChange({ ...value, [target]: e.target.value })} /></label>
      <button type="button" onClick={() => { const copy = { ...value }; delete copy[target]; onChange(copy) }}>Remove mapping {index + 1}</button>
    </div>)}
    <button type="button" disabled={entries.length === fields.length} onClick={() => { const field = fields.find(f => !(f in value)); if (field) onChange({ ...value, [field]: '' }) }}>Add field mapping</button>
  </fieldset>
}
function Policy({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return <label>Duplicate policy<select value={value} onChange={e => onChange(e.target.value)}><option value="create_only">Create only; differing existing records conflict</option><option value="upsert">Explicit upsert; replace existing fields after preview</option></select><small>Unchanged records are always a no-op. Duplicate codes never silently match: use existing_id to explicitly adopt the intended draft record.</small></label>
}

export function Imports({ path, draftId, csrf, editable, campus }: { path: string; draftId: string; csrf: string; editable: boolean; campus: Dashboard }) {
  const cache = useQueryClient()
  const submission = useRef<{ fingerprint: string; key: string } | null>(null)
  const [jobId, setJobId] = useState('')
  const [offset, setOffset] = useState(0)
  const [format, setFormat] = useState('csv')
  const [entity, setEntity] = useState('places')
  const [policy, setPolicy] = useState('create_only')
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const queryKey = ['admin', campus.campus_id, 'imports']
  const jobs = useQuery({ queryKey: [...queryKey, offset], queryFn: () => adminApi<{ items: Job[]; total: number }>(`${path}/imports?offset=${offset}`), refetchInterval: query => query.state.data?.items.some(j => ['uploaded', 'parsing'].includes(j.state)) ? 1500 : false })
  return <section className="admin-card"><h2>Staged campus-data imports</h2><p>Selected draft only. Importing never publishes. {campus.is_demo && <strong>Synthetic Demo Campus — no official map or field verification.</strong>}</p>
    <p>Upload UTF-8 CSV, import-v1 JSON bundles or RFC 7946 GeoJSON. Limits: 5 MiB and 2,000 rows by default. JSON bundles can include related catalog and outdoor graph records; indoor plans, floors and connectors remain later work.</p>
    <div className="admin-actions">{['places.csv', 'catalog-bundle.json', 'places.geojson'].map(name => <a key={name} href={`${path.startsWith('/') ? '/api/v1/admin' : ''}${path}/import-templates/${name}`} download>Download {name} template</a>)}</div>
    {editable && <form onSubmit={async event => {
      event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); const file = data.get('file')
      if (!(file instanceof File)) return
      if (!file.size || file.size > 5 * 1024 * 1024) { setError(new Error('Choose a non-empty file of at most 5 MiB.')); return }
      setBusy(true); setError(null); setNotice('')
      const options: Options = { format, entity, campus_code: campus.campus_code, timezone: campus.timezone, source_rights: String(data.get('rights')), provenance: String(data.get('provenance')), policy, mapping }
      try {
        const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer())
        const fingerprint = `${draftId}:${file.name}:${JSON.stringify(options)}:${Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('')}`
        if (submission.current?.fingerprint !== fingerprint) submission.current = { fingerprint, key: crypto.randomUUID() }
        const job = await adminApi<Job>(`${path}/drafts/${draftId}/imports?filename=${encodeURIComponent(file.name)}`, { method: 'POST', rawBody: file, csrf, headers: { 'Idempotency-Key': submission.current.key, 'X-Import-Options': btoa(Array.from(new TextEncoder().encode(JSON.stringify(options)), b => String.fromCharCode(b)).join('')) } })
        setJobId(job.id); setNotice('Upload staged. The worker will prepare a private preview.'); await cache.invalidateQueries({ queryKey }); form.reset(); submission.current = null
      } catch (e) { setError(e) } finally { setBusy(false) }
    }}>
      <div className="admin-form-grid"><label>Import format<select value={format} onChange={e => setFormat(e.target.value)}><option value="csv">CSV</option><option value="json">JSON bundle</option><option value="geojson">GeoJSON</option></select></label>
        <label>Default entity<select value={entity} onChange={e => setEntity(e.target.value)}>{entities.map(e => <option key={e}>{e}</option>)}</select></label>
        <label>Data file<input name="file" type="file" accept={`.${format}`} required /></label>
        <label>Source rights / authorization<input name="rights" required maxLength={2000} placeholder="Permission or synthetic test-data declaration" /></label>
        <label>Source and verification notes<textarea name="provenance" required maxLength={2000} placeholder="Source, version/date and survey limitations" /></label>
      </div><Policy value={policy} onChange={setPolicy} /><Mapping value={mapping} onChange={setMapping} />
      <button className="primary-button" disabled={busy}>{busy ? 'Uploading…' : 'Upload to selected draft'}</button>
    </form>}
    <ErrorMessage error={error} />{notice && <p role="status">{notice}</p>}
    {jobId && <ImportDetail key={jobId} path={`${path}/imports/${jobId}`} csrf={csrf} editable={editable} onChange={(revisionId = draftId) => Promise.all([
      cache.invalidateQueries({ queryKey }),
      cache.invalidateQueries({ queryKey: ['admin', `${path}/drafts/${revisionId}`] }),
      cache.invalidateQueries({ queryKey: ['admin', campus.campus_id, 'dashboard'] }),
    ])} />}
    <h3>Campus import history</h3><ErrorMessage error={jobs.error} />{jobs.isPending && <p>Loading import history…</p>}
    <ul className="import-history">{jobs.data?.items.map(job => <li key={job.id}><button onClick={() => setJobId(job.id)}>{job.filename} · {job.state.replaceAll('_', ' ')}</button><small>Draft {job.revision_id} · {new Date(job.created_at).toLocaleString()}</small></li>)}</ul>
    <div className="admin-actions"><button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous jobs</button><span>{jobs.data?.total ?? 0} jobs</span><button disabled={!jobs.data || offset + 25 >= jobs.data.total} onClick={() => setOffset(offset + 25)}>Next jobs</button></div>
  </section>
}

function ImportDetail({ path, csrf, editable, onChange }: { path: string; csrf: string; editable: boolean; onChange: (revisionId?: string) => Promise<unknown> }) {
  const [offset, setOffset] = useState(0)
  const job = useQuery({ queryKey: ['admin', 'import', path, offset], queryFn: () => adminApi<Job>(`${path}?offset=${offset}`), refetchInterval: query => ['uploaded', 'parsing'].includes(query.state.data?.state ?? '') ? 1000 : false })
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [notice, setNotice] = useState('')
  async function action(name: string) {
    setBusy(true); setError(null)
    try { await adminApi(`${path}/${name}`, { method: 'POST', csrf, version: job.data?.preview_version ?? undefined }); setConfirm(false); setNotice(name === 'apply' ? 'Batch applied to draft. Public release unchanged.' : `Import ${name} completed.`); await job.refetch(); await onChange(job.data?.revision_id) }
    catch (e) { setError(e); setConfirm(false) } finally { setBusy(false) }
  }
  if (!job.data) return <><ErrorMessage error={job.error} /><p>Loading import…</p></>
  const data = job.data
  const processed = ['preview_ready', 'validated', 'failed'].includes(data.state)
  const clean = data.counts && !data.counts.invalid && !data.counts.conflict
  return <section className="import-detail" aria-label="Import preview"><h3>{data.filename}</h3><p><strong>Job state: {data.state.replaceAll('_', ' ')}</strong> · Processing attempts {data.attempts}/3</p>
    <p className="admin-id">Target draft: {data.revision_id}<br />Uploaded by: {data.uploader_id}{data.applier_id && <><br />Applied by: {data.applier_id}</>}<br />SHA-256: {data.checksum}</p>
    {['uploaded', 'parsing'].includes(data.state) && <p role="status">Preparing preview. If this remains queued, start the import worker using the setup instructions.</p>}
    {data.failure && <ErrorMessage error={new Error(data.failure)} />}<ErrorMessage error={error} />{notice && <p role="status">{notice}</p>}
    {data.counts && <p className="import-counts">Additions: {data.counts.add} · Updates: {data.counts.update} · Unchanged: {data.counts.unchanged} · Conflicts: {data.counts.conflict} · Invalid: {data.counts.invalid}. Preview draft version: {data.preview_version}.</p>}
    <div className="admin-actions"><a href={`/api/v1/admin${path}/errors.csv`} download>Download row diagnostics CSV</a>
      {editable && <>{data.state === 'preview_ready' && <button disabled={busy || !clean} onClick={() => void action('validate')}>Validate clean preview</button>}
        {data.state === 'validated' && <button disabled={busy} onClick={() => setConfirm(true)}>Apply batch to draft</button>}
        {['preview_ready', 'validated'].includes(data.state) && <button disabled={busy} onClick={() => void action('refresh')}>Refresh preview after draft changes</button>}
        {data.state === 'failed' && data.attempts < 3 && <button disabled={busy} onClick={() => void action('retry')}>Retry processing</button>}
        {!['committed', 'cancelled'].includes(data.state) && <button disabled={busy} onClick={() => void action('cancel')}>Cancel import</button>}</>}
    </div>
    {confirm && <div className="admin-notice" role="group" aria-label="Confirm batch application"><p>Apply the entire validated batch to draft version {data.preview_version}? This is one transaction. A stale preview will be rejected. The public release stays unchanged.</p><button disabled={busy} onClick={() => void action('apply')}>Confirm apply to draft</button><button disabled={busy} onClick={() => setConfirm(false)}>Keep preview</button></div>}
    {editable && processed && <Reprocess key={data.updated_at} options={data.options} busy={busy} onSubmit={async options => {
      setBusy(true); setError(null); try { await adminApi(`${path}/mapping`, { method: 'PUT', csrf, body: options }); await job.refetch(); await onChange(job.data?.revision_id) } catch (e) { setError(e) } finally { setBusy(false) }
    }} />}
    <ol className="import-rows">{data.rows.map(row => <li key={row.row}><strong>Row {row.row}: {row.entity} / {row.external_id || '(missing ID)'} — {row.action}</strong>
      {row.errors.map((message, index) => <p className="error-box" key={index}>{message}</p>)}{row.warnings.map((message, index) => <p key={index}>{message}</p>)}
      <details><summary>Compare current and proposed fields</summary><h4>Current draft</h4><pre>{JSON.stringify(row.before ?? null, null, 2)}</pre><h4>Proposed</h4><pre>{JSON.stringify(row.after ?? row.data ?? null, null, 2)}</pre></details>
    </li>)}</ol>
    {data.total_rows > 50 && <div className="admin-actions"><button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous rows</button><span>Rows {offset + 1}–{Math.min(offset + 50, data.total_rows)} of {data.total_rows}</span><button disabled={offset + 50 >= data.total_rows} onClick={() => setOffset(offset + 50)}>Next rows</button></div>}
    <details><summary>Processing history</summary><ul>{data.history.map((entry, index) => <li key={index}>{entry.state.replaceAll('_', ' ')} · {new Date(entry.at).toLocaleString()}{entry.actor_id && ` · ${entry.actor_id}`}</li>)}</ul></details>
  </section>
}
function Reprocess({ options, busy, onSubmit }: { options: Options; busy: boolean; onSubmit: (options: Options) => Promise<void> }) {
  const [mapping, setMapping] = useState(options.mapping)
  const [policy, setPolicy] = useState(options.policy)
  return <details><summary>Adjust mapping or duplicate policy</summary><form onSubmit={event => { event.preventDefault(); void onSubmit({ ...options, mapping, policy }) }}><Policy value={policy} onChange={setPolicy} /><Mapping value={mapping} onChange={setMapping} /><button disabled={busy}>Reprocess with these settings</button></form></details>
}
