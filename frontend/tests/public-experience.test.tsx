import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { CampusOpening, CampusOverview } from '../src/features/public/PublicExperience'
import { focusPlanner } from '../src/features/public/focusPlanner'
import type { Campus, MapData, Search } from '../src/api/client'
const initial: Search = { items: [], total: 124, release_id: 'published', limit: 100, offset: 0 }
const map: MapData = { type: 'FeatureCollection', release_id: 'published', truncated: false, features: [{ type: 'Feature', id: 'building', properties: { layer: 'building' }, geometry: { type: 'Polygon', coordinates: [] } }] }
it('uses published totals rather than the current page size and omits unknown counts', () => {
  render(<CampusOverview initial={initial} />)
  expect(screen.getByText('124')).toBeInTheDocument()
  expect(screen.queryByText('Mapped buildings')).not.toBeInTheDocument()
  expect(screen.queryByText('Published floors')).not.toBeInTheDocument()
})
it('shows complete published footprint/floor counts and refuses a truncated building count', () => {
  const { rerender } = render(<CampusOverview initial={initial} map={map} floors={{ release_id: 'published', floors: [] }} />)
  expect(screen.getByText('Mapped buildings')).toBeInTheDocument()
  expect(screen.getByText('0')).toBeInTheDocument()
  rerender(<CampusOverview initial={initial} map={{ ...map, truncated: true }} />)
  expect(screen.queryByText('Mapped buildings')).not.toBeInTheDocument()
})
it('discloses synthetic data only for the selected synthetic campus, with no empty-campus invented counts', () => {
  const campus = { id: 'id', name: 'Published campus', is_demo: true } as Campus
  const { rerender } = render(<CampusOpening campus={campus} campuses={[campus]} locked={false} onCampus={() => {}} online connected />)
  expect(screen.getByText('Synthetic demo.')).toBeInTheDocument()
  rerender(<CampusOpening campus={{ ...campus, is_demo: false }} campuses={[campus]} locked={false} onCampus={() => {}} online connected />)
  expect(screen.queryByText('Synthetic demo.')).not.toBeInTheDocument()
  rerender(<CampusOpening campuses={[]} locked={false} onCampus={() => {}} online connected />)
  expect(screen.getByRole('option', { name: 'No published campus' })).toBeInTheDocument()
})
it('opens collapsed controls before choosing a directory route destination', async () => {
  render(<details className="route-controls"><summary>Route controls</summary><select id="destination" aria-label="Destination"><option>Library</option></select></details>)
  expect(document.querySelector('details')?.open).toBe(false)
  focusPlanner('destination')
  await new Promise(resolve => requestAnimationFrame(resolve))
  expect(document.querySelector('details')?.open).toBe(true)
  expect(screen.getByLabelText('Destination')).toHaveFocus()
})
