import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import OutdoorLocation from '../src/features/location/OutdoorLocation'
const props = { campus: 'campus', release: 'release', overlay: 0, profile: 'shortest' as const, ready: true }
afterEach(() => vi.unstubAllGlobals())
function setup(position: unknown = { coords: { latitude: .0002, longitude: .00015, accuracy: 5 }, timestamp: Date.now() }, code?: number) {
  const geolocation = { getCurrentPosition: vi.fn((success: (value: unknown) => void, failure: (value: { code: number }) => void, options?: PositionOptions) => { void options; return code ? failure({ code }) : success(position) }) }
  vi.stubGlobal('navigator', { geolocation })
  vi.stubGlobal('isSecureContext', true)
  const fetch = vi.fn<typeof globalThis.fetch>().mockImplementation(async input => new Response(JSON.stringify(String(input).endsWith('/location-policy') ? { max_accuracy_m: 20, max_age_seconds: 60 } : { release_id: 'release', closure_overlay_version: 0, accuracy_m: 5, expires_at: new Date(Date.now() + 60000).toISOString(), candidates: [{ node_id: 'node', label: 'Gate', approach_distance_m: 0, path_distance_m: 0 }] })))
  vi.stubGlobal('fetch', fetch)
  const confirm = vi.fn(), invalidate = vi.fn()
  const view = render(<OutdoorLocation {...props} onConfirm={confirm} onInvalidate={invalidate} />)
  return { geolocation, fetch, confirm, invalidate, ...view }
}
it('does not request permission or send observations before explicit action; requires landmark confirmation', async () => {
  const { geolocation, fetch, confirm } = setup()
  expect(geolocation.getCurrentPosition).not.toHaveBeenCalled(); expect(fetch).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: 'Use my location' }))
  await screen.findByRole('button', { name: 'I am at this landmark now' })
  expect(confirm).not.toHaveBeenCalled(); expect(geolocation.getCurrentPosition).toHaveBeenCalledTimes(1)
  expect(geolocation.getCurrentPosition.mock.calls[0][2]).toEqual({ enableHighAccuracy: true, maximumAge: 0, timeout: 10000 })
  await userEvent.click(screen.getByRole('button', { name: 'I am at this landmark now' }))
  expect(confirm.mock.calls[0][0]).toMatchObject({ kind: 'gps', confirmed_node_id: 'node', confirmed: true })
  expect(screen.getByText(/straight-line approach is unverified/)).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: 'Discard location' }))
  expect(screen.queryByRole('button', { name: 'I am at this landmark now' })).not.toBeInTheDocument()
})
it.each([[1, 'permission denied'], [2, 'unavailable'], [3, 'timed out']])('handles browser error %i with fallback', async (code, message) => {
  const { confirm } = setup(undefined, code as number)
  await userEvent.click(screen.getByRole('button', { name: 'Use my location' }))
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(message))
  expect(confirm).not.toHaveBeenCalled(); expect(screen.getByRole('alert')).toHaveTextContent('manual/QR')
})
it.each([
  [{ coords: { latitude: .0002, longitude: .00015, accuracy: 100 }, timestamp: Date.now() }, 'exceeds'],
  [{ coords: { latitude: .0002, longitude: .00015, accuracy: 5 }, timestamp: Date.now() - 120000 }, 'stale'],
  [{ coords: { latitude: NaN, longitude: .00015, accuracy: 5 }, timestamp: Date.now() }, 'Invalid location'],
])('rejects invalid observation locally without transmitting it', async (position, message) => {
  const { fetch, confirm } = setup(position)
  await userEvent.click(screen.getByRole('button', { name: 'Use my location' }))
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(message))
  expect(fetch).toHaveBeenCalledTimes(1); expect(confirm).not.toHaveBeenCalled()
})

it('ignores late browser callbacks after navigation/unmount without sending coordinates', async () => {
  const { geolocation, fetch, unmount } = setup()
  let late: ((value: unknown) => void) | undefined
  geolocation.getCurrentPosition.mockImplementationOnce(success => { late = success })
  await userEvent.click(screen.getByRole('button', { name: 'Use my location' }))
  await waitFor(() => expect(geolocation.getCurrentPosition).toHaveBeenCalledTimes(1))
  unmount(); late?.({ coords: { latitude: .0002, longitude: .00015, accuracy: 5 }, timestamp: Date.now() })
  expect(fetch).toHaveBeenCalledTimes(1)
})
it('expires a proposal and handles unsupported contexts without retaining a fix', async () => {
  const { fetch, invalidate } = setup()
  fetch.mockImplementation(async input => new Response(JSON.stringify(String(input).endsWith('/location-policy') ? { max_accuracy_m: 20, max_age_seconds: 60 } : { release_id: 'release', closure_overlay_version: 0, accuracy_m: 5, expires_at: new Date(Date.now() + 100).toISOString(), candidates: [{ node_id: 'node', label: 'Gate', approach_distance_m: 0, path_distance_m: 0 }] })))
  await userEvent.click(screen.getByRole('button', { name: 'Use my location' }))
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('confirmation ended'))
  expect(invalidate).toHaveBeenCalledTimes(2)
  vi.stubGlobal('isSecureContext', false)
  await userEvent.click(screen.getByRole('button', { name: 'Use my location' }))
  expect(screen.getByRole('alert')).toHaveTextContent('unavailable in this browser/context')
})
