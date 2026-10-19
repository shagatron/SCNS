import { afterEach, expect, it, vi } from 'vitest'
import { api, ApiError } from '../src/api/client'
afterEach(() => vi.unstubAllGlobals())

it('preserves domain error codes and safe request correlation', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'no_route', message: 'No route available.', request_id: 'trace' } }), { status: 422 })))
  await expect(api('/routes')).rejects.toMatchObject({ code: 'no_route', message: 'No route available.', requestId: 'trace' })
})

it('explains network failures without inventing a route', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fetch failed')))
  await expect(api('/routes')).rejects.toBeInstanceOf(ApiError)
  await expect(api('/routes')).rejects.toMatchObject({ code: 'network_error' })
})
