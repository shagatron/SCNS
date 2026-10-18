// Actual loopback native-preview smoke; no Docker, database, credentials or UI edits.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { Buffer } from 'node:buffer'
import { EventEmitter } from 'node:events'
import { createServer, request } from 'node:http'
import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { preview } from '../../node_modules/vite/dist/node/index.js'
import { MAX_BODY, nativeBoundary } from '../../frontend/native-preview-security.mjs'

test('chunked payloads are byte-bounded without dropping valid requests', () => {
  const req = new EventEmitter()
  req.url = '/api/v1/admin/imports'; req.headers = {}; req.destroy = () => { req.destroyed = true }
  const headers = {}, res = { setHeader(k,v) { headers[k] = v }, end() { this.headersSent = true } }
  let next = false
  nativeBoundary(req, res, () => { next = true })
  req.emit('data', Buffer.alloc(MAX_BODY))
  assert.equal(next, true); assert.equal(req.destroyed, undefined)
  req.emit('data', Buffer.from('x'))
  assert.equal(res.statusCode, 413); assert.equal(req.destroyed, true)
  assert.equal(headers['X-Content-Type-Options'], 'nosniff')
})

test('compiled native preview preserves SPA, original assets, proxy and private/size boundaries', async () => {
  let hits = 0
  const api = createServer(async (req,res) => {
    hits++
    res.setHeader('Content-Type','application/json')
    if (req.method === 'POST') {
      const chunks=[]
      for await (const chunk of req) chunks.push(chunk)
      const bytes=Buffer.concat(chunks)
      res.end(JSON.stringify({bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')}))
    } else res.end(JSON.stringify({database:'ready'}))
  })
  await new Promise(resolve => api.listen(0,'127.0.0.1',resolve))
  const previous = process.env.API_PROXY_TARGET
  process.env.API_PROXY_TARGET = `http://127.0.0.1:${api.address().port}`
  let web
  try {
    const root = fileURLToPath(new URL('../../frontend/',import.meta.url))
    web = await preview({ root, configFile: fileURLToPath(new URL('../../frontend/vite.native.config.mjs',import.meta.url)), preview:{host:'127.0.0.1',port:0,strictPort:true} })
    const origin = `http://127.0.0.1:${web.httpServer.address().port}`
    for (const path of ['/', '/admin', '/?campus=synthetic']) {
      const res = await fetch(origin+path)
      assert.equal(res.status,200)
      assert.match(await res.text(),/<div id="root">/)
      assert.equal(res.headers.get('x-content-type-options'),'nosniff')
      assert.equal(res.headers.get('referrer-policy'),'strict-origin-when-cross-origin')
    }
    for (const path of ['/storage/private-original.pdf','/data/raw/source.osm','/%73torage/secret']) {
      assert.equal((await fetch(origin+path)).status,404)
    }
    const asset = await fetch(origin+'/branding/muj/originals/muj_logo.png')
    assert.equal(asset.status,200)
    const served = Buffer.from(await asset.arrayBuffer())
    const original = await readFile(new URL('../../frontend/public/branding/muj/originals/muj_logo.png',import.meta.url))
    assert.equal(createHash('sha256').update(served).digest('hex'),createHash('sha256').update(original).digest('hex'))
    assert.deepEqual(await (await fetch(origin+'/api/v1/health/ready')).json(),{database:'ready'})
    assert.equal(hits,1)
    const upload=Buffer.from('Clearly synthetic upload bytes\0 café')
    const forwarded=await (await fetch(origin+'/api/v1/echo',{method:'POST',body:upload})).json()
    assert.deepEqual(forwarded,{bytes:upload.length,sha256:createHash('sha256').update(upload).digest('hex')})
    assert.equal(hits,2)
    const oversized = await new Promise((resolve,reject) => {
      const req = request(origin+'/api/v1/oversized',{method:'POST',headers:{'Content-Length':MAX_BODY+1}},res => { res.resume(); resolve(res.statusCode) })
      req.on('error',reject); req.end()
    })
    assert.equal(oversized,413); assert.equal(hits,2)
  } finally {
    if (web) await new Promise(resolve => web.httpServer.close(resolve))
    await new Promise(resolve => api.close(resolve))
    if (previous === undefined) delete process.env.API_PROXY_TARGET
    else process.env.API_PROXY_TARGET = previous
  }
})
