import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import QRStart from '../src/features/qr/QRStart'

vi.mock('../src/app/App', () => ({ default: () => <p>Confirmed route planner</p> }))
const marker = { id: 'marker', campus_id: 'campus', campus_name: 'Synthetic campus', version: 2, release_id: 'release', state: 'active', label: 'Synthetic Gate QR', node_label: 'Gate', node_kind: 'outdoor', node_id: 'node', floor_id: null, floor_label: null, verified_on: '2026-10-08', is_demo: true, message: 'Confirm your physical location; no continuous tracking.' }
const clients: QueryClient[] = []
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client)
  return { client, ...render(<QueryClientProvider client={client}><QRStart /></QueryClientProvider>) }
}
function reply(value: unknown) { return new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } }) }
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.unstubAllGlobals(); window.history.replaceState(null, '', '/') })

it('requires explicit confirmation and loses it on reload/remount', async () => {
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async () => reply(marker)))
  const first = mount()
  await screen.findByRole('button', { name: 'I am at this marker now' })
  expect(screen.queryByText('Confirmed route planner')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'I am at this marker now' }))
  await screen.findByText('Confirmed route planner')
  first.unmount(); mount()
  await screen.findByRole('button', { name: 'I am at this marker now' })
  expect(screen.queryByText('Confirmed route planner')).not.toBeInTheDocument()
})

it('hides the confirmed planner when a marker version or release changes and refuses revocation', async () => {
  let value = { ...marker }
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async () => reply(value)))
  const { client } = mount()
  fireEvent.click(await screen.findByRole('button', { name: 'I am at this marker now' }))
  await screen.findByText('Confirmed route planner')
  value = { ...marker, version: 3, release_id: 'new-release' }
  await act(async () => { await client.invalidateQueries({ queryKey: ['qr'] }) })
  await screen.findByRole('button', { name: 'I am at this marker now' })
  expect(screen.queryByText('Confirmed route planner')).not.toBeInTheDocument()
  value = { ...value, state: 'revoked' }
  await act(async () => { await client.invalidateQueries({ queryKey: ['qr'] }) })
  await screen.findByText(/Marker status: revoked/)
  expect(screen.queryByRole('button', { name: 'I am at this marker now' })).not.toBeInTheDocument()
})

it('connection loss clears prior confirmation even if the current marker stays unchanged', async () => {
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async () => reply(marker)))
  mount()
  fireEvent.click(await screen.findByRole('button', { name: 'I am at this marker now' }))
  await screen.findByText('Confirmed route planner')
  await act(async () => { window.dispatchEvent(new Event('offline')) })
  await waitFor(() => expect(screen.queryByText('Confirmed route planner')).not.toBeInTheDocument())
  await screen.findByRole('button', { name: 'I am at this marker now' })
})


it('an unsuccessful live check clears confirmation even after recovery to the same version', async () => {
  let fail = false
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async () => fail ? new Response(JSON.stringify({ error: { code: 'service_unavailable', message: 'Temporarily unavailable' } }), { status: 503 }) : reply(marker)))
  const { client } = mount()
  fireEvent.click(await screen.findByRole('button', { name: 'I am at this marker now' }))
  await screen.findByText('Confirmed route planner')
  fail = true
  await act(async () => { await client.invalidateQueries({ queryKey: ['qr'] }) })
  await screen.findByRole('alert')
  expect(screen.queryByText('Confirmed route planner')).not.toBeInTheDocument()
  fail = false
  await act(async () => { await client.invalidateQueries({ queryKey: ['qr'] }) })
  await screen.findByRole('button', { name: 'I am at this marker now' })
  expect(screen.queryByText('Confirmed route planner')).not.toBeInTheDocument()
})
