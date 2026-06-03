<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="96%"
    top="4vh"
    class="skill-editor-dialog"
    destroy-on-close
    :close-on-click-modal="false"
    :before-close="handleBeforeClose"
    @open="onOpen"
    @closed="onClosed"
  >
    <div v-loading="detailLoading" element-loading-text="加载中..." class="skill-editor-body flex gap-4">
      <div class="skill-editor-tree w-70 shrink-0 rounded-lg border border-gray-200 p-2 overflow-y-auto">
        <el-tree
          v-if="treeData.length"
          ref="treeRef"
          :data="treeData"
          node-key="id"
          :props="{ label: 'label', children: 'children' }"
          highlight-current
          default-expand-all
          @node-click="handleTreeNodeClick"
        >
          <template #default="{ data }">
            <div class="flex items-center gap-1.5 min-w-0 py-0.5">
              <Icon
                :icon="data.isFile ? 'mdi:file-document-outline' : 'mdi:folder-outline'"
                class="shrink-0 text-gray-500"
              />
              <span class="truncate text-sm">{{ data.label }}</span>
            </div>
          </template>
        </el-tree>
        <div v-else-if="!detailLoading" class="text-sm text-gray-400 text-center py-8">暂无文件</div>
      </div>

      <div class="flex-1 min-w-0 min-h-0 h-full flex flex-col border border-gray-200 rounded-lg overflow-hidden">
        <div class="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-gray-50">
          <span class="text-sm text-gray-600 truncate font-mono">{{ currentPath || '请选择文件' }}</span>
          <el-radio-group
            v-if="currentPath && showPreviewToggle"
            v-model="viewMode"
            size="small"
          >
            <el-radio-button value="edit">编辑</el-radio-button>
            <el-radio-button value="preview">预览</el-radio-button>
          </el-radio-group>
        </div>

        <div
          v-loading="contentLoading"
          element-loading-text="加载中..."
          class="skill-editor-pane flex-1 min-h-0 p-3"
        >
          <template v-if="currentPath">
            <div v-if="viewMode === 'edit'" class="skill-editor-editor-wrap h-full min-h-0">
              <MonacoEditor
                v-model="editorContent"
                :language="editorLanguage"
                :min-height="editorPaneHeight"
              />
            </div>
            <div
              v-else
              class="skill-editor-preview-wrap h-full min-h-0 overflow-y-auto rounded border border-gray-100 bg-white p-4"
            >
              <MarkdownViewer :content="editorContent" custom-class="skill-editor-preview" />
            </div>
          </template>
          <div v-else class="skill-editor-empty flex flex-col items-center justify-center h-full text-gray-400">
            <Icon icon="mdi:file-tree" class="text-5xl mb-2" />
            <p class="text-sm">从左侧选择要编辑的文件</p>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="handleClose">关闭</el-button>
      <el-button
        type="primary"
        :loading="saveLoading"
        :disabled="!currentPath || !isDirty"
        @click="handleSave"
      >
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MonacoEditor from '@/components/MonacoEditor.vue'
import MarkdownViewer from '@/components/common/MarkdownViewer.vue'
import { agentApi } from '@/api/agent'
import {
  buildFileTreeFromPaths,
  findDefaultFilePath,
  getMonacoLanguageByPath,
  isMarkdownPath
} from '@/utils/skillFileTree'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  skillId: {
    type: String,
    default: ''
  },
  skillName: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'saved'])

const visible = ref(props.modelValue)
const detailLoading = ref(false)
const contentLoading = ref(false)
const saveLoading = ref(false)
const treeData = ref([])
const treeRef = ref(null)
const currentPath = ref('')
const editorContent = ref('')
const originalContent = ref('')
const viewMode = ref('edit')

/** 编辑区与预览区统一高度（px），与 CSS calc 最小高度对齐 */
const editorPaneHeight = 600

const dialogTitle = computed(() => {
  const name = props.skillName?.trim()
  return name ? `编辑技能 · ${name}` : '编辑技能'
})

const editorLanguage = computed(() => getMonacoLanguageByPath(currentPath.value))

const showPreviewToggle = computed(() => isMarkdownPath(currentPath.value))

const isDirty = computed(
  () => currentPath.value && editorContent.value !== originalContent.value
)

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val
  }
)

