import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { components } from '../../api/generated'

type Status = components['schemas']['ClosureStatus']
export function useClosures(campus: string, online: boolean) {
  const status = useQuery({ queryKey: ['closures', campus], queryFn: () => api<Status>(`/campuses/${campus}/closures`, { cache: 'no-store' }), retry: false, staleTime: 0, refetchInterval: online ? 15000 : false, refetchOnWindowFocus: true, refetchOnReconnect: true })
  const [clock, setClock] = useState(Date.now)
  useEffect(() => { const timer = window.setInterval(() => setClock(Date.now()), 1000); return () => window.clearInterval(timer) }, [])
  const fresh = online && !status.error && !!status.data && clock - status.dataUpdatedAt < 30000
  return { ...status, fresh, clock }
}
