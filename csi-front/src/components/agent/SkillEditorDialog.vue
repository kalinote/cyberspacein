<template>
  <component
    :is="isMobile ? ElDrawer : ElDialog"
    v-model="visible"
    :title="dialogTitle"
    width="96%"
    top="4vh"
    class="skill-editor-dialog"
    :class="{ 'agent-config-mobile-panel': isMobile }"
    :modal-class="isMobile ? 'agent-config-mobile-overlay' : undefined"
    :size="isMobile ? '100%' : undefined"
    :append-to-body="isMobile"
    destroy-on-close
    :close-on-click-modal="false"
    :before-close="handleBeforeClose"
    @open="onOpen"
    @closed="onClosed"
  >
    <template v-if="isMobile" #header><div class="agent-config-panel-heading"><el-button :disabled="saveLoading" @click="handleClose">返回</el-button><h2>{{ dialogTitle }}</h2></div></template>
    <div v-if="isMobile" class="skill-mobile-editor">
      <p v-if="detailLoading" role="status">正在加载技能文件…</p>
      <div v-if="loadError" role="alert" class="skill-mobile-error"><p>{{ loadError }}</p><el-button @click="currentPath ? loadFileContent(currentPath) : onOpen()">重新加载</el-button></div>
      <template v-if="mobileFilesVisible">
        <p class="text-sm text-gray-500 mb-4">选择一个文件进行查看或编辑</p>
        <el-tree v-if="treeData.length" :data="treeData" node-key="id" :props="{ label: 'label', children: 'children' }" default-expand-all @node-click="handleTreeNodeClick"><template #default="{ data }"><span class="skill-mobile-file"><Icon :icon="data.isFile ? 'mdi:file-document-outline' : 'mdi:folder-outline'" />{{ data.label }}</span></template></el-tree>
        <p v-else-if="!detailLoading && !loadError" class="text-gray-500">暂无文件</p>
      </template>
      <template v-else>
        <div class="skill-mobile-current"><el-button :disabled="saveLoading" @click="mobileFilesVisible = true">切换文件</el-button><span>{{ currentPath }}</span><span v-if="isDirty">未保存</span></div>
        <p v-if="contentLoading" role="status">正在读取文件…</p>
        <AgentConfigTextField v-if="currentPath && !contentLoading && !loadError" v-model="editorContent" :language="editorLanguage" />
      </template>
    </div>
    <div v-else v-loading="detailLoading" element-loading-text="加载中..." class="skill-editor-body flex gap-4">
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
        :disabled="!currentPath || !isDirty || contentLoading || Boolean(loadError) || (isMobile && (!hasPerm(PERM.operations.agent.skill.read) || !hasPerm(PERM.operations.agent.skill.update)))"
        @click="handleSave"
      >
        保存
      </el-button>
    </template>
  </component>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { Icon } from '@iconify/vue'
import { ElDialog, ElDrawer, ElMessage, ElMessageBox } from 'element-plus'
import { useMobileViewport } from '@/composables/useMobileViewport'
import AgentConfigTextField from '@/components/agent/AgentConfigTextField.vue'
import { hasPerm } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'
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
const { isMobile } = useMobileViewport()
const mobileFilesVisible = ref(true)
const loadError = ref('')
let fileGeneration = 0
let sessionGeneration = 0
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
  if (saveLoading.value) return false
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
  if (isMobile.value && !hasPerm(PERM.operations.agent.skill.read)) { loadError.value = '没有读取技能文件的权限'; return }
  const generation = ++fileGeneration
  loadError.value = ''
  contentLoading.value = true
  try {
    const res = await agentApi.getSkillFileContent(props.skillId, path)
    if (generation !== fileGeneration || !visible.value) return
    if (isMobile.value && !hasPerm(PERM.operations.agent.skill.read)) { loadError.value = '读取权限已变更'; return }
    if (typeof res?.data?.content !== 'string') throw new Error('文件内容无效，请重试')
    const content = res?.data?.content ?? ''
    editorContent.value = content
    originalContent.value = content
    if (!isMarkdownPath(path)) {
      viewMode.value = 'edit'
    }
  } catch (e) {
    if (generation !== fileGeneration) return
    loadError.value = '加载技能文件失败，请重试'
    console.error('加载技能文件失败:', e)
  } finally {
    if (generation === fileGeneration) contentLoading.value = false
  }
}

