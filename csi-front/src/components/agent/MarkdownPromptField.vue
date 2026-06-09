<!--
  Markdown 提示词编辑字段 (MarkdownPromptField)

  提供 Markdown 文本的「编辑 / 预览」Tab 切换输入体验，基于 MonacoEditor + MarkdownViewer。

  使用场景：
  - 分析引擎启动弹窗中的「初始用户提示词」(user_prompt)
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
  - readOnly (Boolean, 默认: false): 编辑 Tab 是否只读
  - minHeight (Number, 默认: 240): 编辑区与预览区最小高度（px）

  Events:
  - update:modelValue: 文本内容变化
-->
<template>
  <el-tabs v-model="activeTab" class="markdown-prompt-field w-full">
    <el-tab-pane label="编辑" name="edit">
      <div class="markdown-prompt-pane">
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
        class="markdown-prompt-pane overflow-y-auto rounded border border-gray-100 bg-white p-4"
        :style="{ minHeight: `${minHeight}px` }"
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
</template>

<script setup>
import { ref } from 'vue'
import MonacoEditor from '@/components/MonacoEditor.vue'
import MarkdownViewer from '@/components/common/MarkdownViewer.vue'

defineProps({
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
})

const emit = defineEmits(['update:modelValue'])

const activeTab = ref('edit')
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
}

.markdown-prompt-pane :deep(.monaco-editor-container) {
  width: 100%;
}
</style>