watch(visible, (val) => {
  emit('update:modelValue', val)
})

watch(showPreviewToggle, (canPreview) => {
  if (!canPreview && viewMode.value === 'preview') {
    viewMode.value = 'edit'
  }
})

async function confirmDiscardIfDirty() {
  if (!isDirty.value) return true
  try {
    await ElMessageBox.confirm('当前文件有未保存的修改，是否放弃？', '未保存的修改', {
      confirmButtonText: '放弃修改',
      cancelButtonText: '继续编辑',
      type: 'warning'
    })
    return true
  } catch {
    return false
  }
}

async function loadFileContent(path) {
  if (!props.skillId || !path) return

  contentLoading.value = true
  try {
    const res = await agentApi.getSkillFileContent(props.skillId, path)
    const content = res?.data?.content ?? ''
    editorContent.value = content
    originalContent.value = content
    if (!isMarkdownPath(path)) {
      viewMode.value = 'edit'
    }
  } catch (e) {
    editorContent.value = ''
    originalContent.value = ''
    console.error('加载技能文件失败:', e)
  } finally {
    contentLoading.value = false
  }
}

async function selectFile(path) {
  if (!path) return
  currentPath.value = path
  await loadFileContent(path)
  await nextTick()
  treeRef.value?.setCurrentKey(path)
}

async function handleTreeNodeClick(data) {
  if (!data?.isFile || !data.path) return
  if (data.path === currentPath.value) return

  const ok = await confirmDiscardIfDirty()
  if (!ok) {
    await nextTick()
    treeRef.value?.setCurrentKey(currentPath.value || undefined)
    return
  }

  await selectFile(data.path)
}

async function onOpen() {
  if (!props.skillId) return

  detailLoading.value = true
  treeData.value = []
  currentPath.value = ''
  editorContent.value = ''
  originalContent.value = ''
  viewMode.value = 'edit'

  try {
    const res = await agentApi.getSkillDetail(props.skillId)
    const files = Array.isArray(res?.data?.files) ? res.data.files : []
    treeData.value = buildFileTreeFromPaths(files)

    const defaultPath = findDefaultFilePath(treeData.value)
    if (defaultPath) {
      await nextTick()
      await selectFile(defaultPath)
    }
  } catch (e) {
    ElMessage.error('加载技能详情失败')
    console.error('加载技能详情失败:', e)
  } finally {
    detailLoading.value = false
  }
}

function onClosed() {
  treeData.value = []
  currentPath.value = ''
  editorContent.value = ''
  originalContent.value = ''
  viewMode.value = 'edit'
}

async function handleSave() {
  if (!props.skillId || !currentPath.value) return

  saveLoading.value = true
  try {
    await agentApi.updateSkillFileContent(props.skillId, currentPath.value, editorContent.value)
    originalContent.value = editorContent.value
    ElMessage.success('保存成功')
    if (currentPath.value === 'SKILL.md') {
      emit('saved')
    }
  } catch (e) {
    console.error('保存技能文件失败:', e)
  } finally {
    saveLoading.value = false
  }
}

async function handleClose() {
  const ok = await confirmDiscardIfDirty()
  if (!ok) return
  visible.value = false
}

async function handleBeforeClose(done) {
  const ok = await confirmDiscardIfDirty()
  if (ok) done()
}
</script>

<style scoped>
.skill-editor-dialog :deep(.el-dialog) {
  max-width: 1680px;
  margin-bottom: 2vh;
}

.skill-editor-dialog :deep(.el-dialog__header) {
  padding-bottom: 8px;
}

.skill-editor-dialog :deep(.el-dialog__body) {
  padding-top: 8px;
  max-height: calc(96vh - 100px);
  overflow: hidden;
}

.skill-editor-body {
  height: calc(92vh - 120px);
  min-height: 600px;
}

.skill-editor-tree {
  height: 100%;
  min-height: 600px;
}

.skill-editor-pane {
  height: 100%;
  min-height: 600px;
  display: flex;
  flex-direction: column;
}

.skill-editor-editor-wrap :deep(.monaco-editor-container) {
  height: 100%;
  min-height: 600px;
}

.skill-editor-preview-wrap {
  flex: 1;
  min-height: 600px;
}

.skill-editor-empty {
  min-height: 600px;
}
</style>
