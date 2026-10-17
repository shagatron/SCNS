// Shared original category symbols. No remote logos, photos or invented ratings.
export const categoryPaths: Record<string, string> = {
  building: 'M4 21V3h16v18M8 7h1m6 0h1M8 11h1m6 0h1M9 21v-5h6v5',
  library: 'M3 4h7l2 2 2-2h7v15h-7l-2 2-2-2H3zM12 6v15',
  entrance: 'M5 21V3h14v18M2 21h20M9 12h7m-3-3 3 3-3 3',
  cafe: 'M4 4h12v9a6 6 0 0 1-12 0zM16 6h2a3 3 0 0 1 0 6h-2M3 21h15',
  water: 'M12 2S4 11 4 15a8 8 0 0 0 16 0c0-4-8-13-8-13z',
  washroom: 'M8 5h.01M16 5h.01M5 10h6m2 0h6M8 10v11m8-11v11',
  garden: 'M12 21V10M12 15C3 15 3 4 3 4s9 0 9 8c0-8 9-8 9-8s0 11-9 11',
  help: 'M9 8a3 3 0 1 1 5 2c-2 1-2 2-2 4M12 18h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  room: 'M4 21V3h16v18M15 12h.01M8 21V7h8',
}
export function iconMarkup(kind: string) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${categoryPaths[kind] ?? categoryPaths.building}"/></svg>`
}
export default function PlaceIcon({ kind }: { kind: string }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={categoryPaths[kind] ?? categoryPaths.building} /></svg>
}
