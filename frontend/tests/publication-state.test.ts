import { expect, test } from 'vitest'
import { warningReasons } from '../src/features/admin/publicationState'

test('acknowledgements include current warning identifiers and exclude blocking errors', () => {
  const diagnostics = [
    { id: 'blocking', severity: 'error' as const, code: 'missing_reference', message: 'Fix reference', entity: 'edges', ids: ['edge'] },
    { id: 'warning-v1', severity: 'warning' as const, code: 'unknown_accessibility', message: 'Unknown', entity: 'edges', ids: ['edge'] },
  ]
  expect(warningReasons(diagnostics, 'Reviewed coverage limitation')).toEqual({ 'warning-v1': 'Reviewed coverage limitation' })
  expect(warningReasons([], 'Reviewed')).toEqual({})
})
