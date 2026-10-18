// Native local hosting mirrors infra/nginx.conf boundaries; no UI/API changes.
import { Buffer } from 'node:buffer'
import { URL } from 'node:url'

export const MAX_BODY = 10 * 1024 * 1024
export function nativeBoundary(req, res, next) {
  res.setHeader('X-Content-Type-Options', 'nosniff')
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin')
  function refuse(status) {
    if (!res.headersSent) { res.setHeader('Connection', 'close'); res.statusCode = status; res.end() }
  }
  let path
  try { path = decodeURIComponent(new URL(req.url ?? '/', 'http://localhost').pathname) }
  catch { refuse(400); return }
  if (/^\/(storage|data)(\/|$)/.test(path)) { refuse(404); return }
  const size = req.headers['content-length']
  if (size !== undefined && (!/^\d+$/.test(size) || !Number.isSafeInteger(Number(size)))) { refuse(400); return }
  if (Number(size) > MAX_BODY) { refuse(413); return }
  let bytes = 0
  req.on('data', chunk => {
    bytes += typeof chunk === 'string' ? Buffer.byteLength(chunk) : chunk.byteLength
    if (bytes > MAX_BODY) { refuse(413); req.destroy() }
  })
  next()
}
