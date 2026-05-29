export const DETAIL_PAGE_SCROLL_SNAP_CLASS = 'detail-page-scroll-snap'

/** @param {boolean} enabled */
export function setDetailPageScrollSnap(enabled) {
    document.documentElement.classList.toggle(DETAIL_PAGE_SCROLL_SNAP_CLASS, enabled)
}
