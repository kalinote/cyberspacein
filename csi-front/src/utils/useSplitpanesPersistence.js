const STORAGE_KEY = 'article-detail-pane-sizes'

export const ARTICLE_DETAIL_PANE_DEFAULTS = {
    horizontal: [18, 52, 30],
    centerVertical: [62, 38],
}

/**
 * @param {typeof ARTICLE_DETAIL_PANE_DEFAULTS} defaults
 */
export function loadArticleDetailPaneSizes(defaults = ARTICLE_DETAIL_PANE_DEFAULTS) {
    try {
        const raw = localStorage.getItem(STORAGE_KEY)
        if (!raw) return { ...defaults }
        const parsed = JSON.parse(raw)
        const horizontal = normalizePaneSizes(parsed.horizontal, defaults.horizontal, 3)
        const centerVertical = normalizePaneSizes(parsed.centerVertical, defaults.centerVertical, 2)
        return { horizontal, centerVertical }
    } catch {
        return { ...defaults }
    }
}

/**
 * @param {unknown} values
 * @param {number[]} fallback
 * @param {number} length
 */
function normalizePaneSizes(values, fallback, length) {
    if (!Array.isArray(values) || values.length !== length) {
        return [...fallback]
    }
    const nums = values.map((v) => parseFloat(v))
    if (nums.some((n) => Number.isNaN(n) || n <= 0)) {
        return [...fallback]
    }
    return nums
}

/**
 * @param {{ horizontal: number[], centerVertical: number[] }} sizes
 */
export function saveArticleDetailPaneSizes(sizes) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sizes))
    } catch {
        /* 存储不可用时忽略 */
    }
}

/**
 * @param {{ panes: Array<{ size: number }> }} payload
 * @param {number} count
 */
export function paneSizesFromResizedPayload(payload, count) {
    const fromPanes = payload?.panes?.map((p) => p.size) ?? []
    if (fromPanes.length === count) {
        return fromPanes
    }
    return null
}
