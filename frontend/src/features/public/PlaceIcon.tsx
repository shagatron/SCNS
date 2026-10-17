import { categoryPaths } from './placeSymbols'

export default function PlaceIcon({ kind }: { kind: string }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={categoryPaths[kind] ?? categoryPaths.building} /></svg>
}
