import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { adminApi, type Audit, type Role, type User } from './api'
import { ErrorMessage } from './AdminApp'

const roles: Role[] = ['editor', 'reviewer_publisher', 'operations', 'system_admin']
const roleName = (role: string) => role.replaceAll('_', ' ')

export function AuditLog({ path }: { path: string }) {
  const [offset, setOffset] = useState(0)
  const events = useQuery({ queryKey: ['admin', path, 'audit', offset], queryFn: () => adminApi<Audit[]>(`${path}/audit?offset=${offset}`) })
  return <section className="admin-card"><h2>Audit records</h2><p>Administrative changes in this campus, newest first. Records include actor, resource, before/after values and request reference.</p><button onClick={() => void events.refetch()}>Refresh audit</button><ErrorMessage error={events.error} />
    {events.isPending ? <p role="status">Loading audit…</p> : <ul className="admin-records">{events.data?.map(event => <li key={event.id}><div><h3>{event.action}</h3><p>{new Date(event.created_at).toLocaleString()}</p><small className="admin-id">Actor: {event.actor_id ?? 'Trusted host'}<br />Revision: {event.revision_id ?? 'Not applicable'}<br />Resource: {event.resource_id ?? 'Not applicable'}<br />Request: {event.request_id}</small><details><summary>Before and after</summary><pre>{JSON.stringify({ before: event.before, after: event.after }, null, 2)}</pre></details></div></li>)}</ul>}
    {!events.isPending && !events.data?.length && <p>No records on this page.</p>}
    <div className="admin-actions"><button disabled={!offset} onClick={() => setOffset(offset - 50)}>Previous audit page</button><button disabled={(events.data?.length ?? 0) < 50} onClick={() => setOffset(offset + 50)}>Next audit page</button></div>
  </section>
}

export function Users({ path, csrf }: { path: string; csrf: string }) {
  const cache = useQueryClient()
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const users = useQuery({ queryKey: ['admin', path, 'users', offset], queryFn: () => adminApi<User[]>(`${path}/users?offset=${offset}`) })
  const refresh = async () => { await cache.invalidateQueries({ queryKey: ['admin', path, 'users'] }); await cache.invalidateQueries({ queryKey: ['admin', 'session'] }); await cache.invalidateQueries({ queryKey: ['admin'], predicate: q => q.queryKey.includes('dashboard') }) }
  return <section className="admin-card"><h2>Users and roles</h2><p>Provision accounts for this campus. Changes apply on the next request. Granting an existing account access to another campus requires the trusted-host command. At least one active system administrator must remain.</p>
    <form className="admin-editor" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError(null); setMessage('')
      const form = event.currentTarget
      const data = new FormData(form)
      try { await adminApi(`${path}/users`, { method: 'POST', csrf, body: Object.fromEntries(data) }); form.reset(); setMessage('Campus account created. Share the password securely with its owner.'); await refresh() }
      catch (e) { setError(e); const input = form.elements.namedItem('password'); if (input instanceof HTMLInputElement) input.value = '' } finally { setBusy(false) }
    }}><h3>Create campus account</h3><div className="admin-form-grid">
      <label>New username<input name="username" required minLength={3} maxLength={64} pattern="[a-zA-Z0-9_.\-]+" autoComplete="off" autoCapitalize="none" /></label>
      <label>Display name<input name="display_name" required maxLength={120} autoComplete="off" /></label>
      <label>Initial password<input name="password" type="password" required minLength={12} maxLength={128} autoComplete="new-password" /><small>12–128 characters. Use a unique password and a secure sharing channel.</small></label>
      <label>Campus role<select name="role">{roles.map(r => <option key={r} value={r}>{roleName(r)}</option>)}</select></label>
    </div><button disabled={busy}>Create account</button></form>
    <ErrorMessage error={error || users.error} />{message && <p className="admin-success" role="status">{message}</p>}
    <h3>Campus accounts</h3>{users.isPending ? <p role="status">Loading accounts…</p> : <ul className="admin-records">{users.data?.map(user => <li key={user.id}><div><h3>{user.display_name}</h3><p>{user.username} · {user.roles.map(roleName).join(', ')}</p></div><form onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError(null); setMessage('')
      const role = new FormData(event.currentTarget).get('role')
      try { await adminApi(`${path}/users/${user.id}/role`, { method: 'PUT', csrf, body: { role } }); setMessage('Campus role updated.'); await refresh() } catch (e) { setError(e) } finally { setBusy(false) }
    }}><label>Role for {user.username}<select key={user.roles.join()} name="role" defaultValue={user.roles[0]}>{roles.map(r => <option key={r} value={r}>{roleName(r)}</option>)}</select></label><button disabled={busy}>Replace campus roles</button></form></li>)}</ul>}
    <div className="admin-actions"><button disabled={!offset} onClick={() => setOffset(offset - 50)}>Previous accounts</button><button disabled={(users.data?.length ?? 0) < 50} onClick={() => setOffset(offset + 50)}>Next accounts</button></div>
  </section>
}
