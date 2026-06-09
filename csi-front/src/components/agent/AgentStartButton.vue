<!--
  分析引擎启动按钮 (AgentStartButton)

  封装「触发按钮 + 启动弹窗 + 调用 /agent/start」的完整流程，是各页面启动分析引擎的推荐入口。

  使用场景：
  - 会话列表页「运行分析引擎」
  - 文章/论坛详情页「分析此实体」（需预填 entity_uuid、entity_type）
  - AgentMonitor 卡片「运行」（需预填 preselectedAgentId）

  使用方法：
  <template>
    <AgentStartButton
      button-text="运行分析引擎"
      loading-text="启动中..."
      :agent-options="agentOptions"
      :default-injection-param="{ entity_uuid: '...', entity_type: 'article' }"
      :preselected-agent-id="''"
      icon="mdi:play-circle-outline"
      compact
      element-primary
      block
      @started="handleAgentStarted"
    />
  </template>

  <script setup>
  import AgentStartButton from '@/components/agent/AgentStartButton.vue'
  import { agentApi } from '@/api/agent'

  const agentOptions = ref([])

  async function loadAgentOptions() {
    const res = await agentApi.getAgentsConfigList()
    agentOptions.value = (res?.data || []).map((item) => ({
      label: item.name,
      value: item.id,
    }))
  }

  function handleAgentStarted({ agentId, sessionId, payload }) {
    // 跳转详情页、切换内嵌分析面板等后续逻辑由父组件自行处理
  }
  </script>

  Props:
  - buttonText (String, 必需): 按钮显示文本
  - loadingText (String, 默认: '启动中...'): 加载状态文本
  - disabled (Boolean, 默认: false): 是否禁用按钮
  - loading (Boolean, 默认: false): 外部加载状态（与内部 API 请求状态合并）
  - agentOptions (Array, 默认: []): 分析引擎选项，格式 { label, value }
  - defaultInjectionParam (Object, 默认: {}): 弹窗打开时预填的执行参数（injection_param）
  - preselectedAgentId (String, 默认: ''): 弹窗打开时预选的分析引擎 ID
  - icon (String, 默认: 'mdi:play-circle-outline'): 按钮图标
  - compact (Boolean, 默认: false): 紧凑尺寸（工具栏场景）
  - elementPrimary (Boolean, 默认: false): 使用 Element Plus 主题色
  - block (Boolean, 默认: false): 按钮是否占满容器宽度

  Events:
  - started: 启动成功，参数 { agentId, sessionId, payload }
  - update:loading: 内部 API 请求加载状态变化

  Expose:
  - openDialog(): 编程式打开启动弹窗
-->
<template>
  <div :class="block ? 'w-full' : 'inline-flex'">
    <button
      type="button"
      :disabled="disabled || loading || !agentOptions.length"
      :class="buttonClass"
      @click="openDialog"
    >
      <Icon v-if="icon" :icon="loading ? 'mdi:loading' : icon" :class="{ 'animate-spin': loading }" />
      <span>{{ loading ? loadingText : buttonText }}</span>
    </button>

    <AgentStartDialog
      v-model="dialogVisible"
      :agent-options="agentOptions"
      :default-injection-param="defaultInjectionParam"
      :preselected-agent-id="preselectedAgentId"
      :submit-loading="loading"
      @confirm="handleConfirm"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import AgentStartDialog from '@/components/agent/AgentStartDialog.vue'
import { agentApi } from '@/api/agent'

const props = defineProps({
  buttonText: {
    type: String,
    required: true,
  },
  loadingText: {
    type: String,
    default: '启动中...',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  loading: {
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
  icon: {
    type: String,
    default: 'mdi:play-circle-outline',
  },
  compact: {
    type: Boolean,
    default: false,
  },
  elementPrimary: {
    type: Boolean,
    default: false,
  },
  block: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['started', 'update:loading'])

const dialogVisible = ref(false)
const internalLoading = ref(false)

const loading = computed(() => props.loading || internalLoading.value)

const PRIMARY_CLASS =
  'text-white font-medium transition-colors flex items-center justify-center gap-1.5 bg-[var(--el-color-primary)] hover:bg-[var(--el-color-primary-light-3)] disabled:bg-[var(--el-color-primary-light-5)] disabled:cursor-not-allowed rounded-md'
const LEGACY_CLASS =
  'bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white font-medium transition-colors flex items-center justify-center gap-2 rounded-lg'

const buttonClass = computed(() => {
  const size = props.compact ? 'h-8 text-sm px-3' : 'py-3 px-4'
  const width = props.block ? 'w-full' : ''
  const base = props.elementPrimary ? PRIMARY_CLASS : LEGACY_CLASS
  return `${base} ${size} ${width}`
})

function openDialog() {
  if (!props.agentOptions.length) {
    ElMessage.warning('暂无可用的分析引擎')
    return
  }
  dialogVisible.value = true
}

async function handleConfirm(payload) {
  internalLoading.value = true
  emit('update:loading', true)
  try {
    const response = await agentApi.startAgent(payload)

    if (response.code === 0 && response.data?.agent_id) {
      const sessionId = response.data.session_id
      if (!sessionId) {
        ElMessage.error('未返回 session_id，无法继续')
        return
      }
      dialogVisible.value = false
      ElMessage.success('分析引擎已启动')
      emit('started', {
        agentId: String(response.data.agent_id),
        sessionId: String(sessionId),
        payload,
      })
    } else {
      ElMessage.error(response.message || '启动分析引擎失败')
    }
  } catch (err) {
    console.error('启动分析引擎失败:', err)
    ElMessage.error('启动分析引擎失败，请稍后重试')
  } finally {
    internalLoading.value = false
    emit('update:loading', false)
  }
}

defineExpose({ openDialog })
</script>
