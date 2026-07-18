export function normalizePermissionCodes(value) {
  if (!Array.isArray(value)) return []
  return [...new Set(value
    .filter(code => typeof code === 'string' && code.trim().length > 0)
    .map(code => code.trim()))]
}

export function hasAllForPermissions(granted, required) {
  if (!Array.isArray(required)) return false
  if (required.length === 0) return false
  if (!required.every(code => typeof code === 'string' && code.length > 0)) return false
  const normalized = normalizePermissionCodes(granted)
  if (normalized.includes('*')) return true
  return required.every(code => normalized.includes(code))
}

export function hasAnyForPermissions(granted, required) {
  if (!Array.isArray(required) || required.length === 0) return false
  return required.some(code => hasAllForPermissions(granted, [code]))
}
