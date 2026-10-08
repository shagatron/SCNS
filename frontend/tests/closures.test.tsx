import { act, cleanup, render, screen } from '@testing-library/react'
import { onlineManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import { useClosures } from '../src/features/closures/useClosures'

const clients: QueryClient[] = []
const status = { release_id: 'release', closure_overlay_version: 0, checked_at: '2026-10-08T00:00:00Z', next_change_at: null, unresolved_count: 0, items: [] }
function Status({ online = true }: { online?: boolean }) { const value = useClosures('campus', online); return <p>{value.fresh ? `fresh v${value.data?.closure_overlay_version}` : 'unavailable'}</p> }
function mount() { const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client); return { client, ...render(<QueryClientProvider client={client}><Status /></QueryClientProvider>) } }
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.unstubAllGlobals(); vi.useRealTimers(); onlineManager.setOnline(true) })
it('requires a successful current check and picks up overlay changes', async () => {
  let version = 0
  const fetch = vi.fn<typeof globalThis.fetch>().mockImplementation(async () => new Response(JSON.stringify({ ...status, closure_overlay_version: version })))
  vi.stubGlobal('fetch', fetch)
  const { client } = mount()
  await screen.findByText('fresh v0')
  expect(fetch.mock.calls[0][1]?.cache).toBe('no-store')
  version = 1
  await act(async () => { await client.invalidateQueries({ queryKey: ['closures'] }) })
  await screen.findByText('fresh v1')
})
it('does not treat cached data as fresh after a failed check or while offline', async () => {
  let fail = false
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async () => fail ? new Response(JSON.stringify({ error: { code: 'service_unavailable', message: 'Temporary outage' } }), { status: 503 }) : new Response(JSON.stringify(status))))
  const { client, rerender } = mount()
  await screen.findByText('fresh v0')
  fail = true
  await act(async () => { await client.invalidateQueries({ queryKey: ['closures'] }) })
  await screen.findByText('unavailable')
  fail = false
  await act(async () => { await client.invalidateQueries({ queryKey: ['closures'] }) })
  await screen.findByText('fresh v0')
  rerender(<QueryClientProvider client={client}><Status online={false} /></QueryClientProvider>)
  expect(screen.getByText('unavailable')).toBeInTheDocument()
})
