const prefix = 'scns-floor-recovery:'
const records = {
  form: ['id', 'building_id', 'code', 'label', 'ordering', 'elevation_m', 'visibility'],
  measurement: ['ax', 'ay', 'bx', 'by', 'distance', 'cx', 'cy', 'dx', 'dy', 'checkDistance', 'date', 'evidence', 'uncertainty'],
  uploadMeta: ['title', 'rights', 'provenance', 'attribution'],
}
export function saveFloorRecovery(key: string, data: unknown) {
  try { const text = JSON.stringify({ savedAt: Date.now(), data }); if (text.length <= 64000) sessionStorage.setItem(prefix + key, text) } catch { /* Optional recovery never stores files/tokens. */ }
}
export function readFloorRecovery(key: string): unknown {
  try {
    const text = sessionStorage.getItem(prefix + key)
    if (!text || text.length > 64000) return null
    const stored = JSON.parse(text)
    if (!stored || !Number.isFinite(stored.savedAt) || Date.now() - stored.savedAt < 0 || Date.now() - stored.savedAt >= 2 * 3600000) return null
    const data = stored.data
    if (!data || typeof data.selectedId !== 'string' || !Number.isInteger(data.capturedVersion) || data.capturedVersion <= 0 || !Number.isInteger(data.page) || data.page < 1 || data.page > 30) return null
    for (const [key, fields] of Object.entries(records)) if (!data[key] || fields.some(field => typeof data[key][field] !== 'string')) return null
    if (!Array.isArray(data.masks) || data.masks.length > 20 || data.masks.some((mask: Record<string, unknown>) => !mask || ['x', 'y', 'width', 'height'].some(field => typeof mask[field] !== 'number' || !Number.isFinite(mask[field])))) return null
    return data
  } catch { return null }
}
export function discardFloorRecovery(key: string) { try { sessionStorage.removeItem(prefix + key) } catch { /* Optional storage. */ } }
