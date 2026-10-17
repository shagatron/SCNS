import { test, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

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
