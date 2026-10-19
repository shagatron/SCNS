import { describe, expect, it } from 'vitest'
import fixture from '../../data/demo/indoor-routing/connections.json'
import { changes, clone, fresh, reconcile, remove, restore, reverse, type Data } from '../src/features/admin/connectionsState'
import { clearGraphRecovery, recoveryGeneration } from '../src/features/admin/graphState'
const initial = () => ({ ...clone(fixture.records), revision_version: 1, status: 'draft', campus: { is_demo: true }, buildings: {}, floors: { '$GROUND': { layer_id: '$GROUND_LAYER' } }, nodes: {}, anchors: {} }) as unknown as Data

describe('explicit connection edits', () => {
  it('pairs shared attributes without inventing geometry or unknown costs', () => { const s = initial(), id = Object.keys(s.paths)[0]; s.paths[id].distance_m = null; s.paths[id].distance_status = 'unknown'; reverse(s, { entity: 'paths', id }, true); const other = Object.entries(s.paths).find(([key, p]) => key !== id && p.physical_path_id === s.paths[id].physical_path_id)![1]; expect(other.distance_m).toBeNull(); expect(other.from_stop_id).toBe(s.paths[id].to_stop_id); expect(other.vertical_rise_m).toBeNull(); reverse(s, { entity: 'paths', id }, false); expect(Object.values(s.paths).filter(p => p.physical_path_id === s.paths[id].physical_path_id)).toHaveLength(1) })
  it('previews explicit dependent deletion and remains reversible', () => { const base = initial(), work = clone(base), id = Object.keys(work.connectors)[0]; remove(work, { entity: 'connectors', id }); expect(Object.values(work.stops).some(s => s.connector_id === id)).toBe(false); expect(Object.values(work.paths).some(s => s.connector_id === id)).toBe(false); expect(changes(base, work).length).toBeGreaterThan(1); expect(base.connectors[id]).toBeDefined() })
  it('merges independent records and requires choices for a concurrently changed record', () => { const base = initial(), mine = clone(base), latest = clone(base), ids = Object.keys(base.connectors); mine.connectors[ids[0]].label = 'Mine'; latest.connectors[ids[1]].label = 'Independent'; const result = reconcile(base, mine, latest); expect(result.conflicts).toEqual([]); expect(result.merged.connectors[ids[0]].label).toBe('Mine'); expect(result.merged.connectors[ids[1]].label).toBe('Independent'); latest.connectors[ids[0]].label = 'Concurrent'; expect(reconcile(base, mine, latest).conflicts).toHaveLength(1); latest.floors.$GROUND.layer_id = 'different'; expect(reconcile(base, mine, latest).changedPlans).toEqual(['$GROUND']) })
  it('recovers raw invalid fields and clears private recovery at logout', () => { const base = initial(), saved = fresh(base); saved.form = { distance_m: 'unfinished-number' }; sessionStorage.setItem('scns-connections-recovery:test', JSON.stringify(saved)); expect(restore('scns-connections-recovery:test', base).form.distance_m).toBe('unfinished-number'); const generation = recoveryGeneration(); clearGraphRecovery(); expect(recoveryGeneration()).not.toBe(generation); expect(sessionStorage.getItem('scns-connections-recovery:test')).toBeNull() })
})

it('retains unresolved record and raw-field decisions through reload and rejects corrupt context', () => {
  const base = initial(), state = fresh(base), id = Object.keys(base.connectors)[0]
  state.conflicts = [{ entity: 'connectors', id, data: { ...base.connectors[id], label: 'Retained mine' } }]
  state.selected = { entity: 'connectors', id }; state.rawConflict = state.selected; state.form = { label: 'Retained raw input' }
  sessionStorage.setItem('connection-decisions', JSON.stringify(state))
  const recovered = restore('connection-decisions', base)
  expect(recovered.conflicts?.[0].data && 'label' in recovered.conflicts[0].data && recovered.conflicts[0].data.label).toBe('Retained mine')
  expect(recovered.rawConflict).toEqual(state.selected)
  sessionStorage.setItem('connection-decisions', JSON.stringify({ ...state, work: { connectors: {} } }))
  expect(restore('connection-decisions', base).conflicts).toBeUndefined()
  sessionStorage.removeItem('connection-decisions')
})
