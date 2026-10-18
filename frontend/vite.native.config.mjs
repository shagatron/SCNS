import base from './vite.config.ts'
import { nativeBoundary } from './native-preview-security.mjs'

export default {
  ...base,
  plugins: [...base.plugins, {
    name: 'scns-native-private-boundaries',
    configurePreviewServer(server) { server.middlewares.use(nativeBoundary) },
  }],
}
