export type Pixel = { x: number; y: number }
export function pixelToMap(point: Pixel, height: number): [number, number] {
  if (!Number.isFinite(point.x) || !Number.isFinite(point.y) || point.x < 0 || point.y < 0 || point.y > height || height <= 0) throw new Error('Invalid floor-local pixels')
  return [height - point.y, point.x]
}
export function mapToPixel(lat: number, lng: number, width: number, height: number): Pixel {
  const point = { x: lng, y: height - lat }
  pixelToMap(point, height)
  if (point.x > width) throw new Error('Point is outside the reference plan')
  return point
}
export function lineMetres(a: Pixel, b: Pixel, scale: number | null): number | null {
  if (scale === null) return null
  if (!Number.isFinite(scale) || scale <= 0) throw new Error('A verified positive scale is required')
  return Math.hypot(b.x - a.x, b.y - a.y) * scale
}
