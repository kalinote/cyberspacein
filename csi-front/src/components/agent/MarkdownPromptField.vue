<!--
  Markdown 提示词编辑字段 (MarkdownPromptField)

  提供 Markdown 文本的「编辑 / 预览 / 实时渲染」切换输入体验，基于 MonacoEditor + MarkdownViewer。

  使用场景：
  - 分析引擎启动弹窗中的「初始用户提示词」(user_prompt)
  - 提示词模板编辑弹窗中的系统/用户提示词
  - 其他需要 Markdown 编写并即时预览的表单字段

  使用方法：
  <template>
    <MarkdownPromptField
      v-model="userPrompt"
      :min-height="240"
      :read-only="false"
    />
  </template>

  <script setup>
  import MarkdownPromptField from '@/components/agent/MarkdownPromptField.vue'

  const userPrompt = ref('')
  </script>

  Props:
  - modelValue (String, 默认: ''): Markdown 文本，支持 v-model
  - readOnly (Boolean, 默认: false): 编辑区是否只读
  - minHeight (Number, 默认: 240): 内容区目标高度（px），受视口上限约束
  - layout (String, 默认: 'tabs'): 'tabs' 为 Tab 切换，'toggle' 为顶部按钮切换

  视图说明：
  - 编辑：纯 Monaco 编辑器
  - 预览：纯 Markdown 渲染
  - 实时渲染（默认）：左右分屏，左侧编辑、右侧实时预览（可拖拽分割线，滚动位置联动）

  Events:
  - update:modelValue: 文本内容变化
-->
<template>
  <div
    class="markdown-prompt-field w-full"
    :class="{ 'markdown-prompt-field--toggle': layout === 'toggle' }"
  >
    <template v-if="layout === 'toggle'">
      <div class="flex flex-col border border-gray-200 rounded-lg overflow-hidden">
        <div class="flex items-center justify-end px-4 py-2 border-b border-gray-200 bg-gray-50">
          <el-radio-group v-model="activeTab" size="small">
            <el-radio-button value="live">实时渲染</el-radio-button>
            <el-radio-button value="edit">编辑</el-radio-button>
            <el-radio-button value="preview">预览</el-radio-button>
          </el-radio-group>
        </div>
        <div class="markdown-prompt-pane p-3">
          <div v-if="activeTab === 'edit'" class="markdown-prompt-editor-wrap" :style="contentHeightStyle">
            <MonacoEditor
              :model-value="modelValue"
              language="markdown"
              :read-only="readOnly"
              :min-height="minHeight"
              @update:model-value="emit('update:modelValue', $event)"
            />
          </div>
          <div
            v-else-if="activeTab === 'preview'"
            class="markdown-prompt-preview-wrap overflow-y-auto rounded border border-gray-100 bg-white p-4"
            :style="contentHeightStyle"
          >
            <MarkdownViewer
              v-if="modelValue?.trim()"
              :content="modelValue"
              custom-class="markdown-prompt-preview"
            />
            <p v-else class="text-sm text-gray-400 text-center py-8">暂无内容</p>
          </div>
          <div
            v-else-if="activeTab === 'live'"
            class="markdown-prompt-live-wrap"
            :style="contentHeightStyle"
          >
            <Splitpanes class="default-theme markdown-prompt-splitpanes h-full" @resized="handlePaneResized">
              <Pane :size="50" :min-size="25">
                <div class="markdown-prompt-live-editor h-full min-h-0 overflow-hidden">
                  <MonacoEditor
                    ref="liveEditorRef"
                    :model-value="modelValue"
                    language="markdown"
                    :read-only="readOnly"
                    :min-height="minHeight"
                    @update:model-value="emit('update:modelValue', $event)"
                    @ready="setupScrollSync"
                  />
                </div>
              </Pane>
              <Pane :size="50" :min-size="25">
                <div
                  ref="livePreviewRef"
                  class="markdown-prompt-live-preview h-full min-h-0 overflow-y-auto rounded border border-gray-100 bg-white p-4"
                >
                  <MarkdownViewer
                    v-if="modelValue?.trim()"
                    :content="modelValue"
                    custom-class="markdown-prompt-preview"
                  />
                  <p v-else class="text-sm text-gray-400 text-center py-8">暂无内容</p>
                </div>
              </Pane>
            </Splitpanes>
          </div>
        </div>
      </div>
    </template>
    <el-tabs v-else v-model="activeTab" class="w-full">
      <el-tab-pane label="实时渲染" name="live">
        <div class="markdown-prompt-live-wrap" :style="contentHeightStyle">
          <Splitpanes class="default-theme markdown-prompt-splitpanes h-full" @resized="handlePaneResized">
            <Pane :size="50" :min-size="25">
              <div class="markdown-prompt-live-editor h-full min-h-0 overflow-hidden">
                <MonacoEditor
                  ref="liveEditorRef"
                  :model-value="modelValue"
                  language="markdown"
                  :read-only="readOnly"
                  :min-height="minHeight"
                  @update:model-value="emit('update:modelValue', $event)"
                  @ready="setupScrollSync"
                />
              </div>
            </Pane>
            <Pane :size="50" :min-size="25">
              <div
                ref="livePreviewRef"
                class="markdown-prompt-live-preview h-full min-h-0 overflow-y-auto rounded border border-gray-100 bg-white p-4"
              >
                <MarkdownViewer
                  v-if="modelValue?.trim()"
                  :content="modelValue"
                  custom-class="markdown-prompt-preview"
                />
                <p v-else class="text-sm text-gray-400 text-center py-8">暂无内容</p>
              </div>
            </Pane>
          </Splitpanes>
        </div>
      </el-tab-pane>
      <el-tab-pane label="编辑" name="edit">
        <div class="markdown-prompt-pane" :style="contentHeightStyle">
          <MonacoEditor
            :model-value="modelValue"
            language="markdown"
            :read-only="readOnly"
            :min-height="minHeight"
            @update:model-value="emit('update:modelValue', $event)"
          />
        </div>
      </el-tab-pane>
      <el-tab-pane label="预览" name="preview">
        <div
          class="markdown-prompt-pane markdown-prompt-preview-wrap overflow-y-auto rounded border border-gray-100 bg-white p-4"
          :style="contentHeightStyle"
        >
          <MarkdownViewer
            v-if="modelValue?.trim()"
            :content="modelValue"
            custom-class="markdown-prompt-preview"
          />
          <p v-else class="text-sm text-gray-400 text-center py-8">暂无内容</p>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount, nextTick } from 'vue'
