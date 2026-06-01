import { provide, ref } from 'vue'
import { WIKI_EDITOR_KEY } from '@/components/wiki/wikiEditorKey.js'

/**
 * 为历史版本预览等只读场景提供 WikiSectionBlock 所需的 editor 上下文。
 */
export function provideWikiReadonlyEditor() {
  provide(WIKI_EDITOR_KEY, {
    editMode: ref(false),
    editingContentId: ref(null),
    contentDraft: ref(''),
    startEditContent() {},
    saveContent: async () => {},
    cancelContent() {},
    openInfoboxEditor() {},
    addInfobox: async () => {},
    removeInfobox: async () => {},
  })
}
