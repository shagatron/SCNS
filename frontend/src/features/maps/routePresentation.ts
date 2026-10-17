import type { Route } from '../../api/client'

// Entrance transitions have floor-local coordinates, not an outdoor line. Only
// use an explicitly shared node's stored outdoor endpoint; never project pixels
// into WGS84 or draw an invented connector across frames.
export function outdoorTransitions(route?: Route) {
  const outdoor = route?.segments.filter(s => s.kind === 'outdoor' && s.geometry) ?? []
  return route?.segments.flatMap(segment => {
    if (segment.kind !== 'entrance_transition') return []
    const entering = outdoor.find(s => s.to_node_id === segment.from_node_id)
    const leaving = outdoor.find(s => s.from_node_id === segment.to_node_id)
    const point = entering?.geometry?.coordinates.at(-1) ?? leaving?.geometry?.coordinates[0]
    return point ? [{ id: segment.edge_id, point, instruction: segment.instruction }] : []
  }) ?? []
}
