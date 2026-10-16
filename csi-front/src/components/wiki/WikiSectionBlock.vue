<template>
  <section
    :id="node.section"
    class="scroll-mt-24"
    :class="node.section === 'main' ? '' : 'wiki-section-block'"
  >
    <component
      v-if="showHeading"
      :is="headingTag"
      class="font-bold text-gray-900 border-b border-gray-100 pb-2 mb-4 flex items-center gap-2 flex-wrap"
      :class="headingSizeClass"
    >
      <span
        v-if="displayNumber"
        class="text-sm font-mono text-blue-600 bg-blue-50 px-2 py-0.5 rounded shrink-0"
      >
        {{ displayNumber }}
      </span>
      <span class="flex-1 min-w-0">{{ node.title }}</span>
      <SectionEditActions
        v-if="isEditMode"
        :section-id="node.section"
        :has-infobox="Boolean(node.infobox)"
      />
    </component>

    <div
      v-if="node.section === 'main' || showHeading || node.content || node.infobox || isEditingContent"
      class="wiki-section-body clearfix"
      :class="[
        hasChildren ? 'mb-6' : '',
        isEditingContent ? 'wiki-section-body--editing' : '',
      ]"
    >
      <div
        v-if="node.section === 'main'"
        class="flex items-center justify-end gap-1 mb-2"
      >
        <span class="text-xs text-gray-500 mr-auto">导语</span>
        <SectionEditActions
          v-if="isEditMode"
          :section-id="node.section"
          :has-infobox="Boolean(node.infobox)"
        />
      </div>

      <div v-if="node.infobox && !isEditingContent" class="mb-2">
        <details v-if="isMobile" class="wiki-mobile-infobox"><summary>{{ node.infobox.caption || '专题信息' }} · 查看资料卡</summary><WikiInfobox :infobox="node.infobox" /></details>
        <WikiInfobox v-else :infobox="node.infobox" />
      </div>

      <template v-if="isEditingContent">
        <div class="wiki-section-editor clear-both w-full min-w-0">
          <MonacoEditor
            ref="monacoRef"
            v-model="contentDraftModel"
            language="markdown"
            :min-height="editorHeight"
          />
          <div class="flex justify-end gap-2 mt-3">
            <el-button size="small" @click="editor.cancelContent()">取消</el-button>
            <el-button type="primary" size="small" @click="editor.saveContent()">保存</el-button>
          </div>
        </div>
      </template>
      <WikiMarkdown v-else-if="node.content" :content="node.content" />
    </div>

    <div v-if="hasChildren && !isEditingContent" class="space-y-8">
      <WikiSectionBlock
        v-for="(child, index) in node.children"
        :key="child.section"
        :node="child"
        :depth="depth + 1"
        :parent-number="node.section === 'main' ? '' : displayNumber"
        :child-index="index + 1"
      />
    </div>
  </section>
</template>

