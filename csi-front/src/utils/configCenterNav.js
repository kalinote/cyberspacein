/**
 * @typedef {Object} ConfigNavItem
 * @property {string} key
 * @property {string} label
 * @property {string} icon
 * @property {boolean} [disabled]
 * @property {ConfigNavItem[]} [children]
 */

/**
 * 在扁平或一层分组的导航项中按 key 查找（用于当前 tab 图标与标题）。
 * @param {ConfigNavItem[]|undefined} items
 * @param {string} activeKey
 * @returns {ConfigNavItem|null}
 */
export function findNavItemByKey(items, activeKey) {
  if (!items?.length || !activeKey) return null
  for (const tab of items) {
    if (tab.key === activeKey) return tab
    if (tab.children?.length) {
      const child = tab.children.find((c) => c.key === activeKey)
      if (child) return child
    }
  }
  return null
}
