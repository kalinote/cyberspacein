/**
 * @typedef {Object} WikiInfoboxRow
 * @property {string} label
 * @property {string} value
 */

/**
 * @typedef {Object} WikiInfobox
 * @property {string} caption
 * @property {string} [series]
 * @property {string|null} [image]
 * @property {WikiInfoboxRow[]} [rows]
 */

/**
 * @typedef {Object} WikiContentNode
 * @property {string} section
 * @property {string} [title]
 * @property {string} [content]
 * @property {WikiInfobox|null} [infobox]
 * @property {WikiContentNode[]} [children]
 */

/**
 * @typedef {Object} WikiFootnote
 * @property {string} id
 * @property {string} text
 */

/**
 * @typedef {Object} WikiReference
 * @property {string} id
 * @property {string} text
 * @property {string} [url]
 * @property {string|null} [entityType]
 * @property {string|null} [entityUuid]
 */

/**
 * @typedef {Object} WikiCitationHealth
 * @property {string[]} [missingRefs]
 * @property {string[]} [missingFootnotes]
 * @property {string[]} [orphanReferences]
 * @property {string[]} [orphanFootnotes]
 */

/**
 * @typedef {Object} WikiPageDetail
 * @property {string} id
 * @property {string} slug
 * @property {string} title
 * @property {string} [sourceNote]
 * @property {string} [lastModified]
 * @property {number} revision
 * @property {string} [status]
 * @property {WikiContentNode} [contentTree]
 * @property {WikiFootnote[]} [footnotes]
 * @property {WikiReference[]} [references]
 * @property {string[]} [categories]
 * @property {WikiCitationHealth} [citationHealth]
 */

/**
 * @typedef {Object} WikiPageListItem
 * @property {string} id
 * @property {string} slug
 * @property {string} title
 * @property {string|null} [sourceNote]
 * @property {string} [status]
 * @property {string[]} [categories]
 * @property {string} [lastModified]
 * @property {number} [revision]
 * @property {string} [createdAt]
 */

export {}
