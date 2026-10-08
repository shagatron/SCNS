import type { components } from '../../api/generated'

type Schema = components['schemas']
export type Position = [number, number]
export type GraphNode = Schema['GraphNodeFields']
export type GraphEdge = Schema['EdgeFields'] & { distance_m?: number }
export type GraphAnchor = Schema['AnchorFields']
export type Graph = { revision_version: number; campus: { name: string; is_demo: boolean; boundary: { type: 'Polygon'; coordinates: Position[][] } }; nodes: Record<string, GraphNode>; edges: Record<string, GraphEdge>; anchors: Record<string, GraphAnchor>; frames: Record<string, { code: string; kind: string }>; places: Record<string, { name: string; visibility: string; point: { coordinates: Position } }> }
export type Layer = 'nodes' | 'edges' | 'anchors'
export type Change = { entity: Layer; id: string; data?: GraphNode | GraphEdge | GraphAnchor }
export function surfaceDistance(a: Position, b: Position) {
  const radians = Math.PI / 180
  const dLat = (b[1] - a[1]) * radians, dLon = (b[0] - a[0]) * radians
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * radians) * Math.cos(b[1] * radians) * Math.sin(dLon / 2) ** 2
  return 6371008.8 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(Math.max(0, 1 - h)))
}
function canonical(value: unknown): string {
  return JSON.stringify(value, (_, item: unknown) => item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.entries(item).sort(([a],[b]) => a.localeCompare(b))) : item)
}
export const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T
export function plain(value: GraphEdge) { const fields = { ...value }; delete fields.distance_m; return fields }
export function changes(base: Graph, work: Graph): Change[] {
  const result: Change[] = []
  for (const entity of ['nodes', 'edges', 'anchors'] as const) {
    for (const id of new Set([...Object.keys(base[entity]), ...Object.keys(work[entity])])) {
      const before = entity === 'edges' && base.edges[id] ? plain(base.edges[id]) : base[entity][id]
      const after = entity === 'edges' && work.edges[id] ? plain(work.edges[id]) : work[entity][id]
      if (canonical(before) !== canonical(after)) result.push({ entity, id, ...(after ? { data: after } : {}) })
    }
  }
  return result
}
export function moveNode(graph: Graph, id: string, point: Position) {
  graph.nodes[id].point.coordinates = point
  for (const e of Object.values(graph.edges)) {
    if (e.from_node_id === id || e.to_node_id === id) {
      if (e.from_node_id === id) e.geometry.coordinates[0] = point
      if (e.to_node_id === id) e.geometry.coordinates[e.geometry.coordinates.length - 1] = point
      e.accessibility_status = 'unknown'; e.distance_status = 'estimated'; delete e.distance_m
    }
  }
}
export function pathEdges(graph: Graph, id: string) {
  const edge = graph.edges[id]
  return edge ? Object.keys(graph.edges).filter(key => graph.edges[key].physical_path_id === edge.physical_path_id) : []
}
export function setPath(graph: Graph, id: string, edge: GraphEdge, twoWay: boolean) {
  const oldPair = pathEdges(graph, id).find(key => key !== id)
  graph.edges[id] = plain(edge)
  if (twoWay) graph.edges[oldPair ?? crypto.randomUUID()] = { ...clone(plain(edge)), from_node_id: edge.to_node_id, to_node_id: edge.from_node_id, geometry: { type: 'LineString', coordinates: [...clone(edge.geometry.coordinates)].reverse() } }
  else if (oldPair) delete graph.edges[oldPair]
}
export function affected(graph: Graph, id: string) {
  return { edges: Object.keys(graph.edges).filter(k => [graph.edges[k].from_node_id, graph.edges[k].to_node_id].includes(id)), anchors: Object.keys(graph.anchors).filter(k => graph.anchors[k].node_id === id) }
}
export function deleteNode(graph: Graph, id: string) {
  const refs = affected(graph, id)
  for (const key of refs.edges) delete graph.edges[key]
  for (const key of refs.anchors) delete graph.anchors[key]
  delete graph.nodes[id]
}
export function splitPath(graph: Graph, edgeId: string, vertex: number, nodeId?: string) {
  const source = graph.edges[edgeId]
  const points = source.geometry.coordinates
  if (vertex < 1 || vertex >= points.length - 1) throw new Error('Select an interior vertex to split; add a vertex at the desired intersection first.')
  const position = points[vertex] as Position
  const id = nodeId || crypto.randomUUID()
  if (nodeId && surfaceDistance(graph.nodes[nodeId].point.coordinates as Position, position) > 1) throw new Error('The selected intersection node must be within 1m of this vertex. Move/add the vertex deliberately first.')
  if ([source.from_node_id, source.to_node_id].includes(id)) throw new Error('An endpoint cannot be the split node.')
  const point = nodeId ? graph.nodes[nodeId].point.coordinates as Position : position
  if (!nodeId) graph.nodes[id] = { frame_id: source.frame_id, label: 'Unverified intersection', visibility: source.visibility ?? 'public', evidence: 'Editor-created split; source/last verification not recorded.', point: { type: 'Point', coordinates: point } }
  const pair = pathEdges(graph, edgeId)
  const firstPhysical = crypto.randomUUID(), secondPhysical = crypto.randomUUID()
  for (const key of pair) {
    const original = graph.edges[key]
    const reversed = original.from_node_id !== source.from_node_id
    const first = [...clone(points.slice(0, vertex)), point]
    const second = [point, ...clone(points.slice(vertex + 1))]
    const parts = reversed ? [second.reverse(), first.reverse()] : [first, second]
    const physical = reversed ? [secondPhysical, firstPhysical] : [firstPhysical, secondPhysical]
    const targets = [id, original.to_node_id]
    const starts = [original.from_node_id, id]
    delete graph.edges[key]
    parts.forEach((coordinates, n) => { graph.edges[crypto.randomUUID()] = { ...clone(plain(original)), physical_path_id: physical[n], from_node_id: starts[n], to_node_id: targets[n], geometry: { type: 'LineString', coordinates }, distance_status: 'estimated', accessibility_status: 'unknown' } })
  }
  return id
}
export function reconcile(base: Graph, local: Graph, latest: Graph) {
  const merged = clone(latest), conflicts: Change[] = []
  for (const change of changes(base, local)) {
    const entity = change.entity
    const before = entity === 'edges' && base.edges[change.id] ? plain(base.edges[change.id]) : base[entity][change.id]
    const current = entity === 'edges' && latest.edges[change.id] ? plain(latest.edges[change.id]) : latest[entity][change.id]
    if (canonical(before) !== canonical(current) && canonical(current) !== canonical(change.data)) conflicts.push(change)
    else applyChange(merged, change)
  }
  return { merged, conflicts }
}
export function applyChange(graph: Graph, change: Change) {
  const layer = graph[change.entity] as Record<string, GraphNode | GraphEdge | GraphAnchor>
  if (change.data) layer[change.id] = clone(change.data)
  else delete layer[change.id]
}

let memoryGeneration = crypto.randomUUID()
export function recoveryGeneration() { try { return sessionStorage.getItem('scns-private-generation') ?? memoryGeneration } catch { return memoryGeneration } }
export function clearGraphRecovery() { memoryGeneration = crypto.randomUUID(); try { sessionStorage.setItem('scns-private-generation', memoryGeneration); for (const key of Object.keys(sessionStorage)) if (key.startsWith('scns-graph-recovery:') || key.startsWith('scns-admin-view:') || key.startsWith('scns-floor-recovery:') || key.startsWith('scns-indoor-recovery:') || key.startsWith('scns-connections-recovery:')) sessionStorage.removeItem(key) } catch { /* storage may be disabled */ } }
