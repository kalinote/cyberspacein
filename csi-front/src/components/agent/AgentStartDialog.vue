<!--
  分析引擎启动弹窗 (AgentStartDialog)

  提供启动分析引擎前的参数配置界面，对应 POST /agent/start 的请求体字段。
  通常由 AgentStartButton 内嵌使用；若需自定义提交逻辑，也可单独引用并监听 confirm 事件。

  使用场景：
  - 需要让用户选择分析引擎、编辑 injection_param、填写初始 user_prompt、设置 merge_user_prompts / auto_approve
  - 详情页启动前预填实体参数（entity_uuid、entity_type）
  - AgentMonitor 从卡片入口预填 agent_id

  单独使用示例：
  <template>
    <el-button @click="dialogVisible = true">运行分析引擎</el-button>
    <AgentStartDialog
      v-model="dialogVisible"
      :agent-options="agentOptions"
      :default-injection-param="defaultInjectionParam"
      :preselected-agent-id="preselectedAgentId"
      :submit-loading="submitting"
      @confirm="handleStartConfirm"
    />
  </template>

  <script setup>
  import AgentStartDialog from '@/components/agent/AgentStartDialog.vue'
  import { agentApi } from '@/api/agent'

  const dialogVisible = ref(false)
  const submitting = ref(false)
  const defaultInjectionParam = { entity_uuid: 'xxx', entity_type: 'article' }

  async function handleStartConfirm(payload) {
    // payload: { agent_id, injection_param, auto_approve, merge_user_prompts?, user_prompt? }
    submitting.value = true
    try {
      const res = await agentApi.startAgent(payload)
      if (res.code === 0) dialogVisible.value = false
    } finally {
      submitting.value = false
    }
  }
  </script>

  Props:
  - modelValue (Boolean): 弹窗显隐，支持 v-model
  - agentOptions (Array, 默认: []): 分析引擎下拉选项，格式 { label, value }
  - defaultInjectionParam (Object, 默认: {}): 打开时预填到执行参数编辑器
  - preselectedAgentId (String, 默认: ''): 打开时预选的分析引擎 ID
  - submitLoading (Boolean, 默认: false): 确定按钮加载状态

  Events:
  - update:modelValue: 弹窗显隐变化
  - confirm: 校验通过后触发，参数为 startAgent 请求体
-->
<template>
  <el-dialog
    v-model="visible"
    title="运行分析引擎"
    :width="dialogWidth"
    :close-on-click-modal="false"
    destroy-on-close
    @open="onOpen"
    @closed="onClosed"
  >
    <el-form label-width="120px" class="agent-start-form">
      <el-form-item label="分析引擎" required>
        <el-select
          v-model="form.agentId"
          placeholder="请选择分析引擎"
          filterable
          class="w-full"
        >
          <el-option
            v-for="opt in agentOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="执行参数" class="agent-start-form-item-block">
        <TypedDictParamsEditor
          ref="paramsEditorRef"
          v-model="form.paramRows"
          title="执行参数 (injection_param)"
        />
      </el-form-item>

      <el-form-item label="初始用户提示词" class="agent-start-form-item-block">
        <div class="w-full min-w-0">
          <MarkdownPromptField v-model="form.userPrompt" :min-height="200" />
          <p class="text-xs text-gray-400 mt-1">{{ userPromptHint }}</p>
        </div>
      </el-form-item>

      <el-form-item label="合并提示词">
        <div class="w-full min-w-0">
          <div class="flex items-center gap-2">
            <el-switch v-model="form.mergeUserPrompts" size="small" />
            <span class="text-sm text-gray-600">合并模板与请求提示词</span>
            <el-tooltip
              content="开启后将提示词模板的 user_prompt（前）与上方输入（后）分别渲染后合并，中间空一行"
              placement="top"
            >
              <Icon icon="mdi:help-circle-outline" class="text-gray-400 text-base cursor-help" />
            </el-tooltip>
          </div>
          <p class="text-xs text-gray-400 mt-1">
            关闭时：优先使用输入的初始用户提示词，留空则使用模板默认；开启时：请求提示词必填
          </p>
        </div>
      </el-form-item>

      <el-form-item label="自动执行">
        <div class="w-full min-w-0">
          <AgentAutoApproveSwitch />
          <p class="text-xs text-gray-400 mt-1">开启后工具调用无需人工审批</p>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitLoading" @click="handleConfirm">
        确定运行
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import TypedDictParamsEditor from '@/components/agent/TypedDictParamsEditor.vue'
import MarkdownPromptField from '@/components/agent/MarkdownPromptField.vue'
import AgentAutoApproveSwitch from '@/components/agent/AgentAutoApproveSwitch.vue'
import { getAgentAutoApproveValue } from '@/composables/useAgentAutoApprove'
import {
  objectToParamRows,
  buildObjectFromParamRows,
  validateParamRows,
} from '@/utils/typedDictParams'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  agentOptions: {
    type: Array,
    default: () => [],
  },
  defaultInjectionParam: {
    type: Object,
    default: () => ({}),
  },
  preselectedAgentId: {
    type: String,
    default: '',
  },
  submitLoading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue', 'confirm'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const paramsEditorRef = ref(null)

const form = reactive({
  agentId: '',
  paramRows: [],
  userPrompt: '',
  mergeUserPrompts: false,
})

const userPromptHint = computed(() =>
  form.mergeUserPrompts
    ? '请填写补充内容，初始用户提示词将与预置模板用户提示词合并'
    : '可留空，将使用分析引擎绑定的默认用户提示词模板'
)

const dialogWidth = computed(() => {
  const hasComplexParam = form.paramRows.some(
    (row) => row.valueType === 'array' || row.valueType === 'object'
  )
  return hasComplexParam ? 'min(1100px, 96vw)' : '760px'
})

function resetForm() {
  form.agentId = props.preselectedAgentId || props.agentOptions[0]?.value || ''
  form.paramRows = objectToParamRows(props.defaultInjectionParam || {})
  form.userPrompt = ''
  form.mergeUserPrompts = false
}

function onOpen() {
  resetForm()
}

function onClosed() {
  paramsEditorRef.value?.resetValuePanelState?.()
}

function handleConfirm() {
  if (!form.agentId) {
    ElMessage.warning('请选择分析引擎')
    return
  }

  const paramError = validateParamRows(form.paramRows)
  if (paramError) {
    ElMessage.warning(paramError)
    return
  }

  const trimmedPrompt = form.userPrompt?.trim()

  if (form.mergeUserPrompts && !trimmedPrompt) {
    ElMessage.warning('开启合并提示词时，初始用户提示词不能为空')
    return
  }

  const payload = {
    agent_id: form.agentId,
    injection_param: buildObjectFromParamRows(form.paramRows),
    auto_approve: getAgentAutoApproveValue(),
  }

  if (form.mergeUserPrompts) {
    payload.merge_user_prompts = true
    payload.user_prompt = trimmedPrompt
  } else if (trimmedPrompt) {
    payload.user_prompt = trimmedPrompt
  }

  emit('confirm', payload)
}
</script>

<style scoped>
.agent-start-form :deep(.el-form-item__content) {
  flex: 1;
  min-width: 0;
}

.agent-start-form-item-block :deep(.el-form-item__content) {
  display: block;
}
</style>