async function selectFile(path) {
  if (!path) return
  currentPath.value = path
  mobileFilesVisible.value = false
  await loadFileContent(path)
  await nextTick()
  treeRef.value?.setCurrentKey(path)
}

async function handleTreeNodeClick(data) {
  if (!data?.isFile || !data.path) return
  if (data.path === currentPath.value) { mobileFilesVisible.value = false; return }

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
  if (isMobile.value && !hasPerm(PERM.operations.agent.skill.read)) { loadError.value = '没有读取技能文件的权限'; return }

  const generation = ++sessionGeneration
  fileGeneration += 1
  loadError.value = ''
  mobileFilesVisible.value = true
  detailLoading.value = true
  treeData.value = []
  currentPath.value = ''
  editorContent.value = ''
  originalContent.value = ''
  viewMode.value = 'edit'

  try {
    const res = await agentApi.getSkillDetail(props.skillId)
    if (generation !== sessionGeneration || !visible.value) return
    if (isMobile.value && !hasPerm(PERM.operations.agent.skill.read)) { loadError.value = '读取权限已变更'; return }
    const files = Array.isArray(res?.data?.files) ? res.data.files : []
    treeData.value = buildFileTreeFromPaths(files)

    const defaultPath = findDefaultFilePath(treeData.value)
    if (defaultPath && !isMobile.value) {
      await nextTick()
      await selectFile(defaultPath)
    }
  } catch (e) {
    if (generation !== sessionGeneration) return
    loadError.value = '加载技能文件目录失败，请重试'
    ElMessage.error('加载技能详情失败')
    console.error('加载技能详情失败:', e)
  } finally {
    if (generation === sessionGeneration) detailLoading.value = false
  }
}

function onClosed() {
  sessionGeneration += 1
  fileGeneration += 1
  loadError.value = ''
  treeData.value = []
  currentPath.value = ''
  editorContent.value = ''
  originalContent.value = ''
  viewMode.value = 'edit'
}

async function handleSave() {
  if (!props.skillId || !currentPath.value || saveLoading.value || contentLoading.value || loadError.value) return
  if (isMobile.value && (!hasPerm(PERM.operations.agent.skill.read) || !hasPerm(PERM.operations.agent.skill.update))) return
  const generation = sessionGeneration
  const path = currentPath.value
  const content = editorContent.value

  saveLoading.value = true
  try {
    await agentApi.updateSkillFileContent(props.skillId, path, content)
    if (generation !== sessionGeneration || !visible.value) return
    if (isMobile.value && (!hasPerm(PERM.operations.agent.skill.read) || !hasPerm(PERM.operations.agent.skill.update))) return
    originalContent.value = content
    ElMessage.success('保存成功')
    if (path === 'SKILL.md') {
      emit('saved')
    }
  } catch (e) {
    console.error('保存技能文件失败:', e)
  } finally {
    if (generation === sessionGeneration) saveLoading.value = false
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
onBeforeRouteLeave(() => !isMobile.value || !visible.value ? true : confirmDiscardIfDirty())
onDeactivated(() => { visible.value = false; sessionGeneration += 1; fileGeneration += 1; saveLoading.value = false })
onBeforeUnmount(() => { sessionGeneration += 1; fileGeneration += 1 })
</script>

<style scoped>
.skill-mobile-editor{min-width:0}.skill-mobile-editor :deep(.el-tree-node__content){height:auto;min-height:48px}.skill-mobile-file{display:flex;gap:8px;align-items:center;white-space:normal;overflow-wrap:anywhere;font-size:14px;padding:8px 0}.skill-mobile-file svg{flex-shrink:0}.skill-mobile-current{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:16px}.skill-mobile-current>span{font-size:13px;color:#64748b;overflow-wrap:anywhere}.skill-mobile-error{border:1px solid #fed7aa;background:#fff7ed;border-radius:10px;padding:12px;margin-bottom:12px}
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
