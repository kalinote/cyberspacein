export function classifyAuthorizationFailure(code, httpStatus) {
  const codeString = typeof code === 'number' ? String(code) : ''
  if (codeString.startsWith('2401') || httpStatus === 401) return 'unauthorized'
  if (codeString.startsWith('2403') || httpStatus === 403) return 'forbidden'
  return 'other'
}

export function shouldRedirectToLogin(kind) {
  return kind === 'unauthorized'
}
