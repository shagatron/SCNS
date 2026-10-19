import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Route } from '../src/api/client'
import RouteDetails from '../src/features/routing/RouteDetails'

const route: Route = {
  id: 'route', campus_id: 'campus', release_id: 'release-1234', dataset_revision_id: 'revision',
  generated_at: '2026-10-06T09:00:00Z', departure_at: '2026-10-06T09:00:00Z', profile: 'shortest', distance_status: 'complete', cost_mode: 'metric', cost_units: 'metres', closure_overlay_version: 0, schedule_policy: 'static_release_state',
  source_place_id: 'source', destination_place_id: 'dest', source_anchor_id: 'a', destination_anchor_id: 'b',
  distance_m: 140, estimated_duration_s: 100, walking_speed_mps: 1.4, segments: [
    { edge_id: 'e1', from_node_id: 'n1', to_node_id: 'n2', distance_m: 140, kind: 'outdoor', distance_status: 'measured',
      geometry: { type: 'LineString', coordinates: [[0, 0], [.001, .001]] }, instruction: 'Follow the path to Library.' },
  ], arrival_instruction: 'Arrive at Library.', warnings: ['Synthetic campus: not real navigation.'],
}

describe('text route', () => {
  it('renders returned instructions, distance, baseline ETA and disclosure', () => {
    render(<RouteDetails route={route} />)
    expect(screen.getByText('Follow the path to Library.')).toBeInTheDocument()
    expect(screen.getByText('Arrive at Library.')).toBeInTheDocument()
    expect(screen.getByText('140')).toBeInTheDocument()
    expect(screen.getByText('min · estimated')).toBeInTheDocument()
    expect(screen.getByText('Synthetic campus: not real navigation.')).toBeInTheDocument()
  })
  it('handles a successful zero-distance arrival', () => {
    render(<RouteDetails route={{ ...route, distance_m: 0, estimated_duration_s: 0, segments: [] }} />)
    expect(screen.getByRole('heading', { name: 'You’re already there' })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
  })
})

it('reports unknown total distance and ETA and labels directions-only honestly', () => {
  render(<RouteDetails route={{ ...route, distance_m: null, estimated_duration_s: null, known_distance_m: 18, cost_mode: 'directions_only' }} />)
  expect(screen.getByText('Distance unknown')).toBeInTheDocument()
  expect(screen.getByText('ETA unavailable')).toBeInTheDocument()
  expect(screen.getByText(/Known distance subtotal: 18.00m/)).toBeInTheDocument()
  expect(screen.getByText(/not a shortest-distance or fastest route/)).toBeInTheDocument()
})


it('keeps the traversal objective explicit even when a directions-only route has known estimated lengths', () => {
  render(<RouteDetails route={{ ...route, distance_m: 799, cost_mode: 'directions_only', cost_units: 'traversals',
    segments: [{ ...route.segments[0], distance_m: 799, distance_status: 'estimated' }],
    warnings: ['OSM-derived lengths are estimates, not field-survey evidence.'] }} />)
  expect(screen.getByText('799')).toBeInTheDocument()
  expect(screen.getByText(/fewest eligible traversals/)).toBeInTheDocument()
  expect(screen.getByText(/not a shortest-distance or fastest route/)).toBeInTheDocument()
  expect(screen.getByText('OSM-derived lengths are estimates, not field-survey evidence.')).toBeInTheDocument()
})
