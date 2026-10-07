import { StrictMode, type PropsWithChildren } from 'react'
import { act, cleanup, render, renderHook, screen, waitFor } from '@testing-library/react'
import { focusManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AdminApp from '../src/features/admin/AdminApp'
import { adminApi, type Session } from '../src/features/admin/api'
import { useAdminSession } from '../src/features/admin/useAdminSession'

const identity: Session = { user_id: 'test-user', username: 'test-user', display_name: 'Test user', csrf_token: 'session-bound-test-token', expires_at: '2099-01-01T00:00:00Z', grants: [] }
const clients: QueryClient[] = []
function harness(strict = false) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  clients.push(cache)
  return { cache, wrapper: ({ children }: PropsWithChildren) => strict ? <StrictMode><QueryClientProvider client={cache}>{children}</QueryClientProvider></StrictMode> : <QueryClientProvider client={cache}>{children}</QueryClientProvider> }
}
function reply(status: number, data: unknown) {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
}
const anonymous = () => reply(401, { error: { code: 'authentication_required', message: 'Sign in to continue.' } })
afterEach(() => { cleanup(); clients.splice(0).forEach(cache => cache.clear()); focusManager.setFocused(undefined); vi.unstubAllGlobals() })

describe('admin session lifecycle', () => {
  it('fresh anonymous visit settles on normal login without an expiration message or request loop', async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockImplementation(async () => {
      // Bound a faulty implementation so the regression fails without hanging
      // the runner in an unbounded series of immediately fulfilled requests.
      if (fetch.mock.calls.length > 6) return new Promise<Response>(() => {})
      return anonymous()
    })
    vi.stubGlobal('fetch', fetch)
    const { cache, wrapper } = harness(true)
    render(<AdminApp />, { wrapper })
    await screen.findByRole('heading', { name: 'Admin sign in' })
    await waitFor(() => expect(cache.getQueryData(['admin', 'session'])).toBeNull())
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    await act(async () => { focusManager.setFocused(false); focusManager.setFocused(true) })
    expect(fetch.mock.calls.length).toBeLessThanOrEqual(2)
    expect(cache.isFetching()).toBe(0)
  })

  it('an established session rejected on recheck expires and discards private data', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValueOnce(reply(200, identity)).mockImplementation(async () => anonymous()))
    const { cache, wrapper } = harness()
    const { result } = renderHook(useAdminSession, { wrapper })
    await waitFor(() => expect(result.current.session.data).toEqual(identity))
    cache.setQueryData(['admin', 'private-records'], { restricted: true })
    cache.setQueryData(['public', 'campuses'], ['public-data'])
    await act(async () => { await result.current.session.refetch() })
    expect(result.current.session.data).toBeNull()
    expect(result.current.ended).toBe(true)
    expect(cache.getQueryData(['admin', 'private-records'])).toBeUndefined()
    expect(cache.getQueryData(['public', 'campuses'])).toEqual(['public-data'])
  })

  it('protected 401 cancels an older check and cannot restore a revoked session', async () => {
    let finishOldCheck!: (response: Response) => void
    let checks = 0
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockImplementation(async input => {
      if (String(input).endsWith('/session')) {
        checks++
        if (checks === 1) return reply(200, identity)
        return new Promise<Response>(resolve => { finishOldCheck = resolve })
      }
      return anonymous()
    }))
    const { cache, wrapper } = harness()
    const { result } = renderHook(useAdminSession, { wrapper })
    await waitFor(() => expect(result.current.session.data).toEqual(identity))
    cache.setQueryData(['admin', 'private-records'], { restricted: true })
    let pending!: ReturnType<typeof result.current.session.refetch>
    act(() => { pending = result.current.session.refetch() })
    await waitFor(() => expect(checks).toBe(2))
    await act(async () => { await expect(adminApi('/campuses/test/dashboard')).rejects.toMatchObject({ code: 'authentication_required' }) })
    await act(async () => { finishOldCheck(reply(200, identity)); await pending })
    expect(result.current.session.data).toBeNull()
    expect(result.current.ended).toBe(true)
    expect(cache.getQueryData(['admin', 'private-records'])).toBeUndefined()
    act(() => window.dispatchEvent(new Event('admin-session-ended')))
    expect(result.current.session.data).toBeNull()
  })

  it('CSRF rejection does not end an established session or remove its token', async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValueOnce(reply(200, identity)).mockImplementation(async () => reply(403, { error: { code: 'access_denied', message: 'Invalid CSRF token.' } }))
    vi.stubGlobal('fetch', fetch)
    const { wrapper } = harness()
    const { result } = renderHook(useAdminSession, { wrapper })
    await waitFor(() => expect(result.current.session.data).toEqual(identity))
    await act(async () => { await expect(adminApi('/campuses/test/drafts', { method: 'POST', csrf: identity.csrf_token })).rejects.toMatchObject({ code: 'access_denied' }) })
    expect(result.current.session.data).toEqual(identity)
    expect(result.current.ended).toBe(false)
    expect(fetch.mock.lastCall?.[1]).toMatchObject({ method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': identity.csrf_token } })
  })

  it('login resets the expired state and deliberate logout returns to normal login', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValueOnce(reply(200, identity)).mockImplementation(async () => anonymous()))
    const { cache, wrapper } = harness()
    const { result } = renderHook(useAdminSession, { wrapper })
    await waitFor(() => expect(result.current.session.data).toEqual(identity))
    await act(async () => { await result.current.session.refetch() })
    expect(result.current.ended).toBe(true)
    act(() => result.current.establish(identity))
    expect(result.current.ended).toBe(false)
    expect(result.current.session.data).toEqual(identity)
    cache.setQueryData(['admin', 'private-records'], { restricted: true })
    act(() => result.current.signOut())
    expect(result.current.session.data).toBeNull()
    expect(result.current.ended).toBe(false)
    expect(cache.getQueryData(['admin', 'private-records'])).toBeUndefined()
    await act(async () => { focusManager.setFocused(false); focusManager.setFocused(true) })
    expect(cache.isFetching()).toBe(0)
  })

  it('a cancelled anonymous check cannot expire a newer successful login', async () => {
    let finishCheck!: (response: Response) => void
    const fetch = vi.fn<typeof globalThis.fetch>().mockImplementation(() => new Promise<Response>(resolve => { finishCheck = resolve }))
    vi.stubGlobal('fetch', fetch)
    const { cache, wrapper } = harness()
    const { result } = renderHook(useAdminSession, { wrapper })
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
    act(() => result.current.establish(identity))
    expect(cache.getQueryData(['admin', 'session'])).toEqual(identity)
    await act(async () => { finishCheck(anonymous()) })
    await waitFor(() => expect(result.current.session.data).toEqual(identity))
    expect(result.current.ended).toBe(false)
  })

  it('network failure is reported without claiming that an anonymous session expired', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline')))
    const { wrapper } = harness()
    const { result } = renderHook(useAdminSession, { wrapper })
    await waitFor(() => expect(result.current.session.error).toMatchObject({ code: 'network_error' }))
    expect(result.current.ended).toBe(false)
  })
})
