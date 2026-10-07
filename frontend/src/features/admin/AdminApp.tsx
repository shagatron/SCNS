import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import { adminApi, type Dashboard, type Draft, type Session } from './api'
import { Catalog } from './Catalog'
import { AuditLog, Users } from './People'
import './admin.css'

export function ErrorMessage({ error }: { error: unknown }) {
  if (!error) return null
  return <div role="alert" className="error-box">{error instanceof Error ? error.message : 'The action could not be completed.'}{error instanceof ApiError && error.requestId && <small>Reference: {error.requestId}</small>}</div>
}

function Login({ onLogin }: { onLogin: (session: Session) => void }) {
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  return <section className="admin-card admin-login"><h1>Admin sign in</h1><p>Use your assigned campus account. First-time setup requires the trusted-host bootstrap command.</p>
    <form onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError(null)
      const form = event.currentTarget
      const data = new FormData(form)
      try { const session = await adminApi<Session>('/login', { method: 'POST', body: { username: data.get('username'), password: data.get('password') } }); form.reset(); onLogin(session) }
      catch (e) { setError(e); const password = form.elements.namedItem('password'); if (password instanceof HTMLInputElement) password.value = '' }
      finally { setBusy(false) }
    }}>
      <label>Username<input name="username" autoComplete="username" required minLength={3} maxLength={64} pattern="[a-zA-Z0-9_.\-]+" autoCapitalize="none" /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required maxLength={128} /></label>
      <ErrorMessage error={error} /><button className="primary-button" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
    </form>
  </section>
}

export default function AdminApp() {
  const cache = useQueryClient()
  const session = useQuery({ queryKey: ['admin', 'session'], queryFn: () => adminApi<Session>('/session'), retry: false, staleTime: 0, refetchOnWindowFocus: true })
  const [campus, setCampus] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    const expired = () => { cache.clear(); cache.setQueryData(['admin', 'session'], null); setError(new Error('Your session ended. Sign in to continue.')) }
    window.addEventListener('admin-session-ended', expired)
    return () => window.removeEventListener('admin-session-ended', expired)
  }, [cache])
  const selected = session.data?.grants.find(g => g.campus_id === campus) ?? session.data?.grants[0]
  return <>
    <a className="skip-link" href="#admin-main">Skip to administration</a>
    <header className="admin-header"><a href="/">← Public campus navigation</a><strong>Campus administration</strong>{session.data && <button disabled={busy} onClick={async () => {
      setBusy(true); setError(null)
      try { await adminApi('/logout', { method: 'POST', csrf: session.data.csrf_token }); cache.clear(); cache.setQueryData(['admin', 'session'], null) }
      catch (e) { setError(e) } finally { setBusy(false) }
    }}>Sign out</button>}</header>
    <main id="admin-main" className="admin-shell"><ErrorMessage error={error} />
      {session.isPending ? <p role="status">Checking your session…</p> : session.data ? <>
        <div className="admin-intro"><div><p className="eyebrow">DRAFT WORKSPACE</p><h1>Admin dashboard</h1><p>Signed in as {session.data.display_name}. Session expires {new Date(session.data.expires_at).toLocaleString()}.</p></div>
          <label>Assigned campus<select value={selected?.campus_id ?? ''} onChange={e => setCampus(e.target.value)}>{session.data.grants.map(g => <option key={g.campus_id} value={g.campus_id}>{g.campus_name}</option>)}</select></label></div>
        {selected ? <CampusDashboard key={selected.campus_id} campus={selected.campus_id} session={session.data} /> : <p>No campus permission is assigned. Contact your system administrator.</p>}
      </> : <><ErrorMessage error={session.error instanceof ApiError && session.error.code === 'authentication_required' ? null : session.error} /><Login onLogin={data => { setError(null); cache.setQueryData(['admin', 'session'], data) }} /></>}
    </main>
  </>
}

function CampusDashboard({ campus, session }: { campus: string; session: Session }) {
  const cache = useQueryClient()
  const path = `/campuses/${campus}`
  const dashboard = useQuery({ queryKey: ['admin', campus, 'dashboard'], queryFn: () => adminApi<Dashboard>(`${path}/dashboard`) })
  const [draftId, setDraftId] = useState('')
  const [tab, setTab] = useState('catalog')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  if (dashboard.isPending) return <p role="status">Loading campus dashboard…</p>
  if (!dashboard.data) return <><ErrorMessage error={dashboard.error} /><button onClick={() => void dashboard.refetch()}>Retry dashboard</button></>
  const data = dashboard.data
  const allowed = (permission: string) => data.permissions.includes(permission)
  const selected = data.drafts.find(d => d.id === draftId) ?? data.drafts[0]
  return <>
    <aside className="admin-notice"><strong>Public navigation stays on its published release.</strong><p>Draft changes are private. Imports, graph editing, review and publication are reserved for later milestones. Synthetic campus data is for software testing only.</p></aside>
    <section className="admin-card"><h2>Published release</h2>{data.release ? <p className="admin-id">{data.release.id}<br />Published {new Date(data.release.published_at).toLocaleString()}</p> : <p>No public release yet.</p>}
      <p>Permissions: {data.permissions.join(', ').replaceAll('_', ' ')}</p>
    </section>
    <div className="admin-tabs" aria-label="Administration sections">
      {allowed('draft_read') && <button aria-pressed={tab === 'catalog'} onClick={() => setTab('catalog')}>Draft catalog</button>}
      {allowed('audit_read') && <button aria-pressed={tab === 'audit'} onClick={() => setTab('audit')}>Audit records</button>}
      {allowed('user_admin') && <button aria-pressed={tab === 'users'} onClick={() => setTab('users')}>Users and roles</button>}
    </div>
    {tab === 'audit' && allowed('audit_read') && <AuditLog path={path} />}
    {tab === 'users' && allowed('user_admin') && <Users path={path} csrf={session.csrf_token} />}
    {tab === 'catalog' && allowed('draft_read') && <>
      <section className="admin-card"><h2>Draft catalog</h2><p>A new draft copies the current public release, including its stored navigation graph. Catalog edits stay within the selected draft.</p>
        <div className="admin-actions"><label>Selected draft<select value={selected?.id ?? ''} onChange={e => setDraftId(e.target.value)}><option value="" disabled>No draft selected</option>{data.drafts.map(d => <option key={d.id} value={d.id}>Draft {d.version} · {new Date(d.created_at).toLocaleString()}</option>)}</select></label>
          {allowed('draft_create') && <button disabled={busy} onClick={async () => { setBusy(true); setError(null); try {
            const draft = await adminApi<Draft>(`${path}/drafts`, { method: 'POST', csrf: session.csrf_token }); setDraftId(draft.id); await cache.invalidateQueries({ queryKey: ['admin', campus, 'dashboard'] })
          } catch (e) { setError(e) } finally { setBusy(false) } }}>{busy ? 'Creating draft…' : 'Create draft from published release'}</button>}
        </div><ErrorMessage error={error} />{data.drafts_total > 100 && <p>Showing the latest 100 drafts of {data.drafts_total}.</p>}
      </section>
      {selected && <Catalog key={selected.id} path={`${path}/drafts/${selected.id}`} csrf={session.csrf_token} editable={allowed('catalog_edit')} />}
    </>}
    {!allowed('draft_read') && <section className="admin-card"><h2>Operations access</h2><p>Your role can inspect this dashboard. Live closure and issue tools are scheduled for a later milestone.</p></section>}
  </>
}
