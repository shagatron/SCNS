import { useEffect, useState } from 'react'
import type { Campus, MapData, Search } from '../../api/client'
import type { components } from '../../api/generated'

const sections = ['intro', 'overview', 'how', 'directory', 'explorer'] as const
export function PublicNavigation() {
  const [active, setActive] = useState<string>('intro')
  useEffect(() => {
    let frame = 0
    const update = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const present = sections.filter(id => document.getElementById(id))
        const passed = present.filter(id => document.getElementById(id)!.getBoundingClientRect().top <= window.innerHeight * .35)
        setActive(passed.at(-1) ?? present[0] ?? 'intro')
      })
    }
    update()
    window.addEventListener('scroll', update, { passive: true }); window.addEventListener('resize', update); window.addEventListener('hashchange', update)
    return () => { cancelAnimationFrame(frame); window.removeEventListener('scroll', update); window.removeEventListener('resize', update); window.removeEventListener('hashchange', update) }
  }, [])
  return <header className="public-navigation"><nav aria-label="Main navigation"><a className="public-wordmark" href="#intro" aria-label="SCNS home">scns<span aria-hidden="true">↗</span></a>
    {sections.map((id, index) => <a key={id} href={`#${id}`} className={`${id === 'explorer' ? 'nav-explore' : ''} ${['overview', 'how'].includes(id) ? 'nav-secondary' : ''}`} aria-current={active === id ? 'location' : undefined} onClick={() => requestAnimationFrame(() => document.getElementById(id)?.focus({ preventScroll: true }))}>{['Home', 'Campus', 'How it works', 'Places', 'Explore ↗'][index]}</a>)}
  </nav></header>
}

export function PublicMotion({ direct }: { direct: boolean }) {
  useEffect(() => {
    const root = document.querySelector('.public-app main')
    if (!root) return
    let navigated = false
    const reveal = typeof IntersectionObserver === 'undefined' ? undefined : new IntersectionObserver(entries => {
      entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('revealed'); reveal?.unobserve(entry.target) } })
    }, { threshold: .1 })
    const observe = () => {
      root.querySelectorAll('[data-reveal]:not(.revealed)').forEach(el => reveal?.observe(el))
      const id = window.location.hash.slice(1) || (direct ? 'explorer' : '')
      if (!navigated && id) {
        const element = document.getElementById(id)
        if (element && (id !== 'explorer' || element.hasAttribute('data-explorer-ready'))) { element.scrollIntoView({ behavior: 'instant' }); navigated = true }
      }
    }
    observe()
    const changes = new MutationObserver(observe); changes.observe(root, { childList: true, subtree: true })
    return () => { reveal?.disconnect(); changes.disconnect() }
  }, [direct])
  return null
}

