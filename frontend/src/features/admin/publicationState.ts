import type { Diagnostic } from './Publication'

export function warningReasons(diagnostics: Diagnostic[], reason: string) { return Object.fromEntries(diagnostics.filter(d => d.severity === 'warning').map(d => [d.id, reason])) }
