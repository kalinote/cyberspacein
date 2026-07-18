import { reactive } from 'vue'
import { hasAllForPermissions, normalizePermissionCodes } from '@/utils/permissionPolicy'

const STORAGE_KEY = 'csi_auth_v2'

const state = reactive({
  accessToken: null,
  user: null,
  permissions: [],
  authorizationVersion: null,
  sessionId: null,
  sessionExpiresAt: null,
  meInitialized: false
})

function loadFromStorage() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
    if (!parsed || typeof parsed !== 'object') return
    state.accessToken = typeof parsed.accessToken === 'string' ? parsed.accessToken : null
    state.user = parsed.user && typeof parsed.user === 'object' ? parsed.user : null
    state.permissions = normalizePermissionCodes(parsed.permissions)
    state.authorizationVersion = Number.isInteger(parsed.authorizationVersion)
      ? parsed.authorizationVersion
      : null
    state.sessionId = typeof parsed.sessionId === 'string' ? parsed.sessionId : null
    state.sessionExpiresAt = typeof parsed.sessionExpiresAt === 'string' ? parsed.sessionExpiresAt : null
    state.meInitialized = false
  } catch {
    clearAuth()
  }
}

function saveToStorage() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    accessToken: state.accessToken,
    user: state.user,
    permissions: state.permissions,
    authorizationVersion: state.authorizationVersion,
    sessionId: state.sessionId,
    sessionExpiresAt: state.sessionExpiresAt
  }))
}

export function setAuth({
  accessToken,
  user,
  permissions,
  authorizationVersion,
  sessionId,
  sessionExpiresAt
}) {
  state.accessToken = typeof accessToken === 'string' && accessToken ? accessToken : null
  state.user = user && typeof user === 'object' ? user : null
  state.permissions = normalizePermissionCodes(permissions)
  state.authorizationVersion = Number.isInteger(authorizationVersion) ? authorizationVersion : null
  state.sessionId = typeof sessionId === 'string' ? sessionId : null
  state.sessionExpiresAt = typeof sessionExpiresAt === 'string' ? sessionExpiresAt : null
  state.meInitialized = true
  saveToStorage()
}

export function clearAuth() {
  state.accessToken = null
  state.user = null
  state.permissions = []
  state.authorizationVersion = null
  state.sessionId = null
  state.sessionExpiresAt = null
  state.meInitialized = false
  try { localStorage.removeItem(STORAGE_KEY) } catch { /* noop */ }
}

export function getAccessToken() { return state.accessToken }

export function hasAllPermissions(requiredPermissions) {
  return hasAllForPermissions(state.permissions, requiredPermissions)
}

export function getAuthState() { return state }

let mePromise = null
export async function ensureMeInitialized(meFetcher) {
  if (state.meInitialized || !state.accessToken) return
  if (typeof meFetcher !== 'function') throw new TypeError('meFetcher 必须是函数')
  if (mePromise) return mePromise
  mePromise = Promise.resolve(meFetcher()).finally(() => { mePromise = null })
  return mePromise
}

loadFromStorage()

export default { getAuthState, setAuth, clearAuth, getAccessToken, hasAllPermissions, ensureMeInitialized }
