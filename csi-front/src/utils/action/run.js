export const normalizeActionSchedulingMode = mode => (
  mode === 'streaming' ? 'streaming' : 'barrier'
)

export const getOppositeActionSchedulingMode = mode => (
  normalizeActionSchedulingMode(mode) === 'streaming' ? 'barrier' : 'streaming'
)

export const buildActionRunRequest = (blueprintId, params, debug = false, schedulingMode = 'barrier') => {
  const payload = {
    blueprint_id: blueprintId,
    debug: Boolean(debug),
    scheduling_mode: normalizeActionSchedulingMode(schedulingMode)
  }
  if (params !== null && params !== undefined) payload.params = params
  return payload
}
