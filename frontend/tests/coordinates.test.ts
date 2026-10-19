import { describe, expect, it } from 'vitest'
import { fromLeaflet, localToLeaflet, toLeaflet } from '../src/features/maps/coordinates'

describe('coordinate adapters', () => {
  it('roundtrips WGS84 longitude/latitude through Leaflet', () => {
    expect(toLeaflet([77.59, 12.97])).toEqual([12.97, 77.59])
    expect(fromLeaflet(toLeaflet([77.59, 12.97]))).toEqual([77.59, 12.97])
  })
  it('rejects out of range or nonfinite positions', () => {
    expect(() => toLeaflet([0, 120])).toThrow()
    expect(() => toLeaflet([NaN, 0])).toThrow()
  })
  it('keeps a separate typed local frame with image-axis inversion', () => {
    expect(localToLeaflet({ frameId: 'floor-1', xPx: 25, yPx: 40 }, 600)).toEqual([560, 25])
    expect(() => localToLeaflet({ frameId: 'floor-1', xPx: 25, yPx: 700 }, 600)).toThrow()
  })
})
