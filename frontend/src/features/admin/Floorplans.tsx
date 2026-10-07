import { lazy, Suspense, useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import { ErrorMessage } from './AdminApp'
import { adminApi, type Session } from './api'
import { discardFloorRecovery, readFloorRecovery, saveFloorRecovery } from './floorRecovery'
import type { Pixel } from './floorplanCoordinates'

const Viewer = lazy(() => import('./FloorplanViewer'))
type Measurement = { start: Pixel; end: Pixel; distance_m: number }
type Calibration = { primary: Measurement; checks: Measurement[]; measured_on: string; evidence: string; uncertainty_m: number; measured_by: string; reviewer: string | null; metres_per_pixel: number; quality: string }
type Floor = { id: string; building_id: string; code: string; label: string; ordering: number; elevation_m: number | null; visibility: string; frame_id: string | null; layer_id: string | null; frame: { width_px: number; height_px: number; metres_per_pixel: number | null; calibration: Calibration | null } | null; layer: { id: string; source_id: string; page: number; checksum: string; approved: boolean; uploader_id: string; rights: string; attribution: string } | null; dependencies: { layer_ids: string[]; pending_job_ids: string[]; graph_nodes: number } }
type Catalog = { edit_version: number; status: string; is_demo: boolean; campus_name: string; buildings: { id: string; name: string; code: string }[]; floors: Floor[]; truncated: boolean }
type Metadata = { page_count: number; pages: { page: number; width_px: number; height_px: number }[]; page: number; width_px: number; height_px: number; display_width_px: number; display_height_px: number; orientation: string }
type Job = { id: string; floor_id: string; filename: string; state: string; attempts: number; options: { page: number; redactions: Mask[] }; metadata: Metadata | null; failure: string | null; original_checksum: string; media_type: string; created_at: string }
type Mask = { x: number; y: number; width: number; height: number }
type FloorForm = { id: string; building_id: string; code: string; label: string; ordering: string; elevation_m: string; visibility: string }
type MeasureForm = { ax: string; ay: string; bx: string; by: string; distance: string; cx: string; cy: string; dx: string; dy: string; checkDistance: string; date: string; evidence: string; uncertainty: string }
const blankFloor: FloorForm = { id: '', building_id: '', code: '', label: '', ordering: '', elevation_m: '', visibility: 'public' }
const blankMeasure: MeasureForm = { ax: '', ay: '', bx: '', by: '', distance: '', cx: '', cy: '', dx: '', dy: '', checkDistance: '', date: '', evidence: '', uncertainty: '' }
const blankUpload = { title: '', rights: 'synthetic', provenance: '', attribution: '' }
function point(x: string, y: string): Pixel | undefined { return x !== '' && y !== '' && Number.isFinite(Number(x)) && Number.isFinite(Number(y)) ? { x: Number(x), y: Number(y) } : undefined }

export function Floorplans({ path, session, permissions }: { path: string; session: Session; permissions: string[] }) {
  const cache = useQueryClient()
  const floors = useQuery({ queryKey: ['admin', path, 'floors'], queryFn: () => adminApi<Catalog>(`${path}/floors`) })
  const [offset, setOffset] = useState(0)
  const jobs = useQuery({ queryKey: ['admin', path, 'floorplan-jobs', offset], queryFn: () => adminApi<{ items: Job[]; total: number }>(`${path}/floorplan-jobs?offset=${offset}`), refetchInterval: query => query.state.data?.items.some(j => ['uploaded', 'processing'].includes(j.state)) ? 1500 : false })
  const [selectedId, setSelectedId] = useState('')
  const [jobId, setJobId] = useState('')
  const [capturedVersion, setCapturedVersion] = useState<number | null>(null)
  const [form, setForm] = useState(blankFloor)
  const [measurement, setMeasurement] = useState(blankMeasure)
  const [uploadMeta, setUploadMeta] = useState(blankUpload)
  const [file, setFile] = useState<File | null>(null)
  const [page, setPage] = useState(1)
  const [masks, setMasks] = useState<Mask[]>([])
  const [uploadKey, setUploadKey] = useState(() => crypto.randomUUID())
  const [replacementConfirmed, setReplacementConfirmed] = useState(false)
  const [measurementConfirmed, setMeasurementConfirmed] = useState(false)
  const [picking, setPicking] = useState('')
  const [dirty, setDirty] = useState({ floor: false, upload: false, measurement: false })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [notice, setNotice] = useState('')
  const [conflict, setConflict] = useState(false)
  const recoveryKey = `${session.user_id}:${path}`
  const [recovered, setRecovered] = useState(() => readFloorRecovery(recoveryKey))
  const unsaved = dirty.floor || dirty.upload || dirty.measurement
  useEffect(() => {
    if (unsaved) saveFloorRecovery(recoveryKey, { form, measurement, uploadMeta, masks, page, selectedId, capturedVersion })
    else if (!recovered) discardFloorRecovery(recoveryKey)
    const prevent = (event: BeforeUnloadEvent) => { if (unsaved) event.preventDefault() }
    window.addEventListener('beforeunload', prevent); return () => window.removeEventListener('beforeunload', prevent)
  }, [unsaved, recoveryKey, form, measurement, uploadMeta, masks, page, selectedId, capturedVersion, recovered])
  if (floors.data && capturedVersion === null) setCapturedVersion(floors.data.edit_version)
  const data = floors.data
  const floor = data?.floors.find(f => f.id === selectedId) ?? data?.floors[0]
  const selectedJob = jobs.data?.items.find(j => j.id === jobId)
  const editable = permissions.includes('catalog_edit') && data?.status === 'draft'
  const approver = permissions.includes('source_approve') && data?.status === 'draft'
  const blocked = busy || conflict || floors.isFetching
  async function refresh() {
    const latest = await floors.refetch()
    if (latest.data) { setCapturedVersion(latest.data.edit_version); setConflict(false); setMeasurementConfirmed(false); setReplacementConfirmed(false); setNotice('Latest revision loaded. Your inputs are retained; recheck the selected plan and explicitly confirm measurements/replacement before saving.') }
  }
  async function act<T extends { edit_version?: number }>(suffix: string, body?: unknown, method = 'POST', rawBody?: File, headers?: Record<string, string>): Promise<T | null> {
    setBusy(true); setError(null); setNotice('')
    try {
      const result = await adminApi<T>(`${path}/${suffix}`, { method, body, rawBody, headers, csrf: session.csrf_token, version: capturedVersion ?? undefined })
      if (result.edit_version) setCapturedVersion(result.edit_version)
      await Promise.all([cache.invalidateQueries({ queryKey: ['admin', path] }), cache.invalidateQueries({ queryKey: ['admin', path.split('/drafts/')[0].split('/').at(-1), 'dashboard'] })])
      setNotice('Draft action completed. Public outdoor navigation is unchanged.'); return result
    } catch (e) { setError(e); if (e instanceof ApiError && e.code === 'conflict') setConflict(true); return null } finally { setBusy(false) }
  }
  function setMeasure(key: keyof MeasureForm, value: string) { setMeasurement(m => ({ ...m, [key]: value })); setDirty(d => ({ ...d, measurement: true })); setMeasurementConfirmed(false) }
  function switchFloor(id: string) {
    if (unsaved && !window.confirm('Switch floor and discard unapplied form inputs?')) return
    setSelectedId(id); setForm(blankFloor); setMeasurement(blankMeasure); setDirty({ floor: false, upload: false, measurement: false }); setCapturedVersion(data?.edit_version ?? null); setReplacementConfirmed(false); setMeasurementConfirmed(false); setPicking(''); setFile(null); setMasks([])
  }
  const primary = [point(measurement.ax, measurement.ay), point(measurement.bx, measurement.by)].filter((p): p is Pixel => !!p)
  const check = [point(measurement.cx, measurement.cy), point(measurement.dx, measurement.dy)].filter((p): p is Pixel => !!p)
  return <section className="admin-card floorplan-workspace"><h2>Indoor floors and floorplans</h2>
    <p>Floor-local display/calibration foundations only. No rooms, corridors, connectors or indoor navigation are available.</p>
    {data?.is_demo && <aside className="admin-notice">Clearly synthetic floorplans and measurements: software fixtures, no real campus survey.</aside>}
    <ErrorMessage error={error || floors.error} />{notice && <p role="status">{notice}</p>}
    {floors.isPending && <p role="status">Loading draft floors…</p>}
    {floors.error && <button onClick={() => void refresh()}>Retry floors</button>}
    {unsaved && <p role="status">Unapplied form changes. Save explicitly; same-tab recovery lasts two hours. Private files are never stored in browser recovery.</p>}
    {!!recovered && <aside className="graph-conflicts"><p>Saved unapplied floorplan inputs are available. Reloads require file reselection and version reconciliation.</p><button onClick={() => {
      const value = recovered as { form: FloorForm; measurement: MeasureForm; uploadMeta: typeof blankUpload; masks: Mask[]; page: number; selectedId: string; capturedVersion: number }
      setForm(value.form); setMeasurement(value.measurement); setUploadMeta(value.uploadMeta); setMasks(value.masks); setPage(value.page); setSelectedId(value.selectedId); setCapturedVersion(value.capturedVersion); setDirty({ floor: true, upload: true, measurement: true }); setConflict(true); setRecovered(null)
    }}>Restore unapplied inputs</button><button onClick={() => { setRecovered(null); discardFloorRecovery(recoveryKey) }}>Discard saved recovery</button></aside>}
    {conflict && <aside className="graph-conflicts"><h3>Reconcile this draft before saving</h3><p>Your input remains intact. Compare the latest floor/plan with your form; refreshing never writes it.</p><details><summary>Latest floor metadata</summary><pre tabIndex={0}>{JSON.stringify(floor, null, 2)}</pre></details><button onClick={() => void refresh()}>Keep my inputs and reconcile latest version</button></aside>}
    {data && <><p>Revision {capturedVersion} · {data.status}. {data.truncated && 'Showing the first 500 floors.'}</p>
      <label>Selected floor<select value={floor?.id ?? ''} onChange={e => switchFloor(e.target.value)}><option value="">No floor selected</option>{data.floors.map(f => <option key={f.id} value={f.id}>{data.buildings.find(b => b.id === f.building_id)?.code} · {f.label} ({f.code})</option>)}</select></label>
      {!data.floors.length && <p>No floors yet. Create a draft floor in an existing building.</p>}
      {data.status !== 'draft' && <p role="status">Revision locked for review/frozen. Private previews and evidence remain readable.</p>}
      {editable && <><div className="admin-actions"><button onClick={() => { if (unsaved && !window.confirm('Start a new floor and discard unapplied form inputs?')) return; setForm(blankFloor); setCapturedVersion(data.edit_version); setDirty(d => ({ ...d, floor: false })) }}>New floor</button>{floor && <button onClick={() => { setForm({ id: floor.id, building_id: floor.building_id, code: floor.code, label: floor.label, ordering: String(floor.ordering), elevation_m: floor.elevation_m === null ? '' : String(floor.elevation_m), visibility: floor.visibility }); setCapturedVersion(data.edit_version); setDirty(d => ({ ...d, floor: false })) }}>Edit selected floor</button>}</div>
        <form onSubmit={async e => { e.preventDefault(); const payload = { building_id: form.building_id || data.buildings[0]?.id, code: form.code, label: form.label, ordering: Number(form.ordering), elevation_m: form.elevation_m === '' ? null : Number(form.elevation_m), visibility: form.visibility }; const result = await act<{ id?: string; edit_version: number }>(form.id ? `floors/${form.id}` : 'floors', payload, form.id ? 'PUT' : 'POST'); if (result) { if (result.id) setSelectedId(result.id); setForm(blankFloor); setDirty(d => ({ ...d, floor: false })) } }}>
          <fieldset disabled={blocked}><legend>{form.id ? 'Edit floor metadata' : 'Create floor'}</legend><div className="admin-form-grid">
            <label>Floor building<select value={form.building_id || data.buildings[0]?.id || ''} disabled={!!form.id} onChange={e => { setForm({ ...form, building_id: e.target.value }); setDirty(d => ({ ...d, floor: true })) }}>{data.buildings.map(b => <option key={b.id} value={b.id}>{b.code} · {b.name}</option>)}</select></label>
            {(['code', 'label', 'ordering', 'elevation_m'] as const).map(key => <label key={key}>{({ code: 'Floor code', label: 'Floor label', ordering: 'Floor ordering (basement negative, ground 0)', elevation_m: 'Floor elevation metres (optional, unknown when blank)' })[key]}<input value={form[key]} type={['ordering', 'elevation_m'].includes(key) ? 'number' : 'text'} step="any" required={key !== 'elevation_m'} maxLength={key === 'code' ? 32 : 160} onChange={e => { setForm({ ...form, [key]: e.target.value }); setDirty(d => ({ ...d, floor: true })) }} /></label>)}
            <label>Floor visibility<select value={form.visibility} onChange={e => { setForm({ ...form, visibility: e.target.value }); setDirty(d => ({ ...d, floor: true })) }}><option value="public">Public after approved release</option><option value="restricted">Restricted</option></select></label>
          </div><button>Save floor metadata</button></fieldset>
        </form></>}
      {floor && <><h3>{floor.label}</h3><p>Stable floor ID: <span className="admin-id">{floor.id}</span>. Ordering {floor.ordering}; elevation {floor.elevation_m === null ? 'unknown' : `${floor.elevation_m}m`}.</p>
        {floor.layer && floor.frame ? <><p>Selected page {floor.layer.page} · {floor.layer.rights} rights · {floor.layer.approved ? 'Sanitized derivative approved' : 'Independent derivative approval required'}. {floor.layer.attribution}</p>
          <Suspense fallback={<p role="status">Loading floor-local controls…</p>}><Viewer key={floor.layer.id} label="Selected private floorplan preview" url={`/api/v1/admin${path}/floorplan-layers/${floor.layer.id}/preview`} width={floor.frame.width_px} height={floor.frame.height_px} primary={primary.length ? primary : floor.frame.calibration ? [floor.frame.calibration.primary.start, floor.frame.calibration.primary.end] : undefined} check={check.length ? check : floor.frame.calibration ? [floor.frame.calibration.checks[0].start, floor.frame.calibration.checks[0].end] : undefined} picking={picking} onPick={p => { const pair: Record<string, [keyof MeasureForm, keyof MeasureForm]> = { 'primary start': ['ax', 'ay'], 'primary end': ['bx', 'by'], 'check start': ['cx', 'cy'], 'check end': ['dx', 'dy'] }; const keys = pair[picking]; if (keys) { setMeasure(keys[0], p.x.toFixed(2)); setMeasure(keys[1], p.y.toFixed(2)); setPicking('') } }} /></Suspense>
          {approver && !floor.layer.approved && <button disabled={blocked || floor.layer.uploader_id === session.user_id} onClick={() => { if (window.confirm('Approve this exact pixel-only sanitized derivative and permitted rights? Inspect masks and the private original first.')) void act(`sources/${floor.layer!.source_id}/approve`) }}>Approve selected sanitized floorplan</button>}
          <a href={`/api/v1/admin${path}/sources/${floor.layer.source_id}/original`}>Download private selected original</a>
          <p>{floor.frame.metres_per_pixel === null ? 'Uncalibrated — display only; no metric navigation, distance or ETA.' : `Uniform scale ${floor.frame.metres_per_pixel.toFixed(6)} m/px · ${floor.frame.calibration?.quality} · ${floor.frame.calibration?.reviewer ? 'Calibration independently reviewed' : 'Independent calibration review required'}`}</p>
          {floor.frame.calibration && <details><summary>Calibration measurements and private evidence</summary><pre tabIndex={0}>{JSON.stringify(floor.frame.calibration, null, 2)}</pre></details>}
          {approver && floor.frame.calibration && !floor.frame.calibration.reviewer && <button disabled={blocked || floor.frame.calibration.measured_by === session.user_id} onClick={() => { if (window.confirm('Approve the exact measured lines, scale, check tolerance, date and uncertainty?')) void act(`floors/${floor.id}/calibration/approve`) }}>Approve selected calibration evidence</button>}
          {editable && <form onSubmit={async e => { e.preventDefault(); const result = await act(`floors/${floor.id}/calibration`, { primary: { start: { x: Number(measurement.ax), y: Number(measurement.ay) }, end: { x: Number(measurement.bx), y: Number(measurement.by) }, distance_m: Number(measurement.distance) }, checks: [{ start: { x: Number(measurement.cx), y: Number(measurement.cy) }, end: { x: Number(measurement.dx), y: Number(measurement.dy) }, distance_m: Number(measurement.checkDistance) }], measured_on: measurement.date, evidence: measurement.evidence, uncertainty_m: Number(measurement.uncertainty), method: 'uniform_scale', plan_quality: 'uniform' }); if (result) { setDirty(d => ({ ...d, measurement: false })); setMeasurementConfirmed(false) } }}>
            <fieldset disabled={blocked}><legend>Uniform-scale calibration</legend><p>Use known measured distances and a nonparallel independent check. Stretched/perspective plans require rectification; 3A does not fit affine transforms. Unknown pixels never become metres.</p>
              <div className="admin-actions">{['primary start', 'primary end', 'check start', 'check end'].map(label => <button key={label} type="button" aria-pressed={picking === label} onClick={() => setPicking(label)}>Pick {label} on plan</button>)}</div>
              <div className="admin-form-grid">{(['ax', 'ay', 'bx', 'by', 'distance', 'cx', 'cy', 'dx', 'dy', 'checkDistance', 'uncertainty'] as const).map(key => <label key={key}>{({ ax: 'Primary start X (px)', ay: 'Primary start Y (px)', bx: 'Primary end X (px)', by: 'Primary end Y (px)', distance: 'Known primary distance (m)', cx: 'Check start X (px)', cy: 'Check start Y (px)', dx: 'Check end X (px)', dy: 'Check end Y (px)', checkDistance: 'Known check distance (m)', uncertainty: 'Measurement uncertainty (m)' })[key]}<input type="number" step="any" min="0" required value={measurement[key]} onChange={e => setMeasure(key, e.target.value)} /></label>)}
                <label>Measurement date<input type="date" required value={measurement.date} onChange={e => setMeasure('date', e.target.value)} /></label><label>Measurement evidence and quality<textarea required minLength={10} maxLength={4000} value={measurement.evidence} onChange={e => setMeasure('evidence', e.target.value)} /></label>
              </div><label className="graph-checkbox"><input type="checkbox" checked={measurementConfirmed} onChange={e => setMeasurementConfirmed(e.target.checked)} />I checked these measurements on the current selected plan</label><button disabled={!measurementConfirmed}>Save calibration evidence</button>
            </fieldset>
          </form>}
        </> : <p>No selected plan. Upload/process a permitted source and explicitly apply a ready page.</p>}
        {editable && <form onSubmit={async e => { e.preventDefault(); if (!file) { setError(new Error('Select a private PDF/PNG/JPEG.')); return }; const result = await act<{ id: string } & { edit_version?: number }>('floorplan-jobs', undefined, 'POST', file, { 'X-Floorplan-Metadata': encodeURIComponent(JSON.stringify({ ...uploadMeta, floor_id: floor.id, filename: file.name, page, redactions: masks, key: uploadKey })) }); if (result) { setJobId(result.id); setOffset(0); setDirty(d => ({ ...d, upload: false })); setUploadKey(crypto.randomUUID()) } }}>
          <fieldset disabled={blocked}><legend>Private plan upload and selected-page processing</legend><p>PDF/PNG/JPEG only. 10MiB; at most 30 PDF pages; 32 million reference pixels and 10,000px/side. Display PNG ≤2048px/side. Files stay private.</p>
            <label>Private floorplan file<input type="file" accept=".pdf,.png,.jpg,.jpeg" required onChange={e => { setFile(e.target.files?.[0] ?? null); setUploadKey(crypto.randomUUID()); setDirty(d => ({ ...d, upload: true })) }} /></label>
            <div className="admin-form-grid">{(['title', 'provenance', 'attribution'] as const).map(key => <label key={key}>Plan {key}<input required minLength={key === 'provenance' ? 10 : 1} maxLength={key === 'provenance' ? 4000 : key === 'title' ? 160 : 500} value={uploadMeta[key]} onChange={e => { setUploadMeta({ ...uploadMeta, [key]: e.target.value }); setUploadKey(crypto.randomUUID()); setDirty(d => ({ ...d, upload: true })) }} /></label>)}
              <label>Plan rights<select value={uploadMeta.rights} onChange={e => { setUploadMeta({ ...uploadMeta, rights: e.target.value }); setUploadKey(crypto.randomUUID()); setDirty(d => ({ ...d, upload: true })) }}><option value="synthetic">Clearly synthetic demo</option><option value="authorized">Authorized for intended public audience</option><option value="restricted">Restricted · never public</option></select></label>
              <label>PDF page / image page 1<input type="number" min="1" max="30" value={page} required onChange={e => { setPage(Number(e.target.value)); setUploadKey(crypto.randomUUID()); setDirty(d => ({ ...d, upload: true })) }} /></label>
            </div><p>Optional opaque masks use selected reference-page pixels; masked originals remain private. Inspect the result before derivative approval.</p>
            {masks.map((mask, index) => <div className="floorplan-mask" key={index}>{(['x', 'y', 'width', 'height'] as const).map(key => <label key={key}>Mask {index + 1} {key} (px)<input type="number" min={key === 'width' || key === 'height' ? 1 : 0} max="10000" required value={mask[key]} onChange={e => { setMasks(masks.map((m, i) => i === index ? { ...m, [key]: Number(e.target.value) } : m)); setUploadKey(crypto.randomUUID()); setDirty(d => ({ ...d, upload: true })) }} /></label>)}<button type="button" onClick={() => { setMasks(masks.filter((_, i) => i !== index)); setUploadKey(crypto.randomUUID()); setDirty(d => ({ ...d, upload: true })) }}>Remove mask {index + 1}</button></div>)}
            <button type="button" disabled={masks.length >= 20} onClick={() => { setMasks([...masks, { x: 0, y: 0, width: 1, height: 1 }]); setDirty(d => ({ ...d, upload: true })); setUploadKey(crypto.randomUUID()) }}>Add opaque mask rectangle</button><button>Upload private plan for processing</button>
          </fieldset>
        </form>}
        {editable && <details><summary>Floor deletion dependencies</summary><p>{floor.dependencies.layer_ids.length} draft layers, {floor.dependencies.pending_job_ids.length} staged jobs, {floor.dependencies.graph_nodes} graph nodes. Cancel staged jobs first. No silent cascade across graph references.</p><button disabled={blocked || floor.dependencies.pending_job_ids.length > 0 || floor.dependencies.graph_nodes > 0} onClick={async () => { if (!window.confirm(`Delete floor ${floor.label} and its ${floor.dependencies.layer_ids.length} draft layers/private source copies? Existing releases and retained job originals remain intact.`)) return; const result = await act(`floors/${floor.id}`, { remove_layer_ids: floor.dependencies.layer_ids }, 'DELETE'); if (result) { setSelectedId(''); setForm(blankFloor); setMeasurement(blankMeasure); setDirty({ floor: false, upload: false, measurement: false }) } }}>Confirm delete floor and listed draft layers</button></details>}
      </>}
    </>}
    <h3>Private processing jobs</h3>{jobs.isPending && <p role="status">Loading floorplan jobs…</p>}<ErrorMessage error={jobs.error} />{jobs.error && <button onClick={() => void jobs.refetch()}>Retry job history</button>}
    {jobs.data?.items.length === 0 && <p>No private floorplan jobs yet.</p>}
    <ul className="floorplan-jobs">{jobs.data?.items.map(job => <li key={job.id}><button aria-pressed={jobId === job.id} onClick={() => { setJobId(job.id); if (job.metadata) setPage(job.metadata.page); setReplacementConfirmed(false) }}>{job.filename} · {job.state} · page {job.options.page}</button><small>Attempts {job.attempts}/3 · {new Date(job.created_at).toLocaleString()}</small></li>)}</ul>
    {jobs.data && jobs.data.total > 50 && <div className="admin-actions"><button disabled={offset === 0} onClick={() => setOffset(v => Math.max(0, v - 50))}>Previous jobs</button><button disabled={offset + 50 >= jobs.data.total} onClick={() => setOffset(v => v + 50)}>Next jobs</button></div>}
    {selectedJob && <article className="import-detail"><h4>Private batch: {selectedJob.filename}</h4><p>Target floor: {data?.floors.find(f => f.id === selectedJob.floor_id)?.label ?? "Deleted historical floor"}</p><p role="status">Processing state: {selectedJob.state} · attempts {selectedJob.attempts}/3</p><p className="admin-id">Original SHA-256: {selectedJob.original_checksum}</p><a href={`/api/v1/admin${path}/floorplan-jobs/${selectedJob.id}/original`}>Download private batch original</a>{selectedJob.failure && <p role="alert">{selectedJob.failure}</p>}
      {['uploaded', 'processing'].includes(selectedJob.state) && <p>Durable worker is processing. Cancellation prevents a late result from applying; it may take up to the decode timeout to stop.</p>}
      {selectedJob.metadata && ['ready', 'applied'].includes(selectedJob.state) && <><p>{selectedJob.metadata.page_count} page(s) · {selectedJob.metadata.orientation} · display {selectedJob.metadata.display_width_px} × {selectedJob.metadata.display_height_px}px.</p><Suspense fallback={<p>Loading staged preview…</p>}><Viewer key={selectedJob.id} label="Staged sanitized page preview" url={`/api/v1/admin${path}/floorplan-jobs/${selectedJob.id}/preview`} width={selectedJob.metadata.width_px} height={selectedJob.metadata.height_px} /></Suspense>
        {editable && <><label>Process selected PDF page<select value={page} onChange={e => setPage(Number(e.target.value))}>{selectedJob.metadata.pages.map(p => <option key={p.page} value={p.page}>Page {p.page} · {p.width_px} × {p.height_px}px</option>)}</select></label><button disabled={blocked} onClick={async () => { const result = await act<{ id: string; edit_version?: number }>(`floorplan-jobs/${selectedJob.id}/pages`, { page, redactions: masks, key: crypto.randomUUID() }); if (result) { setJobId(result.id); setOffset(0) } }}>Create a new selected-page/mask batch</button></>}
      </>}
      {editable && selectedJob.state === 'ready' && <><p>Applying associates this selected page with its target floor, stays private and requires independent approval. Replacement resets prior scale/evidence.</p>{floor?.layer_id && selectedJob.floor_id === floor.id && <label className="graph-checkbox"><input type="checkbox" checked={replacementConfirmed} onChange={e => setReplacementConfirmed(e.target.checked)} />I confirm replacement of the current plan and clearing calibration</label>}
        <button disabled={blocked || !floor || selectedJob.floor_id !== floor.id || (!!floor.layer_id && !replacementConfirmed)} onClick={async () => { const result = await act(`floorplan-jobs/${selectedJob.id}/apply`, { replace_layer_id: floor?.layer_id ?? null, reset_calibration: replacementConfirmed }); if (result) { setMeasurement(blankMeasure); setMeasurementConfirmed(false); setPicking(''); setDirty(d => ({ ...d, measurement: false })) } }}>Apply ready page to selected draft floor</button></>}
      {editable && selectedJob.state === 'failed' && <button disabled={blocked || selectedJob.attempts >= 3} onClick={() => void act(`floorplan-jobs/${selectedJob.id}/control/retry`)}>Retry failed processing</button>}
      {editable && !['applied', 'cancelled'].includes(selectedJob.state) && <button disabled={blocked} onClick={() => { if (window.confirm('Cancel this staged batch? Its private original/history is retained.')) void act(`floorplan-jobs/${selectedJob.id}/control/cancel`) }}>Cancel staged floorplan batch</button>}
    </article>}
  </section>
}
