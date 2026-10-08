<template>
  <component :is="isMobile ? MobileSheet : 'el-dialog'"
    v-model="visible"
    :title="dialogTitle"
    width="560px"
    destroy-on-close
    @closed="handleClosed"
  >
    <el-form label-position="top">
      <div class="mb-4 rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-600">
        绑定目标：<span class="font-medium text-gray-800">{{ targetNodeName }}</span>
      </div>
      <el-form-item label="公开接口名称" required>
        <el-input v-model="form.interfaceName" placeholder="请输入封装节点 Handle 名称" />
      </el-form-item>
      <el-form-item :label="targetPortLabel" required>
        <div v-if="isMobile" class="mobile-binding-ports">
          <p>{{ targetPortPlaceholder }}</p>
          <div v-for="handle in handles" :key="handle.port_id || handle.id" class="mobile-binding-port"><el-checkbox :model-value="form.targetPortIds.includes(handle.port_id || handle.id)" @change="togglePort(handle.port_id || handle.id, $event)"><strong>{{ handle.relabel || handle.label || handle.handle_name || handle.port_id || handle.id }}</strong><small>{{ handle.description || handle.port_id || handle.id }}</small></el-checkbox></div>
          <p v-if="!handles.length" role="status">此节点暂无可绑定端口。</p>
          <el-alert v-if="missingPortIds.length" title="原绑定包含已不可用的端口，请移除后重新选择。" type="warning" :closable="false" />
          <el-button v-for="id in missingPortIds" :key="id" plain type="danger" @click="togglePort(id, false)">移除失效端口 {{ id }}</el-button>
          <span>已选 {{ form.targetPortIds.length }} 个端口</span>
        </div>
        <el-select
          v-else
          v-model="form.targetPortIds"
          class="w-full"
          multiple
          collapse-tags
          :placeholder="targetPortPlaceholder"
        >
          <el-option
            v-for="handle in handles"
            :key="handle.port_id || handle.id"
            :label="handle.relabel || handle.label || handle.handle_name"
            :value="handle.port_id || handle.id"
          />
        </el-select>
      </el-form-item>
      <el-alert
        :title="bindingDescription"
        type="info"
        :closable="false"
        show-icon
      />
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :disabled="!canSubmit" @click="submit">确认绑定</el-button>
    </template>
  </component>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
const { isMobile } = useMobileViewport()
import {
  getBindableHandles,
  getBoundaryDirection,
  getBoundaryHandle
} from '@/utils/action/boundaryBinding'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  boundaryNode: { type: Object, default: null },
  targetNode: { type: Object, default: null },
  availableHandles: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value)
})
const form = reactive({ interfaceName: '', targetPortIds: [] })
const confirmed = ref(false)
const direction = computed(() => getBoundaryDirection(props.boundaryNode))
const boundaryHandle = computed(() => getBoundaryHandle(props.boundaryNode))
const handles = computed(() => (
  props.availableHandles.length > 0
    ? props.availableHandles
    : getBindableHandles(props.boundaryNode, props.targetNode)
))
const targetNodeName = computed(() => props.targetNode?.data?.config?.name || '未知节点')
const dialogTitle = computed(() => (
  direction.value === 'input' ? '绑定蓝图输入' : '绑定蓝图输出'
))
const targetPortLabel = computed(() => (
  direction.value === 'input'
    ? '替代目标节点的输出端口'
    : '替代目标节点的输入端口'
))
const targetPortPlaceholder = computed(() => (
  direction.value === 'input'
    ? '请选择由父流程输入替代的输出端口'
    : '请选择要作为父流程输出的输入端口'
))
const bindingDescription = computed(() => (
  direction.value === 'input'
    ? '封装运行时目标节点不会执行，父流程输入将替代所选端口原本产生的数据；独立运行时目标节点仍正常执行。'
    : '封装运行时目标节点不会执行，流入所选端口的数据将直接返回父流程；独立运行时目标节点仍正常执行。'
))
const missingPortIds = computed(() => form.targetPortIds.filter(id => !handles.value.some(handle => (handle.port_id || handle.id) === id)))
const canSubmit = computed(() => Boolean(form.interfaceName.trim() && form.targetPortIds.length > 0 && !missingPortIds.value.length))

watch(
  () => [props.boundaryNode?.id, props.targetNode?.id, props.modelValue],
  () => {
    if (!props.modelValue) return
    confirmed.value = false
    const nameInput = (props.boundaryNode?.data?.config?.inputs || []).find(
      input => input.name === 'interface_name'
    )
    form.interfaceName = nameInput ? props.boundaryNode?.data?.[nameInput.id] || '' : ''
    const binding = props.boundaryNode?.data?.boundaryBinding
    form.targetPortIds = binding?.bound_node_id === props.targetNode?.id
      ? (binding.port_mappings || []).map(mapping => mapping.target_port_id)
      : []
  }, { immediate: true }
)

/** """按项选择端口，保留原来的端口 ID 与选择顺序。""" */
function togglePort(id, selected) {
  if (selected && !form.targetPortIds.includes(id)) form.targetPortIds = [...form.targetPortIds, id]
  else if (!selected) form.targetPortIds = form.targetPortIds.filter(value => value !== id)
}

const submit = () => {
  if (!props.modelValue || !canSubmit.value || confirmed.value) return
  confirmed.value = true
  emit('confirm', {
    interfaceName: form.interfaceName.trim(),
    targetPortIds: [...form.targetPortIds],
    interfacePortId: props.boundaryNode?.data?.interfacePortId,
    boundaryHandleId: boundaryHandle.value?.port_id || boundaryHandle.value?.id
  })
  visible.value = false
}

const handleClosed = () => {
  if (!confirmed.value) emit('cancel')
  confirmed.value = false
}
</script>

<style scoped>
.mobile-binding-ports { display: grid; gap: 10px; width: 100%; }.mobile-binding-ports > p, .mobile-binding-ports > span { font-size: 12px; color: #64748b; line-height: 1.75; overflow-wrap: anywhere; }
.mobile-binding-port { border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px; }.mobile-binding-port :deep(.el-checkbox) { min-height: 44px; height: auto; width: 100%; margin: 0; white-space: normal; }.mobile-binding-port :deep(.el-checkbox__label) { min-width: 0; white-space: normal; overflow-wrap: anywhere; }.mobile-binding-port strong, .mobile-binding-port small { display: block; }.mobile-binding-port small { font-size: 11px; color: #94a3b8; margin-top: 5px; }
@media (max-width: 767px) { :deep(.el-input__wrapper) { min-height: 44px; }.mobile-binding-ports .el-button { min-height: 44px; height: auto; white-space: normal; overflow-wrap: anywhere; margin: 0; } }
</style>
