<template>
  <el-dialog
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
        <el-select
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
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
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
const canSubmit = computed(() => form.interfaceName.trim() && form.targetPortIds.length > 0)

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
  }
)

const submit = () => {
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
