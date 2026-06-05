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
 * @property {string} title
 * @property {string|null} [sourceNote]
 * @property {string} [status]
 * @property {string[]} [categories]
 * @property {string} [lastModified]
 * @property {number} [revision]
 * @property {string} [createdAt]
 */

/**
 * @typedef {Object} WikiRevisionListItem
 * @property {number} revision
 * @property {string} changeType
 * @property {string|null} [targetSection]
 * @property {string} changeSummary
 * @property {string|null} [operator]
 * @property {number|null} [restoredFromRevision]
 * @property {string} createdAt
 */

/**
 * @typedef {Object} WikiRevisionDetail
 * @property {string} wikiId
 * @property {number} revision
 * @property {string} changeType
 * @property {string|null} [targetSection]
 * @property {string} changeSummary
 * @property {string|null} [operator]
 * @property {number|null} [restoredFromRevision]
 * @property {string} createdAt
 * @property {WikiPageDetail} snapshot
 * @property {WikiCitationHealth} [citationHealth]
 */

/**
 * @typedef {'equal'|'insert'|'delete'} WikiTextDiffOp
 */

/**
 * @typedef {Object} WikiTextDiffHunk
 * @property {WikiTextDiffOp} op
 * @property {string} text
 */

/**
 * @typedef {Object} WikiRevisionDiffSummary
 * @property {number} sectionsAdded
 * @property {number} sectionsRemoved
 * @property {number} sectionsModified
 * @property {number} sectionsMoved
 * @property {number} footnotesChanged
 * @property {number} referencesChanged
 * @property {boolean} metaChanged
 */

/**
 * @typedef {Object} WikiScalarFieldChange
 * @property {string} field
 * @property {unknown} fromValue
 * @property {unknown} toValue
 * @property {WikiTextDiffHunk[]|null} [hunks]
 */

/**
 * @typedef {Object} WikiCategoriesDiff
 * @property {string[]} added
 * @property {string[]} removed
 */

/**
 * @typedef {Object} WikiSectionDiff
 * @property {string} section
 * @property {'added'|'removed'|'modified'|'moved'} change
 * @property {string[]|null} [pathFrom]
 * @property {string[]|null} [pathTo]
 * @property {string|null} [titleFrom]
 * @property {string|null} [titleTo]
 * @property {WikiTextDiffHunk[]|null} [contentHunks]
 * @property {boolean} [infoboxChanged]
 * @property {WikiInfobox|null} [infoboxFrom]
 * @property {WikiInfobox|null} [infoboxTo]
 */

/**
 * @typedef {Object} WikiCitationItemDiff
 * @property {string} id
 * @property {'added'|'removed'|'modified'} change
 * @property {WikiFootnote|WikiReference|null} [fromItem]
 * @property {WikiFootnote|WikiReference|null} [toItem]
 * @property {WikiTextDiffHunk[]|null} [textHunks]
 */

/**
 * @typedef {Object} WikiRevisionDiff
 * @property {string} wikiId
 * @property {number} fromRevision
 * @property {number} toRevision
 * @property {WikiRevisionDiffSummary} summary
 * @property {WikiScalarFieldChange[]} meta
 * @property {WikiCategoriesDiff|null} categories
 * @property {WikiSectionDiff[]} sections
 * @property {WikiCitationItemDiff[]} footnotes
 * @property {WikiCitationItemDiff[]} references
 */

export {}
