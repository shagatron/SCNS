import { describe, expect, it } from 'vitest'
import { affected, changes, clone, deleteNode, moveNode, pathEdges, reconcile, setPath, splitPath, type Graph } from '../src/features/admin/graphState'
function graph(): Graph {
  const g: Graph = { revision_version: 1, campus: { name: 'Synthetic', is_demo: true, boundary: { type: 'Polygon', coordinates: [[[0,0],[1,0],[1,1],[0,0]]] } }, frames: { f: {code:'WGS84',kind:'outdoor'} }, places: { p: {name:'Entrance',visibility:'public',point:{coordinates:[0,0]}} }, nodes: {}, edges: {}, anchors: { x: {place_id:'p',node_id:'a',accessibility_status:'unknown',accessibility_evidence:'',is_open:true} } }
  for (const [id, point] of [['a',[0,0]],['b',[.002,0]]] as const) g.nodes[id] = { frame_id:'f',label:id,visibility:'public',evidence:'Synthetic',point:{type:'Point',coordinates:[...point]} }
  setPath(g,'e',{ frame_id:'f',from_node_id:'a',to_node_id:'b',physical_path_id:'path',geometry:{type:'LineString',coordinates:[[0,0],[.001,.001],[.002,0]]},accessibility_status:'verified_step_free',distance_status:'estimated',kind:'walkway',visibility:'public',is_open:true,evidence:'Synthetic; no physical verification' },true)
  return g
}
describe('outdoor graph edits',()=>{
  it('moves all directed endpoints, retains bends, and invalidates verification',()=>{
    const g=graph(), before=clone(g);moveNode(g,'a',[.0001,0])
    for(const e of Object.values(g.edges)){expect(e.accessibility_status).toBe('unknown');expect(e.geometry.coordinates[1]).toEqual([.001,.001]);expect(e.geometry.coordinates[e.from_node_id==='a'?0:2]).toEqual([.0001,0])}
    expect(changes(before,g)).toHaveLength(3)
  })
  it('splits both directions with stable reversed segments and deliberate shared intersection',()=>{
    const g=graph();const intersection=splitPath(g,'e',1)
    expect(Object.keys(g.edges)).toHaveLength(4);expect(g.nodes[intersection].point.coordinates).toEqual([.001,.001])
    const groups=Object.values(g.edges).map(e=>e.physical_path_id);expect(new Set(groups).size).toBe(2)
    for(const id of Object.keys(g.edges)){const paired=pathEdges(g,id);expect(paired).toHaveLength(2);expect(g.edges[paired[0]].geometry.coordinates).toEqual([...g.edges[paired[1]].geometry.coordinates].reverse());expect(g.edges[id].accessibility_status).toBe('unknown')}
    expect(()=>splitPath(g,Object.keys(g.edges)[0],0)).toThrow(/interior/)
  })
  it('does not connect visual crossings or distant existing split nodes automatically',()=>{
    const g=graph();g.nodes.far={...g.nodes.a,point:{type:'Point',coordinates:[.003,.003]}}
    expect(()=>splitPath(g,'e',1,'far')).toThrow(/within 1m/)
    expect(Object.keys(g.nodes)).toHaveLength(3)
  })
  it('previews and explicitly deletes references, and records deletion diffs',()=>{
    const g=graph(),before=clone(g);expect(affected(g,'a').edges).toHaveLength(2);expect(affected(g,'a').anchors).toEqual(['x']);deleteNode(g,'a')
    expect(Object.keys(g.edges)).toHaveLength(0);expect(Object.keys(g.anchors)).toHaveLength(0);expect(changes(before,g)).toHaveLength(4)
  })
  it('merges independent changes while requiring an explicit same-record decision',()=>{
    const base=graph(),mine=clone(base),theirs=clone(base);mine.nodes.a.label='Mine';theirs.nodes.b.label='Theirs';theirs.revision_version=2
    let result=reconcile(base,mine,theirs);expect(result.conflicts).toHaveLength(0);expect(result.merged.nodes.a.label).toBe('Mine');expect(result.merged.nodes.b.label).toBe('Theirs')
    theirs.nodes.a.label='Conflicting';result=reconcile(base,mine,theirs);expect(result.conflicts).toHaveLength(1);expect(result.merged.nodes.a.label).toBe('Conflicting');expect(mine.nodes.a.label).toBe('Mine')
  })
})
