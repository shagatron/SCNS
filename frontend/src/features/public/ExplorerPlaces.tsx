import { useEffect, useRef } from 'react'
import type { Place, Search } from '../../api/client'
import PlaceIcon from './PlaceIcon'

export function ExplorerPlaces({ data, selected, pending, onSelect, onRoute, onStart }: {
  data?: Search; selected?: string; pending: boolean; onSelect: (place: Place) => void
  onRoute: (place: Place) => void; onStart: (place: Place) => void
}) {
  return <div className="explorer-places" aria-label="Published destination results">{data?.items.map(place => <article className={`place-row place-card ${selected === place.id ? 'is-selected' : ''}`} key={place.id}>
    <button type="button" className="place-select" aria-label={`Select ${place.name}`} aria-pressed={selected === place.id} onClick={() => onSelect(place)}>
      <span className={`category-icon kind-${place.kind}`}><PlaceIcon kind={place.kind} /></span><span><strong>{place.name}</strong><small>{place.kind.replaceAll('_', ' ')}{place.floor_label ? ` · ${place.floor_label}` : ''}</small>{!place.routable && <small className="place-unavailable">{place.navigation_mode === 'indoor_catalog_only' ? 'Indoor catalog only' : 'Entrance not mapped'}</small>}</span><span className="row-arrow" aria-hidden="true">↗</span>
    </button><div className="row-actions"><button disabled={pending} onClick={() => onRoute(place)} aria-label={`Route to ${place.name}`}>Route here ↗</button><button disabled={pending} onClick={() => onStart(place)} aria-label={`Start at ${place.name}`}>Start here</button></div>
  </article>)}</div>
}

export function ExplorerPlaceCard({ place, pending, onClose, onRoute, onStart }: {
  place: Place; pending: boolean; onClose: () => void; onRoute: () => void; onStart: () => void
}) {
  const card = useRef<HTMLElement>(null)
  useEffect(() => { card.current?.focus() }, [place.id])
  return <section ref={card} tabIndex={-1} className="explorer-place-card" aria-label="Selected place details" onKeyDown={e => { if (e.key === 'Escape') { e.stopPropagation(); onClose() } }}>
    <div className="selected-place-heading"><span className={`category-icon kind-${place.kind}`}><PlaceIcon kind={place.kind} /></span><div><p>{place.kind.replaceAll('_', ' ')}</p><h3>{place.name}</h3></div><button className="close-place" aria-label="Close place details" onClick={onClose}>×</button></div>
    {place.description && <p>{place.description}</p>}{place.building_name && <p>{place.building_name}{place.floor_label ? ` · ${place.floor_label}` : ''}{place.room_code ? ` · ${place.room_code}` : ''}</p>}
    {!place.routable && <p className="place-unavailable">{place.navigation_mode === 'indoor_catalog_only' ? 'Indoor catalog only · no reviewed routing capability or eligible door' : 'Entrance not mapped · routing unavailable'}</p>}
    <details><summary>Place details</summary>{place.aliases.length > 0 && <p>Also known as: {place.aliases.join(', ')}</p>}<p>Code: {place.code} · Accessibility: unknown until surveyed.</p></details>
    <div className="selected-place-actions"><button className="primary-button" disabled={pending} onClick={onRoute}>Route here ↗</button><button disabled={pending} onClick={onStart}>Set as start</button></div>
  </section>
}
