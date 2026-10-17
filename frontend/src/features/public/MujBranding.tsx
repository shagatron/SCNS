import { useState } from 'react'
import type { Campus } from '../../api/client'

// Use published campus metadata, never a substring/name or GPS inference.
export function hasMujBranding(campus?: Campus) {
  return campus?.code === 'MUJ' && !campus.is_demo
}

export function MujHeroPhoto() {
  const [failed, setFailed] = useState(false)
  return <div className="muj-hero-photo" aria-hidden="true" data-photo-status={failed ? 'unavailable' : 'available'}>
    {!failed && <picture>
      <source media="(max-width: 760px)" srcSet="/branding/muj/campus-mobile.webp" />
      <img src="/branding/muj/campus-736.webp" srcSet="/branding/muj/campus-480.webp 480w, /branding/muj/campus-736.webp 736w" sizes="100vw" width="736" height="414" alt="" loading="eager" fetchPriority="high" decoding="async" onError={() => setFailed(true)} />
    </picture>}
  </div>
}

export function MujEmblem() {
  const [failed, setFailed] = useState(false)
  return <div className="muj-emblem">
    {failed ? <span className="muj-emblem-fallback">University emblem unavailable</span> : <img src="/branding/muj/originals/muj_logo.png" width="250" height="289" alt="Manipal University Jaipur emblem" decoding="async" onError={() => setFailed(true)} />}
  </div>
}
