import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import { adminApi, allRecords, recordName, type CatalogPage, type CatalogRecord, type CatalogWrite, type Entity, type NodeOption } from './api'
import { ErrorMessage } from './AdminApp'

const entities: Entity[] = ['buildings', 'places', 'departments', 'aliases', 'anchors']
const title = (text: string) => text[0].toUpperCase() + text.slice(1)

export function Catalog({ path, csrf, editable }: { path: string; csrf: string; editable: boolean }) {
  const [entity, setEntity] = useState<Entity>('places')
  return <section className="admin-card"><h2>Catalog records</h2><p>{editable ? 'Edit the selected draft. Changes require a current draft version.' : 'Read-only access. Your role cannot edit this draft.'}</p>
    <div className="admin-tabs" aria-label="Catalog types">{entities.map(e => <button key={e} aria-pressed={e === entity} onClick={() => setEntity(e)}>{title(e)}</button>)}</div>
    <CatalogList key={entity} {...{ path, csrf, editable, entity }} />
  </section>
}

function CatalogList({ path, csrf, editable, entity }: { path: string; csrf: string; editable: boolean; entity: Entity }) {
  const cache = useQueryClient()
  const [offset, setOffset] = useState(0)
  const [editing, setEditing] = useState<{ record?: CatalogRecord; version: number } | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<{ record: CatalogRecord; version: number } | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const list = useQuery({ queryKey: ['admin', path, entity, offset], queryFn: () => adminApi<CatalogPage>(`${path}/catalog/${entity}?offset=${offset}&limit=25`) })
  const places = useQuery({ queryKey: ['admin', path, 'anchor-place-names'], queryFn: ({ signal }) => allRecords(`${path}/catalog/places`, signal), enabled: entity === 'anchors' })
  const names = new Map(places.data?.map(place => [place.id, recordName(place)]))
  const name = (record: CatalogRecord) => recordName(record, names)
  const refresh = () => cache.invalidateQueries({ queryKey: ['admin', path] })
  if (editing) return <CatalogForm {...{ path, csrf, entity }} initial={editing.record} version={editing.version} onCancel={() => setEditing(null)} onSaved={async () => { setEditing(null); setMessage('Draft saved. Public navigation is unchanged.'); await refresh() }} />
  return <>
    <div className="admin-actions"><button disabled={list.isFetching} onClick={() => { setError(null); void list.refetch() }}>Refresh records</button>{editable && <button disabled={!list.data || list.isFetching} onClick={() => { setMessage(''); setEditing({ version: list.data!.revision_version }) }}>Add {entity === 'aliases' ? 'alias' : entity.slice(0, -1)}</button>}</div>
    {message && <p role="status" className="admin-success">{message}</p>}<ErrorMessage error={error || list.error} />
    {list.isPending ? <p role="status">Loading records…</p> : list.data && <>
      <p className="muted">{list.data.total} records · Draft edit version {list.data.revision_version}</p>
      {!list.data.total && <p>No {entity} in this draft yet.</p>}
      <ul className="admin-records">{list.data.items.map(record => <li key={record.id}><div><h3>{name(record)}</h3><small className="admin-id">{record.id}</small><details><summary>Record details</summary><pre>{JSON.stringify(record.item.data, null, 2)}</pre></details></div>
        {editable && <div className="admin-actions"><button disabled={list.isFetching} onClick={() => { setMessage(''); setEditing({ record, version: list.data.revision_version }) }} aria-label={`Edit ${name(record)}`}>Edit</button><button disabled={list.isFetching} onClick={() => { setError(null); setConfirmDelete({ record, version: list.data.revision_version }) }} aria-label={`Delete ${name(record)}`}>Delete</button></div>}
      </li>)}</ul>
      <div className="admin-actions"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous records</button><span>Page {offset / 25 + 1}</span><button disabled={offset + 25 >= list.data.total} onClick={() => setOffset(offset + 25)}>Next records</button></div>
      {confirmDelete && <div className="admin-notice" role="group" aria-label="Confirm deletion"><p>Delete <strong>{name(confirmDelete.record)}</strong> from this draft? Referenced buildings and places must be unlinked first.</p><div className="admin-actions"><button disabled={busy} onClick={async () => {
        setBusy(true); setError(null)
        try { await adminApi(`${path}/catalog/${entity}/${confirmDelete.record.id}`, { method: 'DELETE', csrf, version: confirmDelete.version }); setConfirmDelete(null); setMessage('Record deleted from the draft.'); await refresh() }
        catch (e) { setError(e); setConfirmDelete(null); await refresh() } finally { setBusy(false) }
      }}>Confirm delete</button><button disabled={busy} onClick={() => setConfirmDelete(null)}>Keep record</button></div></div>}
    </>}
  </>
}

