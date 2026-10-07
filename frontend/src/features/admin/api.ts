import { ApiError } from '../../api/client'
import type { components } from '../../api/generated'

type Schema = components['schemas']
export type Session = Schema['SessionOut']
export type Dashboard = Schema['DashboardOut']
export type CatalogPage = Schema['CatalogPage']
export type CatalogRecord = Schema['CatalogRecord']
export type CatalogWrite = CatalogRecord['item']
export type Entity = CatalogWrite['entity']
export type Draft = Schema['DraftOut']
export type Audit = Schema['AuditOut']
export type User = Schema['UserOut']
export type Role = Schema['RoleInput']['role']
export type NodeOption = Schema['NodeOption']

export async function adminApi<T>(path: string, options: { method?: string; body?: unknown; csrf?: string; version?: number; signal?: AbortSignal } = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api/v1/admin${path}`, {
      method: options.method ?? 'GET', credentials: 'same-origin', signal: options.signal,
      headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.csrf ? { 'X-CSRF-Token': options.csrf } : {}), ...(options.version ? { 'If-Match': `"${options.version}"` } : {}) },
      body: options.body ? JSON.stringify(options.body) : undefined,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('network_error', 'Cannot reach administration. Check your connection and retry.')
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    if (!options.signal?.aborted && response.status === 401 && path !== '/login' && path !== '/session') window.dispatchEvent(new Event('admin-session-ended'))
    throw new ApiError(data?.error?.code ?? 'service_unavailable', data?.error?.message ?? 'Administration is unavailable.', data?.error?.request_id)
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}

export async function allRecords(path: string, signal?: AbortSignal): Promise<CatalogRecord[]> {
  const items: CatalogRecord[] = []
  for (let offset = 0; offset <= 10000; offset += 100) {
    const page = await adminApi<CatalogPage>(`${path}?limit=100&offset=${offset}`, { signal })
    items.push(...page.items)
    if (items.length >= page.total) break
  }
  return items
}
export function recordName(record: CatalogRecord, places?: Map<string, string>): string {
  const data = record.item.data
  if ('name' in data) return `${data.code} · ${data.name}`
  if ('value' in data) return `${data.value} (${data.language ?? 'en'})`
  return `${places?.get(data.place_id) ?? data.place_id} · Anchor · ${data.accessibility_status ?? 'unknown'} · ${data.is_open ? 'open' : 'closed'}`
}