export function CampusOpening({ campus, campuses, locked, onCampus, online, connected }: { campus?: Campus; campuses?: Campus[]; locked: boolean; onCampus: (id: string) => void; online: boolean; connected: boolean }) {
  return <section className="campus-opening editorial-section" id="intro" tabIndex={-1} aria-labelledby="intro-heading">
    <div className="opening-top"><span className="section-index">SCNS — SMART CAMPUS NAVIGATION</span><p>{campus?.name ?? 'Campus navigation'}<br />Published places. Connected paths.</p></div>
    <span className="opening-watermark" aria-hidden="true">scns</span>
    <div className="opening-note"><strong>A campus.<br />A clearer way through.</strong><p>Find a place, choose your starting point and follow a route through mapped paths.</p>
      <div className="campus-control"><label htmlFor="campus">Explore campus</label><select id="campus" disabled={locked || !campuses?.length} value={campus?.id ?? ''} onChange={e => onCampus(e.target.value)}>{!campuses?.length && <option value="">{campuses ? 'No published campus' : 'Loading campus…'}</option>}{campuses?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
      {campus?.is_demo && <p className="synthetic-disclosure"><strong>Synthetic demo.</strong> Invented locations and paths. Not for real-world navigation.</p>}
      <a href="#about">About the data <span aria-hidden="true">↗</span></a>
    </div>
    <div className="opening-title"><h1 id="intro-heading">Find your<br />way across<br />campus.</h1><a className="explore-action" href="#explorer"><span className="arrow-disc" aria-hidden="true">↗</span>Explore campus</a></div>
    <div className="opening-bottom"><span className="connection"><i className={online && connected ? 'status-dot' : 'status-dot offline'} />{!online ? 'Offline · connection needed for new routes' : connected ? 'Campus service connected' : 'Checking campus service…'}</span><span>01 / A place to begin</span></div>
  </section>
}

export function CampusOverview({ initial, map, floors }: { initial: Search; map?: MapData; floors?: components['schemas']['FloorsOut'] }) {
  const stats = [{ value: initial.total, label: 'Public destinations', description: 'Searchable places in this release' }]
  if (map && !map.truncated) stats.push({ value: map.features.filter(f => f.properties.layer === 'building').length, label: 'Mapped buildings', description: 'Published footprints within campus extent' })
  if (floors) stats.push({ value: floors.floors.length, label: 'Published floors', description: 'Approved floor views available to browse' })
  return <section id="overview" tabIndex={-1} className="editorial-section campus-overview" aria-labelledby="overview-heading"><p className="section-index">01 — THE PUBLISHED CAMPUS</p><h2 id="overview-heading" className="display-heading" data-reveal>A campus,<br />at a glance.</h2><p className="section-description">Only what’s on the current published map. Draft changes stay behind the scenes.</p>
    <div className="campus-figures">{stats.map(stat => <div key={stat.label}><strong>{stat.value}</strong><h3>{stat.label}</h3><p>{stat.description}</p></div>)}</div>
    {(!map || map.truncated || !floors) && <p className="muted">Unavailable or incomplete building/floor counts are omitted.</p>}
  </section>
}

export function HowNavigationWorks() {
  return <section id="how" tabIndex={-1} className="editorial-section navigation-process" aria-labelledby="how-heading"><div><p className="section-index">02 — THE WAY THROUGH</p><h2 id="how-heading" className="display-heading" data-reveal>Find.<br />Choose.<br />Navigate.</h2><p className="section-description">A graph underneath.<br />A clear next step in front of you.</p></div><div className="process-content"><ol className="process-rows">
    <li><span>01</span><h3>Find</h3><p>Search a name, alias or department. Browse published places and room details.</p><a href="#directory" aria-label="Find a destination">↗</a></li>
    <li><span>02</span><h3>Choose</h3><p>Pick a known start and destination. Set your route preference and distance policy.</p><a href="#explorer" aria-label="Choose route controls">↗</a></li>
    <li><span>03</span><h3>Navigate</h3><p>Follow stored paths, ordered directions and explicit floor transitions.</p><a href="#explorer" aria-label="Open navigation explorer">↗</a></li>
    </ol><figure className="route-illustration"><svg viewBox="0 0 500 170" role="img" aria-label="Illustration of directed graph connections between start and destination"><path d="M35 125 H190 V45 H465" fill="none" stroke="currentColor" strokeWidth="3" /><path d="M190 125 L330 125 V45" fill="none" stroke="currentColor" strokeWidth="1" strokeDasharray="5 7" />{[[35,125],[190,125],[190,45],[330,45],[465,45]].map(([x,y]) => <circle key={`${x}:${y}`} cx={x} cy={y} r="7" fill="currentColor" />)}<text x="20" y="158">Start</text><text x="360" y="27">Destination →</text></svg><figcaption>Illustrative graph · not a navigable campus map</figcaption></figure>
    <div className="algorithm-note"><h3>From graph to walking route.</h3><p>The server uses Dijkstra with adjacency lists and a heap priority queue. It searches eligible directed connections between stored anchors, respecting access rules and live restrictions. Distance follows stored path geometry; an intersection does not create a shortcut.</p><p>Directions-only mode allows unknown distances and minimizes eligible traversals. It does not claim the shortest distance or fastest time.</p></div></div></section>
}