type Fields = Record<string, string>
function initialFields(record?: CatalogRecord): Fields {
  if (!record) return { visibility: 'public', kind: 'help', longitude: '', latitude: '', language: 'en', accessibility_status: 'unknown', is_open: 'true', footprint: '' }
  const data = record.item.data
  const fields: Fields = {}
  for (const [key, value] of Object.entries(data)) fields[key] = value == null ? '' : String(value)
  if ('point' in data) { fields.longitude = String(data.point.coordinates[0]); fields.latitude = String(data.point.coordinates[1]) }
  if ('footprint' in data) fields.footprint = JSON.stringify(data.footprint.coordinates)
  if ('place_ids' in data) fields.place_ids = (data.place_ids ?? []).join(',')
  return fields
}
function payload(entity: Entity, fields: Fields): CatalogWrite {
  const common = { code: fields.code, name: fields.name }
  const visibility = fields.visibility === 'restricted' ? 'restricted' as const : 'public' as const
  switch (entity) {
    case 'buildings': return { entity, data: { ...common, visibility, footprint: { type: 'Polygon', coordinates: JSON.parse(fields.footprint) } } }
    case 'places': return { entity, data: { ...common, kind: fields.kind as Extract<CatalogWrite, { entity: 'places' }>['data']['kind'], description: fields.description || '', building_id: fields.building_id || null, visibility, point: { type: 'Point', coordinates: [Number(fields.longitude), Number(fields.latitude)] } } }
    case 'departments': return { entity, data: { ...common, description: fields.description || '', place_ids: fields.place_ids ? fields.place_ids.split(',') : [] } }
    case 'aliases': return { entity, data: { place_id: fields.place_id, value: fields.value, language: fields.language } }
    case 'anchors': return { entity, data: { place_id: fields.place_id, node_id: fields.node_id, accessibility_evidence: fields.accessibility_evidence || '', accessibility_status: fields.accessibility_status as Extract<CatalogWrite, { entity: 'anchors' }>['data']['accessibility_status'], is_open: fields.is_open === 'true' } }
  }
}

