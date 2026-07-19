import test from 'node:test'
import assert from 'node:assert/strict'

import { buildConfigChanges, countConfigModes, selectConfigChangesByMode } from '../src/utils/systemConfigPolicy.js'

test('buildConfigChanges ignores readonly and unchanged fields', () => {
  const fields = [
    { key: 'RRF_K', editable: true, sensitive: false },
    { key: 'API_V1_STR', editable: false, sensitive: false },
    { key: 'CRAWLAB_TOKEN', editable: true, sensitive: true }
  ]
  assert.deepEqual(
    buildConfigChanges(fields, { RRF_K: 80, API_V1_STR: '/changed', CRAWLAB_TOKEN: '' }, { RRF_K: 60, API_V1_STR: '/api/v1', CRAWLAB_TOKEN: '' }),
    { RRF_K: 80 }
  )
})

test('buildConfigChanges submits a newly entered secret without an original value', () => {
  const fields = [{ key: 'CRAWLAB_TOKEN', editable: true, sensitive: true }]
  assert.deepEqual(buildConfigChanges(fields, { CRAWLAB_TOKEN: 'new-secret' }, { CRAWLAB_TOKEN: '' }), { CRAWLAB_TOKEN: 'new-secret' })
})

test('countConfigModes summarizes all application modes', () => {
  assert.deepEqual(countConfigModes([
    { apply_mode: 'runtime' }, { apply_mode: 'runtime' }, { apply_mode: 'restart' }, { apply_mode: 'readonly' }
  ]), { runtime: 2, restart: 1, readonly: 1 })
})

test('selectConfigChangesByMode keeps runtime and restart saves separate', () => {
  const fields = [
    { key: 'RRF_K', apply_mode: 'runtime' },
    { key: 'APP_NAME', apply_mode: 'restart' },
    { key: 'API_V1_STR', apply_mode: 'readonly' }
  ]
  const changes = { RRF_K: 80, APP_NAME: 'New name', API_V1_STR: '/changed' }

  assert.deepEqual(selectConfigChangesByMode(fields, changes, 'runtime'), { RRF_K: 80 })
  assert.deepEqual(selectConfigChangesByMode(fields, changes, 'restart'), { APP_NAME: 'New name' })
})
