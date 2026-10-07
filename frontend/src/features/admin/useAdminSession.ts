import { useCallback, useEffect, useState } from 'react'
import { useQuery, useQueryClient, type Query } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import { adminApi, type Session } from './api'
import { clearGraphRecovery } from './graphState'

const sessionKey = ['admin', 'session'] as const
const privateData = (query: Query) => query.queryKey[0] === 'admin' && query.queryKey[1] !== 'session'

export function useAdminSession() {
  const cache = useQueryClient()
  const [ended, setEnded] = useState(false)
  const discardPrivateData = useCallback(() => {
    void cache.cancelQueries({ predicate: privateData })
    cache.removeQueries({ predicate: privateData })
  }, [cache])
  const session = useQuery({
    queryKey: sessionKey,
    queryFn: async ({ signal }): Promise<Session | null> => {
      try { return await adminApi<Session>('/session', { signal }) }
      catch (error) {
        if (signal.aborted || !(error instanceof ApiError) || error.code !== 'authentication_required') throw error
        clearGraphRecovery()
        // An initial 401 is a normal anonymous result. Keep this observed query
        // alive so it settles, rather than clearing/recreating it on every 401.
        if (cache.getQueryData<Session | null>(sessionKey)) {
          setEnded(true)
          discardPrivateData()
        }
        return null
      }
    },
    retry: false,
    staleTime: 0,
    refetchOnMount: query => !!query.state.data,
    refetchOnWindowFocus: query => !!query.state.data,
    refetchOnReconnect: query => !!query.state.data,
  })
  const establish = useCallback((data: Session) => {
    // Cancel an older session check before replacing it with a successful login.
    void cache.cancelQueries({ queryKey: ['admin'] })
    discardPrivateData()
    cache.setQueryData(sessionKey, data)
    setEnded(false)
  }, [cache, discardPrivateData])
  const signOut = useCallback(() => {
    clearGraphRecovery()
    void cache.cancelQueries({ queryKey: ['admin'] })
    discardPrivateData()
    cache.setQueryData(sessionKey, null)
    setEnded(false)
  }, [cache, discardPrivateData])
  useEffect(() => {
    const expired = () => {
      // Protected-request 401s end only a session that the UI established.
      // Ignore duplicate/late 401s after it has already ended.
      if (!cache.getQueryData<Session | null>(sessionKey)) return
      void cache.cancelQueries({ queryKey: ['admin'] })
      discardPrivateData()
      cache.setQueryData(sessionKey, null)
      setEnded(true)
    }
    window.addEventListener('admin-session-ended', expired)
    return () => window.removeEventListener('admin-session-ended', expired)
  }, [cache, discardPrivateData])
  return { session, ended, establish, signOut }
}