function CatalogForm({ path, csrf, entity, initial, version, onCancel, onSaved }: { path: string; csrf: string; entity: Entity; initial?: CatalogRecord; version: number; onCancel: () => void; onSaved: () => Promise<void> }) {
  const [fields, setFields] = useState(() => initialFields(initial))
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [latest, setLatest] = useState<CatalogPage | null>(null)
  const [baseVersion, setBaseVersion] = useState(version)
  const [nodeSearch, setNodeSearch] = useState('')
  const [nodeOffset, setNodeOffset] = useState(0)
  const references = useQuery({ queryKey: ['admin', path, 'references'], queryFn: async ({ signal }) => ({ places: await allRecords(`${path}/catalog/places`, signal), buildings: await allRecords(`${path}/catalog/buildings`, signal) }), enabled: entity !== 'buildings' })
  const nodes = useQuery({ queryKey: ['admin', path, 'nodes', nodeSearch, nodeOffset], queryFn: () => adminApi<NodeOption[]>(`${path}/nodes?q=${encodeURIComponent(nodeSearch)}&offset=${nodeOffset}`), enabled: entity === 'anchors' })
  const field = (name: string) => ({ value: fields[name] ?? '', onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setFields({ ...fields, [name]: e.target.value }) })
  const textField = (name: string, label: string, max = 160) => <label>{label}<input {...field(name)} required maxLength={max} /></label>
  const options = (items: CatalogRecord[] | undefined) => items?.map(r => <option key={r.id} value={r.id}>{recordName(r)}</option>)
  const conflict = error instanceof ApiError && error.code === 'conflict'
  return <div className="admin-editor"><h3>{initial ? 'Edit' : 'Add'} {entity === 'aliases' ? 'alias' : entity.slice(0, -1)}</h3><p className="muted">Editing from draft version {baseVersion}. Switching sections discards unsaved input.</p>
    <form onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError(null); setLatest(null)
      try { const body = payload(entity, fields); await adminApi(`${path}/catalog/${entity}${initial ? `/${initial.id}` : ''}`, { method: initial ? 'PUT' : 'POST', body, csrf, version: baseVersion }); await onSaved() }
      catch (e) { setError(e instanceof SyntaxError ? new Error('Enter valid JSON coordinate rings for the footprint.') : e) } finally { setBusy(false) }
    }}>
      <fieldset disabled={busy}><div className="admin-form-grid">
        {['buildings', 'places', 'departments'].includes(entity) && <>{textField('code', 'Code', 32)}{textField('name', 'Name')}</>}
        {['places', 'departments'].includes(entity) && <label className="admin-wide">Description<textarea {...field('description')} maxLength={2000} rows={3} /></label>}
        {['buildings', 'places'].includes(entity) && <label>Visibility<select {...field('visibility')}><option value="public">Public when published</option><option value="restricted">Restricted</option></select></label>}
        {entity === 'buildings' && <label className="admin-wide">Footprint coordinate rings (JSON)<textarea {...field('footprint')} required rows={5} placeholder="[[[longitude, latitude], …, [same first point]]]" /><small>WGS84 longitude first. Close each ring; at least four coordinate pairs. This form does not edit the navigation graph.</small></label>}
        {entity === 'places' && <>
          <label>Category<select {...field('kind')}>{['entrance', 'building', 'library', 'cafe', 'water', 'washroom', 'garden', 'help'].map(k => <option key={k}>{k}</option>)}</select></label>
          <label>Building<select {...field('building_id')}><option value="">No building</option>{options(references.data?.buildings)}</select></label>
          <label>Longitude<input type="number" step="any" min={-180} max={180} {...field('longitude')} required /></label><label>Latitude<input type="number" step="any" min={-90} max={90} {...field('latitude')} required /></label>
        </>}
        {entity === 'departments' && <label className="admin-wide">Associated places<select multiple size={6} value={fields.place_ids ? fields.place_ids.split(',') : []} onChange={e => setFields({ ...fields, place_ids: Array.from(e.target.selectedOptions, o => o.value).join(',') })}>{options(references.data?.places)}</select><small>Select zero or more places. Use Ctrl/Command for multiple choices on desktop.</small></label>}
        {['aliases', 'anchors'].includes(entity) && <label>Place<select {...field('place_id')} required><option value="">Choose a place</option>{options(references.data?.places)}</select></label>}
        {entity === 'aliases' && <>{textField('value', 'Alias')}{textField('language', 'Language code', 16)}</>}
        {entity === 'anchors' && <>
          <label>Find stored node<input value={nodeSearch} onChange={e => { setNodeSearch(e.target.value); setNodeOffset(0) }} maxLength={160} /></label>
          <label>Navigation node<select {...field('node_id')} required><option value="">Choose a stored node</option>{fields.node_id && !nodes.data?.some(n => n.id === fields.node_id) && <option value={fields.node_id}>Selected node · {fields.node_id}</option>}{nodes.data?.map(n => <option key={n.id} value={n.id}>{n.label} · {n.visibility}</option>)}</select></label>
          <div className="admin-actions"><button type="button" disabled={!nodeOffset} onClick={() => setNodeOffset(Math.max(0, nodeOffset - 100))}>Previous nodes</button><button type="button" disabled={(nodes.data?.length ?? 0) < 100} onClick={() => setNodeOffset(nodeOffset + 100)}>Next nodes</button></div>
          <label>Accessibility evidence<select {...field('accessibility_status')}><option value="unknown">Unknown / unverified</option><option value="verified_step_free">Verified step-free</option><option value="not_step_free">Not step-free</option></select><small>Only mark verified when supporting survey evidence exists. Synthetic entries are not real-world certification.</small></label>
          <label className="admin-wide">Verification evidence notes<textarea {...field('accessibility_evidence')} maxLength={2000} rows={3} required={fields.accessibility_status === 'verified_step_free'} /><small>For a verified step-free anchor, record the source, verification date and supporting observations. Synthetic notes must be labelled synthetic.</small></label>
          <label>Anchor availability<select {...field('is_open')}><option value="true">Open</option><option value="false">Closed</option></select></label>
        </>}
      </div></fieldset>
      <ErrorMessage error={error || references.error || nodes.error} />
      {conflict && <div className="admin-notice"><p>Your input is preserved. Load the latest records, compare them, then explicitly reconcile before saving again.</p><button type="button" disabled={busy} onClick={async () => {
        setBusy(true)
        try { const page = await adminApi<CatalogPage>(`${path}/catalog/${entity}?limit=100${initial ? `&resource_id=${initial.id}` : ''}`); setLatest(page) } catch (e) { setError(e) } finally { setBusy(false) }
      }}>Load latest for comparison</button>{latest && <><pre>{JSON.stringify(initial ? latest.items.find(r => r.id === initial.id)?.item.data ?? 'This record was deleted.' : latest.items.map(r => r.item.data), null, 2)}</pre><button type="button" disabled={!!initial && !latest.items.some(r => r.id === initial.id)} onClick={() => { setBaseVersion(latest.revision_version); setError(null); setLatest(null) }}>I have reconciled my input with version {latest.revision_version}</button></>}</div>}
      <div className="admin-actions"><button type="submit" disabled={busy || conflict || (entity !== 'buildings' && references.isPending)}>{busy ? 'Saving…' : 'Save draft record'}</button><button type="button" disabled={busy} onClick={onCancel}>Cancel edit</button></div>
    </form>
  </div>
}
