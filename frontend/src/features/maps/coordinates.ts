export type GeographicPosition = readonly [longitude: number, latitude: number]
export type LocalPosition = { frameId: string; xPx: number; yPx: number }

export function toLeaflet([longitude, latitude]: GeographicPosition): [number, number] {
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude) || Math.abs(longitude) > 180 || Math.abs(latitude) > 90) {
    throw new Error('Invalid WGS84 position')
  }
  return [latitude, longitude]
}

export function fromLeaflet([latitude, longitude]: readonly [number, number]): GeographicPosition {
  toLeaflet([longitude, latitude])
  return [longitude, latitude]
}

export function localToLeaflet(point: LocalPosition, heightPx: number): [number, number] {
  if (![point.xPx, point.yPx, heightPx].every(Number.isFinite) || heightPx <= 0 || point.xPx < 0 || point.yPx < 0 || point.yPx > heightPx) {
    throw new Error('Point outside local image frame')
  }
  return [heightPx - point.yPx, point.xPx]
}
