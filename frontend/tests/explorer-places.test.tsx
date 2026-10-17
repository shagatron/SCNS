import { test, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ExplorerPlaces, ExplorerPlaceCard } from '../src/features/public/ExplorerPlaces'
import type { Place, Search } from '../src/api/client'

const place = { id: 'synthetic-place', name: 'Unidentified entrance', code: 'TEST', kind: 'entrance', description: 'Source identity unresolved.', aliases: [], routable: false, point: null } as unknown as Place

test('directory keeps selection and routing actions separate and discloses an unmapped entrance', async () => {
  const select = vi.fn(), route = vi.fn(), start = vi.fn()
  render(<ExplorerPlaces data={{ items: [place], total: 1 } as Search} selected={place.id} pending={false} onSelect={select} onRoute={route} onStart={start} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Select Unidentified entrance' }))
  expect(select).toHaveBeenCalledWith(place); expect(route).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: 'Select Unidentified entrance' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByText('Entrance not mapped')).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Route to Unidentified entrance' }))
  expect(route).toHaveBeenCalledWith(place)
  await user.click(screen.getByRole('button', { name: 'Start at Unidentified entrance' }))
  expect(start).toHaveBeenCalledWith(place)
})

test('selected details focus, close with Escape and preserve unknown identity/access without invented badges', async () => {
  const close = vi.fn(), route = vi.fn(), start = vi.fn()
  render(<ExplorerPlaceCard place={place} pending={false} onClose={close} onRoute={route} onStart={start} />)
  expect(screen.getByRole('region', { name: 'Selected place details' })).toHaveFocus()
  const user = userEvent.setup()
  await user.keyboard('{Escape}'); expect(close).toHaveBeenCalledOnce()
  await user.click(screen.getByText('Place details'))
  expect(screen.getByText(/Accessibility: unknown until surveyed/)).toBeVisible()
  expect(screen.queryByText(/open now|verified entrance|main entrance/i)).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Route here ↗' })); expect(route).toHaveBeenCalledOnce()
  await user.click(screen.getByRole('button', { name: 'Set as start' })); expect(start).toHaveBeenCalledOnce()
})

test('a failed map renderer leaves the text planner mounted with a clear recovery action', async () => {
  const { default: MapFailureBoundary } = await import('../src/features/maps/MapFailureBoundary')
  const errors = vi.spyOn(console, 'error').mockImplementation(() => {})
  function Broken() { throw new Error('Synthetic viewer failure'); return null }
  try {
    render(<><p>Text directions still available</p><MapFailureBoundary><Broken /></MapFailureBoundary></>)
    expect(screen.getByRole('alert')).toHaveTextContent('Map viewer unavailable')
    expect(screen.getByText('Text directions still available')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Reload map viewer' })).toBeEnabled()
  } finally { errors.mockRestore() }
})
