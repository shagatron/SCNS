import { expect, test } from 'vitest'
import type { Route } from '../src/api/client'
import { outdoorTransitions } from '../src/features/maps/routePresentation'

test('entrance markers use exact shared-node outdoor endpoints in both directions', () => {
  const entering = { segments: [{ kind:'outdoor', from_node_id:'gate',to_node_id:'entrance',geometry:{coordinates:[[1,2],[3,4]]} },{kind:'entrance_transition',edge_id:'entry',from_node_id:'entrance',to_node_id:'door',from_local_point:null,to_local_point:{x_px:300,y_px:200},instruction:'Enter the building.'}] } as unknown as Route
  expect(outdoorTransitions(entering)).toEqual([{id:'entry',point:[3,4],instruction:'Enter the building.'}])
  const leaving = {segments:[{kind:'entrance_transition',edge_id:'exit',from_node_id:'door',to_node_id:'entrance',instruction:'Exit the building.'},{kind:'outdoor',from_node_id:'entrance',to_node_id:'gate',geometry:{coordinates:[[3,4],[1,2]]}}]} as unknown as Route
  expect(outdoorTransitions(leaving)).toEqual([{id:'exit',point:[3,4],instruction:'Exit the building.'}])
})

test('missing shared geometry never invents an outdoor marker from indoor pixels or proximity', () => {
  const route = {segments:[{kind:'outdoor',from_node_id:'other',to_node_id:'unrelated',geometry:{coordinates:[[1,2],[3,4]]}},{kind:'entrance_transition',edge_id:'entry',from_node_id:'entrance',to_node_id:'door',to_local_point:{x_px:300,y_px:200}}]} as unknown as Route
  expect(outdoorTransitions(route)).toEqual([])
  expect(outdoorTransitions()).toEqual([])
})
