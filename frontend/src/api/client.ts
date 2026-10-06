import type { components } from './generated'

export type Campus = components['schemas']['CampusOut']
export type Place = components['schemas']['PlaceOut']
export type Release = components['schemas']['ReleaseOut']
export type Search = components['schemas']['SearchOut']
export type MapData = components['schemas']['MapOut']
export type Route = components['schemas']['RouteOut']
export type RouteRequest = components['schemas']['RouteRequest']

export class ApiError extends Error {
  constructor(public code: string, message: string, public requestId?: string) { super(message) }
}

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api/v1${path}`, options)
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('network_error', 'Cannot reach campus data. Check your connection and try again.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(body?.error?.code ?? 'service_unavailable', body?.error?.message ?? 'Campus data is temporarily unavailable.', body?.error?.request_id)
  }
  return response.json() as Promise<T>
}

export function calculateRoute(body: RouteRequest): Promise<Route> {
  return api('/routes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}
