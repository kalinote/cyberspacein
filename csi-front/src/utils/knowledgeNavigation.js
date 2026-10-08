import { PERM } from './permissions.js'

export const KNOWLEDGE_DESTINATIONS = [
  { label: '检索', path: '/search', icon: 'mdi:magnify', permission: PERM.pages.search },
  { label: '重点', path: '/target/highlights', icon: 'mdi:star-outline', permission: PERM.pages.target.highlights },
  { label: '专题', path: '/target/wiki', icon: 'mdi:book-open-page-variant-outline', permission: PERM.pages.target.wiki },
  { label: '证据', path: '/evidence/chains', icon: 'mdi:graph-outline', permission: PERM.pages.evidence },
]
