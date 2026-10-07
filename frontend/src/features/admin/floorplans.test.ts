import { describe, expect, it } from 'vitest'
import { lineMetres, mapToPixel, pixelToMap } from './floorplanCoordinates'
import { readFloorRecovery, saveFloorRecovery } from './floorRecovery'
import { clearGraphRecovery } from './graphState'

describe('floor-local coordinate and recovery boundaries', () => {
  it('inverts y only at the map adapter; calibrated pixels use the known scale', () => {
    const point = { x: 100, y: 100 }
    expect(pixelToMap(point, 400)).toEqual([300, 100])
    expect(mapToPixel(300, 100, 600, 400)).toEqual(point)
    expect(lineMetres(point, { x: 300, y: 100 }, .05)).toBe(10)
    expect(lineMetres(point, { x: 300, y: 100 }, null)).toBeNull()
  })
  it('rejects invalid/outside map clicks instead of inventing coordinates or scale', () => {
    expect(() => mapToPixel(100, 700, 600, 400)).toThrow()
    expect(() => pixelToMap({ x: 100, y: 500 }, 400)).toThrow()
    expect(() => lineMetres({ x: 0, y: 0 }, { x: 1, y: 1 }, -1)).toThrow()
  })
  it('ignores corrupted and expired recovery instead of crashing the floor form', () => {
    sessionStorage.setItem('scns-floor-recovery:test', JSON.stringify({ savedAt: Date.now(), data: { form: null } }))
    expect(readFloorRecovery('test')).toBeNull()
    saveFloorRecovery('test', { missing: 'required structured form' })
    expect(readFloorRecovery('test')).toBeNull()
    sessionStorage.setItem('scns-floor-recovery:test', JSON.stringify({ savedAt: Date.now() - 7200001, data: {} }))
    expect(readFloorRecovery('test')).toBeNull()
  })
  it('deliberate logout clears floor recovery alongside other private admin recovery', () => {
    saveFloorRecovery('test', {})
    clearGraphRecovery()
    expect(sessionStorage.getItem('scns-floor-recovery:test')).toBeNull()
  })
})
