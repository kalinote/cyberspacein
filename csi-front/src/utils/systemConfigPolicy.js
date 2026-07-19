export function buildConfigChanges(fields, form, original) {
  const output = {}
  for (const field of fields || []) {
    if (!field.editable) continue
    const value = form[field.key]
    if (field.sensitive) {
      if (value !== '' && value != null) output[field.key] = value
    } else if (!Object.is(value, original[field.key])) {
      output[field.key] = value
    }
  }
  return output
}

export function countConfigModes(fields) {
  return ['runtime', 'restart', 'readonly'].reduce((counts, mode) => {
    counts[mode] = (fields || []).filter(field => field.apply_mode === mode).length
    return counts
  }, {})
}

export function selectConfigChangesByMode(fields, changes, mode) {
  const allowedKeys = new Set(
    (fields || []).filter(field => field.apply_mode === mode).map(field => field.key)
  )
  return Object.fromEntries(
    Object.entries(changes || {}).filter(([key]) => allowedKeys.has(key))
  )
}