<script setup>
import { computed, defineComponent, h, inject, nextTick, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import MonacoEditor from '@/components/MonacoEditor.vue'
import WikiInfobox from '@/components/wiki/WikiInfobox.vue'
import WikiMarkdown from '@/components/wiki/WikiMarkdown.vue'
import { WIKI_EDITOR_KEY } from '@/components/wiki/wikiEditorKey.js'
import { useMobileViewport } from '@/composables/useMobileViewport'

const { isMobile } = useMobileViewport()

/**
 * @typedef {import('@/utils/wikiContent.js').WikiContentNode} WikiContentNode
 */

const props = defineProps({
  /** @type {import('vue').PropType<WikiContentNode>} */
  node: {
    type: Object,
    required: true,
  },
  depth: {
    type: Number,
    default: 0,
  },
  parentNumber: {
    type: String,
    default: '',
  },
  childIndex: {
    type: Number,
    default: 0,
  },
})

const editor = inject(WIKI_EDITOR_KEY)
if (!editor) {
  throw new Error('WikiSectionBlock 需要在 WikiDetail 内使用')
}

const monacoRef = ref(null)

const isEditMode = computed(() => editor.editMode.value)

const hasChildren = computed(() => (props.node.children?.length ?? 0) > 0)

const showHeading = computed(
  () => props.node.section !== 'main' && Boolean(props.node.title)
)

const headingTag = computed(() => {
  const level = Math.min(Math.max(props.depth, 1) + 1, 6)
  return `h${level}`
})

const headingSizeClass = computed(() => {
  if (props.depth <= 1) return 'text-xl'
  if (props.depth === 2) return 'text-lg'
  return 'text-base'
})

const displayNumber = computed(() => {
  if (props.node.section === 'main') return ''
  if (props.parentNumber) {
    return `${props.parentNumber}.${props.childIndex}`
  }
  return String(props.childIndex || '')
})

const isEditingContent = computed(
  () => editor.editingContentId.value === props.node.section
)

const contentDraftModel = computed({
  get: () => editor.contentDraft.value,
  set: (val) => {
    editor.contentDraft.value = val
  },
})

const editorHeight = computed(() => {
  if (props.node.section === 'main') return 320
  if (props.depth <= 1) return 300
  if (props.depth === 2) return 260
  return 240
})

watch(isEditingContent, async (editing) => {
  if (!editing) return
  await nextTick()
  requestAnimationFrame(() => {
    monacoRef.value?.layout?.()
  })
})

const actionBtnClass =
  'p-1 rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors'
const actionBtnDangerClass =
  'p-1 rounded text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors'

const SectionEditActions = defineComponent({
  name: 'SectionEditActions',
  props: {
    sectionId: { type: String, required: true },
    hasInfobox: { type: Boolean, default: false },
  },
  setup(sectionProps) {
    return () => {
      if (!editor.editMode.value) return null

      const buttons = [
        h(
          'button',
          {
            type: 'button',
            class: actionBtnClass,
            title: '编辑正文',
            onClick: () => editor.startEditContent(sectionProps.sectionId),
          },
          [h(Icon, { icon: 'mdi:pencil-outline', class: 'text-lg' })]
        ),
      ]

      if (sectionProps.hasInfobox) {
        buttons.push(
          h(
            'button',
            {
              type: 'button',
              class: actionBtnClass,
              title: '编辑信息框',
              onClick: () => editor.openInfoboxEditor(sectionProps.sectionId),
            },
            [h(Icon, { icon: 'mdi:table-edit', class: 'text-lg' })]
          ),
          h(
            'button',
            {
              type: 'button',
              class: actionBtnDangerClass,
              title: '删除信息框',
              onClick: () => editor.removeInfobox(sectionProps.sectionId),
            },
            [h(Icon, { icon: 'mdi:close-circle-outline', class: 'text-lg' })]
          )
        )
      } else {
        buttons.push(
          h(
            'button',
            {
              type: 'button',
              class: actionBtnClass,
              title: '添加信息框',
              onClick: () => editor.addInfobox(sectionProps.sectionId),
            },
            [h(Icon, { icon: 'mdi:table-plus', class: 'text-lg' })]
          )
        )
      }

      return h('div', { class: 'flex items-center gap-0.5 shrink-0' }, buttons)
    }
  },
})
</script>

<style scoped>
.wiki-mobile-infobox{border:1px solid #e2e8f0;border-radius:10px;padding:10px 12px;margin-bottom:18px;background:#f8fafc;display:flow-root}
.wiki-mobile-infobox summary{font-size:14px;font-weight:600;line-height:24px;min-height:30px;cursor:pointer;color:#475569}
.wiki-mobile-infobox :deep(.wiki-infobox){float:none;width:100%;margin:10px 0 0;overflow-wrap:anywhere}
.wiki-mobile-infobox :deep(table){table-layout:fixed}
.wiki-section-body--editing {
  display: flow-root;
  width: 100%;
  clear: both;
}
</style>
