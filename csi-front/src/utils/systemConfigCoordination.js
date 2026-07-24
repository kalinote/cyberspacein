export function formatCoordinationSnapshot(snapshot) {
  return JSON.stringify(snapshot || {}, null, 2)
}

export function unresolvedCoordinationKeys(differences, resolutions) {
  return (differences || [])
    .filter(item => !['file', 'database'].includes(resolutions?.[item.key]))
    .map(item => item.key)
}

export function buildCoordinationResolutions(differences, source) {
  return Object.fromEntries((differences || []).map(item => [
    item.key,
    source === 'database' && item.database_available ? 'database' : 'file'
  ]))
}

export function coordinationImpact(differences, resolutions, fixedImpact = {}) {
  const selectedChanges = (differences || []).filter(item => {
    const source = resolutions?.[item.key]
    return source && item[`${source}_changes_active`]
  })
  return {
    runtime: [...new Set([
      ...(fixedImpact.runtime || []),
      ...selectedChanges.filter(item => item.apply_mode === 'runtime').map(item => item.key)
    ])],
    restart: [...new Set([
      ...(fixedImpact.restart || []),
      ...selectedChanges.filter(item => item.apply_mode === 'restart').map(item => item.key)
    ])]
  }
}
