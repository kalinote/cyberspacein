import { authApi } from '@/api/auth'
import { getAuthState, setAuth } from '@/stores/auth'

let refreshPromise = null

export function refreshAuthContext() {
  const state = getAuthState()
  if (!state.accessToken) return Promise.resolve(null)
  if (refreshPromise) return refreshPromise
  refreshPromise = authApi.me().then(res => {
    const payload = res?.data || {}
    setAuth({
      accessToken: state.accessToken,
      user: payload.user,
      permissions: payload.permissions,
      authorizationVersion: payload.authorization_version,
      sessionId: payload.session_id,
      sessionExpiresAt: payload.session_expires_at
    })
    window.dispatchEvent(new CustomEvent('csi:auth-refreshed'))
    return payload
  }).finally(() => { refreshPromise = null })
  return refreshPromise
}