import { Splitpanes, Pane } from 'splitpanes'
import 'splitpanes/dist/splitpanes.css'
import MonacoEditor from '@/components/MonacoEditor.vue'
import MarkdownViewer from '@/components/common/MarkdownViewer.vue'
import { bindMarkdownLiveScrollSync } from '@/utils/markdownLiveScrollSync'

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  readOnly: {
    type: Boolean,
    default: false,
  },
  minHeight: {
    type: Number,
    default: 240,
  },
  layout: {
    type: String,
    default: 'tabs',
    validator: (value) => ['tabs', 'toggle'].includes(value),
  },
})

const emit = defineEmits(['update:modelValue'])

const activeTab = ref('live')
const liveEditorRef = ref(null)
const livePreviewRef = ref(null)

let disposeScrollSync = null

/** 编辑区与预览区统一高度，避免预览撑破弹窗 */
const contentHeightStyle = computed(() => ({
  height: `min(${props.minHeight}px, calc(100vh - 320px))`,
}))

function teardownScrollSync() {
  disposeScrollSync?.()
  disposeScrollSync = null
}

async function setupScrollSync() {
  teardownScrollSync()
  if (activeTab.value !== 'live') return

  await nextTick()

  const editor = liveEditorRef.value?.getEditor?.()
  const preview = livePreviewRef.value
  if (!editor || !preview) return

  disposeScrollSync = bindMarkdownLiveScrollSync(editor, preview)
}

function handlePaneResized() {
  liveEditorRef.value?.layout()
}

watch(activeTab, (tab) => {
  if (tab === 'live') {
    setupScrollSync()
  } else {
    teardownScrollSync()
  }
})

onBeforeUnmount(() => {
  teardownScrollSync()
})
</script>

<style scoped>
.markdown-prompt-field {
  width: 100%;
}

.markdown-prompt-field :deep(.el-tabs__header) {
  margin-bottom: 8px;
}

.markdown-prompt-field :deep(.el-tabs__content) {
  width: 100%;
  overflow: visible;
}

.markdown-prompt-field :deep(.el-tab-pane) {
  width: 100%;
}

.markdown-prompt-pane {
  width: 100%;
  box-sizing: border-box;
}

.markdown-prompt-pane :deep(.monaco-editor-container) {
  width: 100%;
  height: 100%;
  min-height: 0 !important;
}

.markdown-prompt-field--toggle .markdown-prompt-editor-wrap,
.markdown-prompt-field--toggle .markdown-prompt-preview-wrap {
  width: 100%;
  box-sizing: border-box;
}

.markdown-prompt-field--toggle .markdown-prompt-editor-wrap {
  overflow: hidden;
}

.markdown-prompt-field--toggle .markdown-prompt-editor-wrap :deep(.monaco-editor-container) {
  height: 100%;
  min-height: 0;
}

.markdown-prompt-field--toggle .markdown-prompt-preview-wrap {
  overflow-y: auto;
}

.markdown-prompt-field:not(.markdown-prompt-field--toggle) .markdown-prompt-pane :deep(.monaco-editor-container) {
  height: 100%;
  min-height: 0;
}

.markdown-prompt-live-wrap {
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.markdown-prompt-live-editor :deep(.monaco-editor-container) {
  width: 100%;
  height: 100%;
  min-height: 0 !important;
}

.markdown-prompt-splitpanes :deep(.splitpanes__pane) {
  overflow: hidden;
}

.markdown-prompt-splitpanes :deep(.splitpanes__splitter) {
  box-sizing: border-box;
  flex-shrink: 0;
  position: relative;
  background-color: rgb(249 250 251);
  width: 7px;
  min-width: 7px;
  margin-left: -1px;
  border-left: 1px solid rgb(243 244 246);
  cursor: col-resize;
}

.markdown-prompt-splitpanes :deep(.splitpanes__splitter::before),
.markdown-prompt-splitpanes :deep(.splitpanes__splitter::after) {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 1px;
  height: 30px;
  background-color: rgb(0 0 0 / 0.15);
  transform: translateY(-50%);
  transition: background-color 0.2s;
}

.markdown-prompt-splitpanes :deep(.splitpanes__splitter::before) {
  margin-left: -2px;
}

.markdown-prompt-splitpanes :deep(.splitpanes__splitter::after) {
  margin-left: 1px;
}

.markdown-prompt-splitpanes :deep(.splitpanes__splitter:hover::before),
.markdown-prompt-splitpanes :deep(.splitpanes__splitter:hover::after) {
  background-color: rgb(0 0 0 / 0.3);
}
</style>
