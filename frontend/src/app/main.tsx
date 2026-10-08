import React, { lazy, Suspense } from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import '../styles/global.css'

const AdminApp = lazy(() => import('../features/admin/AdminApp'))
const QRStart = lazy(() => import('../features/qr/QRStart'))
const qrRoute = window.location.pathname.startsWith('/q/')
const adminRoute = window.location.pathname === '/admin' || window.location.pathname.startsWith('/admin/')

const client = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 15000, refetchOnWindowFocus: false } } })

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><QueryClientProvider client={client}><Suspense fallback={<main><p role="status">Loading campus navigation…</p></main>}>{adminRoute ? <AdminApp /> : qrRoute ? <QRStart /> : <App />}</Suspense></QueryClientProvider></React.StrictMode>,
)
