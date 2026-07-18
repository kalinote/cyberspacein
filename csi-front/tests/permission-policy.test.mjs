import assert from 'node:assert/strict'
import test from 'node:test'

import {
  hasAllForPermissions,
  hasAnyForPermissions,
  normalizePermissionCodes
} from '../src/utils/permissionPolicy.js'
import {
  classifyAuthorizationFailure,
  shouldRedirectToLogin
} from '../src/utils/authHttpPolicy.js'

test('invalid permission configuration defaults to deny', () => {
  assert.equal(hasAllForPermissions(['p:a'], null), false)
  assert.equal(hasAllForPermissions(['p:a'], []), false)
  assert.equal(hasAllForPermissions(['p:a'], ['']), false)
  assert.equal(hasAnyForPermissions(['p:a'], []), false)
})

test('permissions are normalized and wildcard remains explicit', () => {
  assert.deepEqual(normalizePermissionCodes([' p:a ', 'p:a', null]), ['p:a'])
  assert.equal(hasAllForPermissions(['p:a'], ['p:a']), true)
  assert.equal(hasAllForPermissions(['*'], ['p:any']), true)
  assert.equal(hasAllForPermissions([], ['p:a']), false)
})

test('only unauthorized failures redirect to login', () => {
  assert.equal(classifyAuthorizationFailure(240100, null), 'unauthorized')
  assert.equal(classifyAuthorizationFailure(240300, null), 'forbidden')
  assert.equal(classifyAuthorizationFailure(null, 403), 'forbidden')
  assert.equal(shouldRedirectToLogin('unauthorized'), true)
  assert.equal(shouldRedirectToLogin('forbidden'), false)
})
