/**
 * 脚注 ID：a…z，第 27 个起 aa、ab…（Excel 列名式，0-based index）。
 * @param {number} index
 * @returns {string}
 */
export function indexToFootnoteId(index) {
  if (index < 0 || !Number.isFinite(index)) return 'a'
  let n = Math.floor(index)
  let id = ''
  do {
    id = String.fromCharCode(97 + (n % 26)) + id
    n = Math.floor(n / 26) - 1
  } while (n >= 0)
  return id
}

/**
 * @param {string} id
 * @returns {number}
 */
export function footnoteIdToIndex(id) {
  const normalized = String(id || '')
    .trim()
    .toLowerCase()
  if (!normalized || !/^[a-z]+$/.test(normalized)) return -1
  let index = 0
  for (let i = 0; i < normalized.length; i += 1) {
    index = index * 26 + (normalized.charCodeAt(i) - 97 + 1)
  }
  return index - 1
}

/**
 * @param {Iterable<string>} existingIds
 * @returns {string}
 */
export function nextFootnoteId(existingIds) {
  const used = new Set(
    [...existingIds].map((id) => String(id).trim().toLowerCase()).filter(Boolean)
  )
  for (let i = 0; i < 10000; i += 1) {
    const candidate = indexToFootnoteId(i)
    if (!used.has(candidate)) return candidate
  }
  return `fn-${Date.now()}`
}

/**
 * @param {Iterable<string>} existingIds
 * @returns {string}
 */
export function nextReferenceId(existingIds) {
  let max = 0
  for (const raw of existingIds) {
    const id = String(raw).trim()
    if (/^\d+$/.test(id)) {
      const n = Number(id)
      if (n > max) max = n
    }
  }
  return String(max + 1)
}
