import type { components } from '../../api/generated'
import { clone } from './graphState'
export { clone }
type S = components['schemas']
export type Room = Required<S['RoomFields']>
export type Node = Required<S['IndoorNodeFields']>
export type Edge = Required<S['IndoorEdgeFields']>
export type Access = Required<S['IndoorAccessFields']>
export type Layer = 'rooms' | 'nodes' | 'edges' | 'access'
export type RecordValue = Room | Node | Edge | Access
export type Point = [number, number]
export type Indoor = { revision_version: number; status: string; campus: { name: string; is_demo: boolean }; ready: boolean; prerequisite_error: string | null; floor: { id: string; label: string; building_id: string; layer_id: string | null; frame_id: string | null; width_px: number | null; height_px: number | null; metres_per_pixel: number | null }; departments: Record<string, string>; metrics: Record<string, { distance_m: number | null; distance_status: string }>; rooms: Record<string, Room>; nodes: Record<string, Node>; edges: Record<string, Edge>; access: Record<string, Access> }
export type Selection = { entity: Layer; id: string } | null
export type Change = { entity: Layer; id: string; data?: RecordValue }
export const layers: Layer[] = ['rooms', 'nodes', 'edges', 'access']
export const evidence = () => ({ visibility: 'public' as const, evidence: '', verified_on: null })
export function key(c: { entity: string; id: string }) { return `${c.entity}:${c.id}` }
function canonical(v: unknown) { return JSON.stringify(v, (_, item: unknown) => item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b))) : item) }
export function changes(base: Indoor, work: Indoor) {
  const result: Change[] = []
  for (const entity of layers) for (const id of new Set([...Object.keys(base[entity]), ...Object.keys(work[entity])])) {
    if (canonical(base[entity][id]) !== canonical(work[entity][id])) result.push({ entity, id, ...(work[entity][id] ? { data: work[entity][id] } : {}) })
  }
  return result
}
export function applyChange(work: Indoor, change: Change) { const records = work[change.entity] as Record<string, RecordValue>; if (change.data) records[change.id] = clone(change.data); else delete records[change.id] }
export function reconcile(base: Indoor, work: Indoor, latest: Indoor) {
  const merged = clone(latest), conflicts: Change[] = []
  for (const change of changes(base, work)) {
    if (canonical(base[change.entity][change.id]) !== canonical(latest[change.entity][change.id]) && canonical(change.data) !== canonical(latest[change.entity][change.id])) conflicts.push(change)
    else applyChange(merged, change)
  }
  return { merged, conflicts, changedPlan: base.floor.layer_id !== latest.floor.layer_id || base.floor.frame_id !== latest.floor.frame_id }
}
export function point(n: { x_px: number; y_px: number }): Point { return [n.x_px, n.y_px] }
export function length(points: number[][], scale: number | null) { if (scale === null) return null; if (!Number.isFinite(scale) || scale <= 0) throw new Error('Scale must be approved and positive'); return points.slice(1).reduce((sum, b, i) => sum + Math.hypot(b[0] - points[i][0], b[1] - points[i][1]), 0) * scale }
export function pair(work: Indoor, id: string) { return Object.keys(work.edges).filter(k => work.edges[k].physical_path_id === work.edges[id]?.physical_path_id) }
function unverify(e: Edge) { e.verified_on = null; e.accessibility_status = 'unknown'; e.width_m = null; e.slope_percent = null; e.step_count = null; e.surface = null }
export function moveNode(work: Indoor, id: string, p: Point) {
  Object.assign(work.nodes[id], { x_px: p[0], y_px: p[1], verified_on: null })
  for (const e of Object.values(work.edges)) if ([e.from_node_id, e.to_node_id].includes(id)) { e.polyline[e.from_node_id === id ? 0 : e.polyline.length - 1] = p; unverify(e) }
  for (const a of Object.values(work.access)) if (a.node_id === id) { a.verified_on = null; a.accessibility_status = 'unknown' }
}
export function setPath(work: Indoor, id: string, edge: Edge, twoWay: boolean) {
  const reverse = pair(work, id).find(k => k !== id)
  work.edges[id] = clone(edge)
  if (twoWay) work.edges[reverse ?? crypto.randomUUID()] = { ...clone(edge), from_node_id: edge.to_node_id, to_node_id: edge.from_node_id, polyline: clone(edge.polyline).reverse() }
  else if (reverse) delete work.edges[reverse]
}
export function remove(work: Indoor, selection: NonNullable<Selection>) {
  if (selection.entity === 'nodes') { for (const [id, e] of Object.entries(work.edges)) if ([e.from_node_id, e.to_node_id].includes(selection.id)) delete work.edges[id]; for (const [id, a] of Object.entries(work.access)) if (a.node_id === selection.id) delete work.access[id] }
  if (selection.entity === 'rooms') for (const [id, a] of Object.entries(work.access)) if (a.room_id === selection.id) delete work.access[id]
  if (selection.entity === 'edges') for (const id of pair(work, selection.id)) delete work.edges[id]
  delete work[selection.entity][selection.id]
}
export function split(work: Indoor, edgeId: string, vertex: number, existing?: string) {
  const edge = work.edges[edgeId], points = edge.polyline
  if (!Number.isInteger(vertex) || vertex <= 0 || vertex >= points.length - 1) throw new Error('Choose an interior vertex; insert one at the intended intersection first.')
  const id = existing || crypto.randomUUID(), p = existing ? point(work.nodes[existing]) : points[vertex] as Point
  if (existing && (!work.nodes[existing] || Math.hypot(p[0] - points[vertex][0], p[1] - points[vertex][1]) > 2)) throw new Error('Existing junction must be within 2 reference pixels of this vertex.')
  if ([edge.from_node_id, edge.to_node_id].includes(id)) throw new Error('Split junction cannot be an endpoint.')
  if (!existing) work.nodes[id] = { ...evidence(), visibility: edge.visibility, kind: 'junction', label: 'Unverified split junction', x_px: p[0], y_px: p[1] }
  const first = [...clone(points.slice(0, vertex)), p], second = [p, ...clone(points.slice(vertex + 1))], physical = [crypto.randomUUID(), crypto.randomUUID()]
  for (const eid of pair(work, edgeId)) {
    const old = work.edges[eid], reversed = old.from_node_id !== edge.from_node_id, parts = reversed ? [clone(second).reverse(), clone(first).reverse()] : [first, second]
    delete work.edges[eid]
    parts.forEach((polyline, i) => { const next = { ...clone(old), physical_path_id: physical[reversed ? 1 - i : i], from_node_id: i ? id : old.from_node_id, to_node_id: i ? old.to_node_id : id, polyline }; unverify(next); work.edges[crypto.randomUUID()] = next })
  }
  return id
}
export type Recovery = { base: Indoor; work: Indoor; past: Indoor[]; future: Indoor[]; selected: Selection; coordinates: [string, string]; geometry: string; alias: string; saved: number }
export function fresh(initial: Indoor): Recovery { return { base: clone(initial), work: clone(initial), past: [], future: [], selected: null, coordinates: ['', ''], geometry: '', alias: '', saved: Date.now() } }
export function restore(key: string, initial: Indoor): Recovery {
  try { const raw = sessionStorage.getItem(key); if (raw && raw.length <= 2_000_000) { const saved = JSON.parse(raw) as Recovery; if (Date.now() - saved.saved < 7_200_000 && saved.base.floor.id === initial.floor.id && layers.every(l => saved.work[l] && saved.base[l]) && Array.isArray(saved.past) && Array.isArray(saved.future) && saved.coordinates?.length === 2) return saved } } catch { /* Corrupt/disabled recovery leaves the server data intact. */ }
  return fresh(initial)
}
