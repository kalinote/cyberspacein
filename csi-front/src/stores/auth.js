import { reactive } from 'vue'

const STORAGE_KEY = 'csi_auth_v1'

const state = reactive({
  accessToken: null,
  user: null,
  permissions: [],
  meInitialized: false
})

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    state.accessToken = parsed.accessToken || null
    state.user = parsed.user || null
    state.permissions = Array.isArray(parsed.permissions) ? parsed.permissions : []
  } catch (e) {
    // 忽略本地存储损坏
  }
}

function saveToStorage() {
  const payload = {
    accessToken: state.accessToken,
    user: state.user,
    permissions: state.permissions
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
}

export function setAuth({ accessToken, user, permissions }) {
  state.accessToken = accessToken || null
  state.user = user || null
  state.permissions = Array.isArray(permissions) ? permissions : []
  state.meInitialized = true
  saveToStorage()
}

export function clearAuth() {
  state.accessToken = null
  state.user = null
  state.permissions = []
  state.meInitialized = false
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (e) {
    // 忽略
  }
}

export function getAccessToken() {
  return state.accessToken
}

export function hasAllPermissions(requiredPermissions = []) {
  if (!requiredPermissions || requiredPermissions.length === 0) return true
  if (!Array.isArray(requiredPermissions)) return true
  if (requiredPermissions.includes('*')) return true
  if (Array.isArray(state.permissions) && state.permissions.includes('*')) return true
  if (!state.permissions || state.permissions.length === 0) return false
  return requiredPermissions.every(code => state.permissions.includes(code))
}

export function getAuthState() {
  return state
}

let mePromise = null

export async function ensureMeInitialized(meFetcher) {
  if (state.meInitialized) return
  if (!state.accessToken) return
  if (mePromise) return mePromise
  mePromise = (async () => {
    try {
      await meFetcher()
      state.meInitialized = true
    } finally {
      mePromise = null
    }
  })()
  return mePromise
}

loadFromStorage()

export default {
  getAuthState,
  setAuth,
  clearAuth,
  getAccessToken,
  hasAllPermissions,
  ensureMeInitialized
}

