import { lazy, Suspense, useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import { adminApi } from './api'
import { ErrorMessage } from './AdminApp'
import { affected, applyChange, changes, clone, deleteNode, moveNode, pathEdges, reconcile, setPath, splitPath, surfaceDistance, type Change, type Graph, type GraphEdge, type Layer, type Position } from './graphState'
const GraphMap = lazy(() => import('./GraphMap'))
type Selection = { layer: Layer; id: string } | null
type Recovery = { base: Graph; work: Graph; past: Graph[]; future: Graph[]; selected: Selection; geometry: string; coordinates: [string, string]; saved: number }
type Diagnostic = { severity: string; code: string; message: string; entity: string; ids: string[] }
type Validation = { revision_version: number; errors: number; warnings: number; diagnostics: Diagnostic[]; truncated: boolean; spatial_warning_limit: number }
type RouteTest = { revision_version: number; found: boolean; distance_m: number | null; edge_ids: string[]; notice: string }
const prefix = 'scns-graph-recovery:'

function restore(key: string, initial: Graph): Recovery {
  try { const saved = JSON.parse(sessionStorage.getItem(key) ?? 'null') as Recovery | null; if (saved && Date.now() - saved.saved < 2 * 60 * 60 * 1000 && saved.base?.nodes && saved.work?.nodes && Array.isArray(saved.past)) return saved } catch { /* malformed/disabled storage */ }
  return { base: clone(initial), work: clone(initial), past: [], future: [], selected: null, geometry: '', coordinates: ['', ''], saved: Date.now() }
}
export function GraphEditor({ path, csrf, editable, userId }: { path: string; csrf: string; editable: boolean; userId: string }) {
  const graph = useQuery({ queryKey: ['admin', path, 'graph'], queryFn: ({ signal }) => adminApi<Graph>(`${path}/graph`, { signal }), retry: false })
  if (graph.isPending) return <p role="status">Loading outdoor draft graph…</p>
  if (!graph.data) return <><ErrorMessage error={graph.error} /><button onClick={() => void graph.refetch()}>Retry graph</button></>
  return <Workspace key={path} initial={graph.data} path={path} csrf={csrf} editable={editable} recoveryKey={`${prefix}${userId}:${path}`} />
}
function Workspace({ initial, path, csrf, editable, recoveryKey }: { initial: Graph; path: string; csrf: string; editable: boolean; recoveryKey: string }) {
  const cache = useQueryClient()
  const [state, setState] = useState(() => editable ? restore(recoveryKey, initial) : restore('', initial))
  const [recovered] = useState(() => editable && state.saved < Date.now() - 100)
  const [storageError, setStorageError] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState('select')
  const [snap, setSnap] = useState(true)
  const [selectedVertex, setSelectedVertex] = useState(1)
  const [splitNode, setSplitNode] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [validation, setValidation] = useState<Validation | null>(null)
  const [route, setRoute] = useState<RouteTest | null>(null)
  const [routeSource, setRouteSource] = useState(''), [routeTarget, setRouteTarget] = useState(''), [profile, setProfile] = useState('shortest')
  const [filter, setFilter] = useState('')
  const [comparison, setComparison] = useState<{ latest: Graph; merged: Graph; conflicts: Change[] } | null>(null)
  const [choices, setChoices] = useState<Record<string, string>>({})
  const graph = state.work, selection = state.selected
  const node = selection?.layer === 'nodes' ? graph.nodes[selection.id] : null
  const edge = selection?.layer === 'edges' ? graph.edges[selection.id] : null
  const anchor = selection?.layer === 'anchors' ? graph.anchors[selection.id] : null
  const pending = changes(state.base, graph)
  const formDirty = !!((node && (state.coordinates[0] !== String(node.point.coordinates[0]) || state.coordinates[1] !== String(node.point.coordinates[1]))) || (edge && state.geometry !== JSON.stringify(edge.geometry.coordinates)))
  const dirty = pending.length > 0 || formDirty
  const stale = initial.revision_version !== state.base.revision_version
  const disabled = !editable || busy || !!comparison
  useEffect(() => {
    if (!editable) return
    let failed = false
    try { if (dirty) sessionStorage.setItem(recoveryKey, JSON.stringify({ ...state, saved: Date.now() })); else sessionStorage.removeItem(recoveryKey) } catch { failed = true }
    const timer = window.setTimeout(() => setStorageError(failed), 0)
    return () => window.clearTimeout(timer)
  }, [state, recoveryKey, editable, dirty])
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = '' } }
    window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  function select(layer: Layer, id: string) {
    if (layer === 'nodes' && mode === 'draw' && edge) { mapClick(graph.nodes[id].point.coordinates as Position); return }
    if (formDirty) { setError(new Error('Apply or reset the coordinate/polyline input before changing selection. Your input is retained.')); return }
    setState(s => ({ ...s, selected: { layer, id }, coordinates: layer === 'nodes' ? graph.nodes[id].point.coordinates.map(String) as [string, string] : ['', ''], geometry: layer === 'edges' ? JSON.stringify(graph.edges[id].geometry.coordinates) : '' }))
    setDeleteConfirm(false); setMode('select'); setError(null); setSelectedVertex(1)
  }
  function edit(action: (next: Graph) => void, newSelection?: Selection) {
    if (disabled) return
    try {
      const next = clone(graph); action(next)
      const sel = newSelection === undefined ? selection : newSelection
      setState(s => ({ ...s, work: next, past: [...s.past.slice(-29), clone(s.work)], future: [], selected: sel, coordinates: sel?.layer === 'nodes' && next.nodes[sel.id] ? next.nodes[sel.id].point.coordinates.map(String) as [string, string] : ['', ''], geometry: sel?.layer === 'edges' && next.edges[sel.id] ? JSON.stringify(next.edges[sel.id].geometry.coordinates) : '' }))
      setError(null); setValidation(null); setRoute(null)
    } catch (e) { setError(e) }
  }
  function addNode(point?: Position) {
    const id = crypto.randomUUID(), frame = Object.keys(graph.frames).find(k => graph.frames[k].kind === 'outdoor')
    if (!frame) { setError(new Error('Import an outdoor coordinate frame before creating nodes.')); return }
    const ring = graph.campus.boundary.coordinates[0]
    const location = point ?? [(ring[0][0] + ring[2][0]) / 2, (ring[0][1] + ring[2][1]) / 2] as Position
    edit(next => { next.nodes[id] = { frame_id: frame, label: 'New unverified node', visibility: 'public', point: { type: 'Point', coordinates: location }, evidence: '' } }, { layer: 'nodes', id }); setMode('select')
  }
  function addEdge() {
    const options = Object.keys(graph.nodes).filter(k => !!graph.nodes[k].point)
    if (options.length < 2) { setError(new Error('Create at least two outdoor nodes first.')); return }
    const from = node && selection ? selection.id : options[0], to = options.find(k => k !== from && graph.nodes[k].frame_id === graph.nodes[from].frame_id)
    if (!to) { setError(new Error('A path needs distinct endpoints in the same outdoor frame.')); return }
    const id = crypto.randomUUID()
    edit(next => setPath(next, id, { frame_id: graph.nodes[from].frame_id, from_node_id: from, to_node_id: to, physical_path_id: crypto.randomUUID(), kind: 'walkway', geometry: { type: 'LineString', coordinates: [graph.nodes[from].point.coordinates, graph.nodes[to].point.coordinates] }, distance_status: 'estimated', accessibility_status: 'unknown', visibility: 'public', is_open: true, evidence: 'Editor draft; source and verification date not recorded.' }, true), { layer: 'edges', id })
  }
  function updateEdge(fields: Partial<GraphEdge>, twoWay = edge && selection ? pathEdges(graph, selection.id).length === 2 : false) {
    if (!edge || !selection) return
    edit(next => setPath(next, selection.id, { ...edge, ...fields }, !!twoWay))
  }
  function mapClick(point: Position) {
    if (disabled || formDirty) return
    const nearest = snap ? Object.entries(graph.nodes).filter(([, n]) => n.point && surfaceDistance(n.point.coordinates as Position, point) < 2).sort(([, a], [, b]) => surfaceDistance(a.point.coordinates as Position, point) - surfaceDistance(b.point.coordinates as Position, point))[0] : null
    const position = nearest?.[1].point.coordinates as Position | undefined ?? point
    if (mode === 'add') { if (nearest) select('nodes', nearest[0]); else addNode(point) }
    if (mode === 'move' && node && selection) edit(next => moveNode(next, selection.id, point))
    if ((mode === 'draw' || mode === 'vertex') && edge) {
      const coords = clone(edge.geometry.coordinates)
      if (mode === 'draw') coords.splice(coords.length - 1, 0, position)
      else if (selectedVertex > 0 && selectedVertex < coords.length - 1) coords[selectedVertex] = position
      else { setError(new Error('Move endpoints with the node controls; select an interior vertex.')); return }
      updateEdge({ geometry: { type: 'LineString', coordinates: coords }, accessibility_status: 'unknown', distance_status: 'estimated' })
    }
  }
  async function compare() {
    setBusy(true); setError(null)
    try { const latest = await adminApi<Graph>(`${path}/graph`); const result = reconcile(state.base, graph, latest); setComparison({ latest, ...result }); setChoices({}) }
    catch (e) { setError(e) } finally { setBusy(false) }
  }
  async function save() {
    if (formDirty) { setError(new Error('Apply the coordinate/polyline input before saving. Your input is retained.')); return }
    setBusy(true); setError(null)
    try {
      const result = await adminApi<Graph>(`${path}/graph`, { method: 'POST', csrf, version: state.base.revision_version, body: { changes: pending } })
      setState({ base: clone(result), work: result, past: [], future: [], selected: null, coordinates: ['', ''], geometry: '', saved: Date.now() }); setValidation(null); setRoute(null)
      await cache.invalidateQueries({ queryKey: ['admin'] })
    } catch (e) { setError(e); if (e instanceof ApiError && e.code === 'conflict') await compare() } finally { setBusy(false) }
  }
  const refs = node && selection ? affected(graph, selection.id) : null
  const sourceNotes = node?.evidence ?? edge?.evidence ?? anchor?.accessibility_evidence ?? ''
  return <section className="admin-card graph-workspace" aria-label="Outdoor graph editor"><h2>Outdoor draft graph editor</h2>
    <p><strong>{graph.campus.is_demo ? 'Synthetic campus — invented geometry; no physical accessibility verification.' : 'Draft campus geometry — field verification required.'}</strong> WGS84 GeoJSON uses [longitude, latitude] degrees. Lengths are recomputed in metres by PostGIS on save. Crossings are separate until deliberately connected.</p>
    <p role="status">{busy ? 'Working…' : dirty ? `Unsaved server changes · ${pending.length} affected records. ${storageError ? 'Recovery unavailable.' : 'Recovery autosaved in this tab.'}` : `Draft saved · version ${state.base.revision_version}.`} {recovered && 'Recovered previous input.'}</p>
    {!editable && <p>Read-only graph access. An editor or campus system administrator must make changes.</p>}
    {storageError && <p role="alert">Browser recovery storage is unavailable or full. Keep this tab open until the server save succeeds.</p>}
    {stale && <p role="alert">Recovered draft version differs from the server. Load latest and reconcile before saving.</p>}
    <ErrorMessage error={error} />
    <div className="admin-actions"><button disabled={disabled || !dirty || pending.length === 0 || pending.length > 500 || !!comparison} onClick={() => void save()}>Save graph to draft</button>
      <button disabled={disabled || !state.past.length || formDirty} onClick={() => { const prior = state.past[state.past.length - 1]; setState(s => ({ ...s, work: prior, past: s.past.slice(0, -1), future: [...s.future, s.work], selected: null, coordinates: ['', ''], geometry: '' })); setValidation(null); setRoute(null) }}>Undo graph action</button>
      <button disabled={disabled || !state.future.length || formDirty} onClick={() => { const next = state.future[state.future.length - 1]; setState(s => ({ ...s, work: next, future: s.future.slice(0, -1), past: [...s.past, s.work], selected: null, coordinates: ['', ''], geometry: '' })); setValidation(null); setRoute(null) }}>Redo graph action</button>
      <button disabled={busy || formDirty} onClick={() => void compare()}>Load latest and reconcile</button>
      <button disabled={!dirty || busy} onClick={() => { if (window.confirm('Discard local graph changes and recovery? This does not modify the server draft.')) { setState({ base: clone(initial), work: clone(initial), past: [], future: [], selected: null, coordinates: ['', ''], geometry: '', saved: Date.now() }); setComparison(null) } }}>Discard local changes</button></div>
    {pending.length > 500 && <p role="alert">A save supports 500 affected records. Undo/reduce this batch before saving.</p>}
    {comparison && <section className="graph-conflicts" aria-label="Graph reconciliation"><h3>Reconcile with draft version {comparison.latest.revision_version}</h3><p>Your local changes remain intact. Independent changes can merge; choose explicitly for every changed record. Server validation still applies.</p>
      {comparison.conflicts.map(change => <div key={`${change.entity}:${change.id}`}><h4>{change.entity} · {change.id}</h4><div className="import-comparison"><div><strong>Latest server</strong><pre>{JSON.stringify(comparison.latest[change.entity][change.id] ?? 'Deleted', null, 2)}</pre></div><div><strong>Your proposed edit</strong><pre>{JSON.stringify(change.data ?? 'Delete', null, 2)}</pre></div></div><label>Conflict resolution {change.id}<select value={choices[change.id] ?? ''} onChange={e => setChoices({ ...choices, [change.id]: e.target.value })}><option value="">Choose explicitly</option><option value="server">Keep server record</option><option value="mine">Keep my proposed edit</option></select></label></div>)}
      <button disabled={comparison.conflicts.some(c => !choices[c.id]) || formDirty} onClick={() => { const merged = clone(comparison.merged); for (const change of comparison.conflicts) if (choices[change.id] === 'mine') applyChange(merged, change); setState(s => ({ ...s, base: comparison.latest, work: merged, past: [], future: [], selected: null, coordinates: ['', ''], geometry: '' })); setComparison(null); setValidation(null); setRoute(null) }}>Use reconciled draft</button><button onClick={() => setComparison(null)}>Keep working on my input</button></section>}
    <div className="admin-actions"><label>Map tool<select value={mode} disabled={disabled} onChange={e => setMode(e.target.value)}><option value="select">Select features</option><option value="add">Add node on map</option><option value="move" disabled={!node}>Move selected node</option><option value="draw" disabled={!edge}>Draw interior path vertices</option><option value="vertex" disabled={!edge}>Move selected vertex</option></select></label><label className="graph-checkbox"><input type="checkbox" checked={snap} onChange={e => setSnap(e.target.checked)} />Snap drawing to existing nodes within 2m</label>
      <button disabled={disabled || formDirty} onClick={() => addNode()}>Add graph node</button><button disabled={disabled || formDirty} onClick={addEdge}>Add path edge</button><button disabled={disabled || !Object.keys(graph.places).length || !Object.keys(graph.nodes).length || formDirty} onClick={() => { const id = crypto.randomUUID(); const nodeId = selection?.layer === 'nodes' ? selection.id : Object.keys(graph.nodes).find(k => graph.nodes[k].visibility === 'public' && graph.nodes[k].point); if (!nodeId) { setError(new Error('Create a public outdoor node before connecting an entrance.')); return } edit(next => { next.anchors[id] = { place_id: Object.keys(graph.places).find(k => graph.places[k].visibility === 'public') ?? Object.keys(graph.places)[0], node_id: nodeId, accessibility_status: 'unknown', accessibility_evidence: '', is_open: true } }, { layer: 'anchors', id }) }}>Connect place entrance</button></div>
    <p>Current tool: {mode}. {mode === 'draw' && 'Click the map to append vertices before the final endpoint.'} {mode === 'vertex' && `Click the map to move vertex ${selectedVertex + 1}.`} Local edits require an explicit server save. Recovery lasts up to two hours in this tab and is cleared on sign out.</p>
    <div className="graph-layout"><Suspense fallback={<p role="status">Loading visual graph…</p>}><GraphMap graph={graph} selected={selection} select={select} click={mapClick} vertex={n => { setSelectedVertex(n); setMode('vertex') }} route={route?.edge_ids ?? []} /></Suspense>
      <div className="graph-inspector"><h3>Selected feature</h3>{!selection && <p>Select a node, path or entrance on the map or below. The graph may be empty; import an outdoor frame and add nodes to begin.</p>}
      {selection && <p className="admin-id">{selection.layer} · {selection.id}</p>}
      {node && selection && <><label>Node label<input disabled={disabled || formDirty} maxLength={160} value={node.label} onChange={e => edit(next => { next.nodes[selection.id].label = e.target.value })} /></label><label>Node visibility<select disabled={disabled || formDirty} value={node.visibility} onChange={e => edit(next => { next.nodes[selection.id].visibility = e.target.value as 'public' | 'restricted' })}><option>public</option><option>restricted</option></select></label>
        <label>Node longitude<input disabled={disabled} value={state.coordinates[0]} inputMode="decimal" onChange={e => setState(s => ({ ...s, coordinates: [e.target.value, s.coordinates[1]] }))} /></label><label>Node latitude<input disabled={disabled} value={state.coordinates[1]} inputMode="decimal" onChange={e => setState(s => ({ ...s, coordinates: [s.coordinates[0], e.target.value] }))} /></label><button disabled={disabled} onClick={() => { const point = state.coordinates.map(Number) as Position; if (state.coordinates.some(v => !v.trim()) || !point.every(Number.isFinite) || Math.abs(point[0]) > 180 || Math.abs(point[1]) > 90) { setError(new Error('Enter finite WGS84 longitude/latitude in degrees.')); return } edit(next => moveNode(next, selection.id, point)) }}>Apply node coordinates</button>
        <label>Node source and last verification notes<textarea disabled={disabled || formDirty} value={node.evidence ?? ''} maxLength={2000} onChange={e => edit(next => { next.nodes[selection.id].evidence = e.target.value })} /></label><p>Moving a node updates all incident paths; their changed geometry becomes unknown for accessibility until verified again.</p></>}
      {edge && selection && <><label>Path from node<select disabled={disabled || formDirty} value={edge.from_node_id} onChange={e => { const id = e.target.value; const coords = clone(edge.geometry.coordinates); coords[0] = graph.nodes[id].point.coordinates; updateEdge({ from_node_id: id, frame_id: graph.nodes[id].frame_id, geometry: { type: 'LineString', coordinates: coords }, accessibility_status: 'unknown' }) }}>{Object.entries(graph.nodes).filter(([,n]) => n.point).map(([id,n]) => <option key={id} value={id}>{n.label} · {id.slice(0,8)}</option>)}</select></label>
        <label>Path to node<select disabled={disabled || formDirty} value={edge.to_node_id} onChange={e => { const id = e.target.value; const coords = clone(edge.geometry.coordinates); coords[coords.length - 1] = graph.nodes[id].point.coordinates; updateEdge({ to_node_id: id, geometry: { type: 'LineString', coordinates: coords }, accessibility_status: 'unknown' }) }}>{Object.entries(graph.nodes).filter(([,n]) => n.point).map(([id,n]) => <option key={id} value={id}>{n.label} · {id.slice(0,8)}</option>)}</select></label>
        <label>Path directions<select disabled={disabled || formDirty} value={pathEdges(graph,selection.id).length === 2 ? 'two' : 'one'} onChange={e => updateEdge({}, e.target.value === 'two')}><option value="two">Two-way · paired stored edges</option><option value="one">One-way · from → to only</option></select></label><label>Path kind<select disabled={disabled || formDirty} value={edge.kind} onChange={e => updateEdge({ kind: e.target.value as GraphEdge['kind'], ...(e.target.value === 'stairs' ? { accessibility_status: 'not_step_free' as const } : {}) })}><option>walkway</option><option>ramp</option><option>stairs</option></select></label>
        <label>Path visibility<select disabled={disabled || formDirty} value={edge.visibility} onChange={e => updateEdge({ visibility: e.target.value as GraphEdge['visibility'] })}><option>public</option><option>restricted</option></select></label><label>Path accessibility<select disabled={disabled || formDirty} value={edge.accessibility_status} onChange={e => updateEdge({ accessibility_status: e.target.value as GraphEdge['accessibility_status'] })}><option value="unknown">Unknown / unverified</option><option value="not_step_free">Not step-free</option><option value="verified_step_free">Verified step-free · evidence required</option></select></label><label className="graph-checkbox"><input type="checkbox" disabled={disabled || formDirty} checked={edge.is_open} onChange={e => updateEdge({ is_open: e.target.checked })} />Open in this draft (no live closure)</label>
        <label>Path distance source<select disabled={disabled || formDirty} value={edge.distance_status} onChange={e => updateEdge({ distance_status: e.target.value as GraphEdge['distance_status'] })}><option>estimated</option><option>measured</option></select></label><label>Path source and last verification notes<textarea disabled={disabled || formDirty} maxLength={2000} value={edge.evidence} onChange={e => updateEdge({ evidence: e.target.value })} /></label><p>Stored length: {edge.distance_m === undefined ? 'pending recalculation on save' : `${edge.distance_m.toFixed(2)}m`}. Physical path: <span className="admin-id">{edge.physical_path_id}</span></p>
        <label>Polyline coordinates [longitude, latitude]<textarea disabled={disabled} rows={5} value={state.geometry} onChange={e => setState(s => ({ ...s, geometry: e.target.value }))} /></label><button disabled={disabled} onClick={() => { try { const coordinates: unknown = JSON.parse(state.geometry); if (!Array.isArray(coordinates) || coordinates.length < 2 || coordinates.length > 500 || coordinates.some(p => !Array.isArray(p) || p.length !== 2 || !p.every((v, i) => typeof v === 'number' && Number.isFinite(v) && Math.abs(v) <= (i === 0 ? 180 : 90)))) throw new Error('Enter 2–500 [longitude, latitude] pairs. Endpoints must match selected nodes.'); updateEdge({ geometry: { type: 'LineString', coordinates: coordinates as Position[] }, accessibility_status: 'unknown', distance_status: 'estimated' }) } catch (e) { setError(e) } }}>Apply polyline coordinates</button>
        <label>Selected path vertex<select value={selectedVertex} onChange={e => setSelectedVertex(Number(e.target.value))}>{edge.geometry.coordinates.map((p,n) => <option key={n} value={n}>Vertex {n+1}: {p.join(', ')}</option>)}</select></label><button disabled={disabled || formDirty || selectedVertex === 0 || selectedVertex >= edge.geometry.coordinates.length - 1} onClick={() => { const coordinates=clone(edge.geometry.coordinates); coordinates.splice(selectedVertex,1); updateEdge({ geometry:{type:'LineString',coordinates},accessibility_status:'unknown',distance_status:'estimated' }); setSelectedVertex(1) }}>Remove selected interior vertex</button>
        <label>Split intersection node<select value={splitNode} onChange={e => setSplitNode(e.target.value)}><option value="">Create unverified node at vertex</option>{Object.entries(graph.nodes).filter(([,n]) => n.point && n.frame_id===edge.frame_id).map(([id,n]) => <option key={id} value={id}>{n.label} · {id.slice(0,8)}</option>)}</select></label><button disabled={disabled || formDirty} onClick={() => edit(next => { splitPath(next,selection.id,selectedVertex,splitNode || undefined) },null)}>Split path at selected vertex</button><p>Split preserves both stored directions. To connect an intersection deliberately, split each crossing path at the same existing node. A visual crossing alone never creates a connection.</p></>}
      {anchor && selection && <><label>Entrance place<select disabled={disabled} value={anchor.place_id} onChange={e => edit(next => { next.anchors[selection.id].place_id=e.target.value })}>{Object.entries(graph.places).map(([id,p]) => <option key={id} value={id}>{p.name}</option>)}</select></label><label>Entrance graph node<select disabled={disabled} value={anchor.node_id} onChange={e => edit(next => { next.anchors[selection.id].node_id=e.target.value })}>{Object.entries(graph.nodes).filter(([,n]) => n.point).map(([id,n]) => <option key={id} value={id}>{n.label} · {id.slice(0,8)}</option>)}</select></label><label>Entrance accessibility<select disabled={disabled} value={anchor.accessibility_status} onChange={e => edit(next => { next.anchors[selection.id].accessibility_status=e.target.value as 'unknown' | 'not_step_free' | 'verified_step_free' })}><option value="unknown">Unknown / unverified</option><option value="not_step_free">Not step-free</option><option value="verified_step_free">Verified step-free · evidence required</option></select></label><label>Entrance source and last verification notes<textarea disabled={disabled} maxLength={2000} value={anchor.accessibility_evidence} onChange={e => edit(next => { next.anchors[selection.id].accessibility_evidence=e.target.value })} /></label><label className="graph-checkbox"><input disabled={disabled} type="checkbox" checked={anchor.is_open} onChange={e => edit(next => { next.anchors[selection.id].is_open=e.target.checked })} />Entrance open in draft</label></>}
      {selection && <><p>Source / last verification: {sourceNotes || 'Not recorded — unverified.'}</p><button disabled={disabled} onClick={() => setState(s => ({ ...s, coordinates: node ? node.point.coordinates.map(String) as [string,string] : ['', ''], geometry: edge ? JSON.stringify(edge.geometry.coordinates) : '' }))}>Reset unapplied coordinate input</button><button disabled={disabled || formDirty} onClick={() => setDeleteConfirm(true)}>Preview graph deletion</button></>}
      {deleteConfirm && selection && <div role="alert"><h4>Explicit draft deletion</h4><p>{refs ? `${refs.edges.length} directed edges and ${refs.anchors.length} entrance anchors will also be removed.` : selection.layer === 'edges' ? `${pathEdges(graph,selection.id).length} stored path directions will be removed.` : 'This entrance anchor will be removed.'} Indoor connectors and QR markers are not implemented. All listed changes are audited together on save.</p>{refs && <ul>{[...refs.edges,...refs.anchors].map(id => <li className="admin-id" key={id}>{id}</li>)}</ul>}<button disabled={disabled} onClick={() => { edit(next => { if (selection.layer==='nodes') deleteNode(next,selection.id); else if (selection.layer==='edges') for (const id of pathEdges(next,selection.id)) delete next.edges[id]; else delete next.anchors[selection.id] },null); setDeleteConfirm(false) }}>Confirm local graph deletion</button><button onClick={() => setDeleteConfirm(false)}>Cancel deletion</button></div>}
    </div></div>
    <section aria-label="Graph feature lists"><h3>Graph features</h3><label>Filter graph features<input value={filter} onChange={e => setFilter(e.target.value)} /></label><div className="graph-lists">{(['nodes','edges','anchors'] as const).map(layer => { const entries=Object.entries(graph[layer]).filter(([id,value]) => JSON.stringify({id,...value,label:layer==='nodes' ? graph.nodes[id].label : layer==='edges' ? `${graph.nodes[graph.edges[id].from_node_id]?.label} → ${graph.nodes[graph.edges[id].to_node_id]?.label}` : `${graph.places[graph.anchors[id].place_id]?.name} entrance`}).toLowerCase().includes(filter.toLowerCase())); return <div key={layer}><h4>{layer} ({entries.length})</h4><ul>{entries.slice(0,100).map(([id]) => <li key={id}><button aria-pressed={selection?.layer===layer && selection.id===id} onClick={() => select(layer,id)}>{layer==='nodes' ? graph.nodes[id].label : layer==='edges' ? `${graph.nodes[graph.edges[id].from_node_id]?.label} → ${graph.nodes[graph.edges[id].to_node_id]?.label}` : `${graph.places[graph.anchors[id].place_id]?.name} entrance`} · {id.slice(0,8)}</button></li>)}</ul>{entries.length>100 && <p>Showing 100; filter by label or full ID to find other features.</p>}</div> })}</div></section>
    <section aria-label="Graph quality"><h3>Graph quality and draft route test</h3><p>Validate saved geometry, references, direction pairs, public and verified step-free connectivity. Validation results become stale after edits.</p><button disabled={busy || dirty} onClick={async () => { setBusy(true); setError(null); try { setValidation(await adminApi<Validation>(`${path}/graph/validation`)) } catch(e) { setError(e) } finally { setBusy(false) } }}>Validate saved graph</button>
      {validation && <><p role="status">Validation version {validation.revision_version}: {validation.errors} errors, {validation.warnings} warnings.</p><ul className="graph-diagnostics">{validation.diagnostics.map((d,n) => <li key={n}><strong>{d.severity} · {d.code}</strong>: {d.message} <span className="admin-id">{d.ids.join(', ')}</span>{(['nodes','edges','anchors'] as string[]).includes(d.entity) && graph[d.entity as Layer][d.ids[0]] && <button onClick={() => select(d.entity as Layer,d.ids[0])}>Inspect diagnostic {n+1}</button>}</li>)}</ul>{validation.truncated && <p>First 500 findings shown. Correct these and rerun.</p>}<p>Spatial warnings are capped at {validation.spatial_warning_limit} pairs per category. Warnings require editor review; this is not a publication approval.</p></>}
      <div className="admin-actions"><label>Draft route start<select value={routeSource} onChange={e => setRouteSource(e.target.value)}><option value="">Choose place</option>{Object.entries(graph.places).filter(([,p])=>p.visibility==='public').map(([id,p])=><option key={id} value={id}>{p.name}</option>)}</select></label><label>Draft route destination<select value={routeTarget} onChange={e => setRouteTarget(e.target.value)}><option value="">Choose place</option>{Object.entries(graph.places).filter(([,p])=>p.visibility==='public').map(([id,p])=><option key={id} value={id}>{p.name}</option>)}</select></label><label>Draft route profile<select value={profile} onChange={e=>setProfile(e.target.value)}><option value="shortest">Standard shortest</option><option value="step_free">Verified step-free</option></select></label><button disabled={busy || dirty || !routeSource || !routeTarget} onClick={async()=>{setBusy(true);setError(null);try { setRoute(await adminApi<RouteTest>(`${path}/graph/route-test?${new URLSearchParams({source:routeSource,target:routeTarget,profile})}`)) }catch(e){setError(e)}finally{setBusy(false)}}}>Compute draft test route</button></div>{route && <p role="status">{route.found ? `Computed draft route: ${route.distance_m?.toFixed(2)}m · ${route.edge_ids.length} stored edges.` : 'No eligible draft route. Check entrances, directionality and unknown accessibility.'} {route.notice}</p>}
    </section>
  </section>
}
