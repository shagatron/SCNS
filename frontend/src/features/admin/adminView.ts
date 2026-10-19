export function readAdminView(key: string, fallback = '') { try { return sessionStorage.getItem(`scns-admin-view:${key}`) ?? fallback } catch { return fallback } }
export function writeAdminView(key: string, value: string) { try { sessionStorage.setItem(`scns-admin-view:${key}`, value) } catch { /* optional selection preference */ } }
