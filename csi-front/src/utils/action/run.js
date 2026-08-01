export const buildActionRunRequest = (blueprintId, params, debug = false) => {
  const payload = {
    blueprint_id: blueprintId,
    debug: Boolean(debug)
  }
  if (params !== null && params !== undefined) payload.params = params
  return payload
}
