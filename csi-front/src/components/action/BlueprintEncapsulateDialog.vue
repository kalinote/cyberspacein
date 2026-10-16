<template>
  <component :is="isMobile ? MobileSheet : 'el-dialog'" v-model="visible" :title="isMobile ? `封装为节点 · ${mobileStep + 1}/2` : '封装为节点'" width="680px" destroy-on-close :close-on-click-modal="!submitting" :close-on-press-escape="!submitting" :show-close="!submitting">
    <el-form label-position="top" :class="{ 'mobile-encapsulate-form': isMobile }">
      <div v-show="!isMobile || mobileStep === 0">
      <el-form-item label="封装节点名称" required>
        <el-input v-model="form.node_name" placeholder="请输入节点名称" />
      </el-form-item>
      <el-form-item label="说明">
        <el-input v-model="form.description" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="发布方式">
        <el-radio-group v-model="form.mode">
          <el-radio value="create">创建新的封装节点</el-radio>
          <el-radio value="add_version">为已有封装节点增加版本</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="form.mode === 'add_version'" label="已有封装节点" required>
        <el-select
          v-model="form.target_encapsulated_node_id"
          class="w-full"
          placeholder="请选择要增加版本的封装节点"
        >
          <el-option
            v-for="node in targetNodes"
            :key="node.id"
            :label="`${node.name}（v${node.definition_version || 1}）`"
            :value="node.id"
          />
        </el-select>
        <p v-if="targetNodes.length === 0" class="mt-2 text-xs text-amber-600">
          当前蓝图尚未生成过封装节点，请选择“创建新的封装节点”。
        </p>
      </el-form-item>
      </div>
      <div v-show="!isMobile || mobileStep === 1">
      <div v-if="isMobile" class="mobile-encapsulate-review"><strong>{{ form.node_name }}</strong><p>{{ form.description || '暂无说明' }}</p><p>{{ form.mode === 'create' ? '创建新的封装节点' : `增加版本：${targetNodes.find(node => node.id === form.target_encapsulated_node_id)?.name || '未选择节点'}` }}</p></div>
      <el-divider content-position="left">{{ isMobile ? '确认公开接口' : '公开 Handles 预览' }}</el-divider>
      <el-empty v-if="interfaces.length === 0" description="当前蓝图没有公开接口" :image-size="48" />
      <div v-else-if="isMobile" class="mobile-interface-list"><article v-for="(port, index) in interfaces" :key="port.id || index"><strong>{{ port.label || port.name }}</strong><p>{{ port.direction === 'input' ? '输入' : '输出' }} · {{ port.interfaceTypeId }}</p><p v-if="port.description">{{ port.description }}</p></article></div>
      <el-table v-else :data="interfaces" size="small">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="direction" label="方向" width="100" />
        <el-table-column prop="interfaceTypeId" label="接口类型" />
      </el-table>
      </div>
    </el-form>
    <template #footer>
      <el-button :disabled="submitting" @click="isMobile && mobileStep > 0 ? mobileStep-- : visible = false">{{ isMobile && mobileStep > 0 ? '上一步' : '取消' }}</el-button>
      <el-button v-if="isMobile && mobileStep === 0" type="primary" :disabled="!canSubmit" @click="mobileStep = 1">核对接口</el-button>
      <el-button v-else type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">
        校验并封装
      </el-button>
    </template>
  </component>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { useMobileViewport } from '@/composables/useMobileViewport'

const { isMobile } = useMobileViewport()
const mobileStep = ref(0)

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  interfaces: { type: Array, default: () => [] },
  targetNodes: { type: Array, default: () => [] },
  submitting: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'submit'])
const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value)
})
const form = reactive({
  node_name: '',
  description: '',
  category: 'subflow',
  mode: 'create',
  target_encapsulated_node_id: ''
})
watch(visible, opened => {
  if (opened && isMobile.value) {
    mobileStep.value = 0
    Object.assign(form, { node_name: '', description: '', category: 'subflow', mode: 'create', target_encapsulated_node_id: '' })
  }
})
const canSubmit = computed(() => (
  form.node_name.trim()
  && (form.mode === 'create' || form.target_encapsulated_node_id.trim())
))
const submit = () => emit('submit', {
  ...form,
  node_name: form.node_name.trim(),
  target_encapsulated_node_id: form.mode === 'add_version'
    ? form.target_encapsulated_node_id.trim()
    : null
})
</script>

<style scoped>
.mobile-encapsulate-form :deep(.el-radio-group) { display: grid; gap: 10px; }.mobile-encapsulate-form :deep(.el-radio) { margin: 0; min-height: 44px; white-space: normal; }.mobile-encapsulate-form :deep(.el-radio__label) { white-space: normal; line-height: 1.5; }.mobile-encapsulate-form :deep(.el-input__wrapper), .mobile-encapsulate-form :deep(.el-select__wrapper) { min-height: 44px; }.mobile-encapsulate-review { font-size: 14px; overflow-wrap: anywhere; }.mobile-encapsulate-review p { color: #64748b; white-space: pre-wrap; margin: 8px 0; }.mobile-interface-list article { padding: 14px; border: 1px solid #e2e8f0; border-radius: 12px; margin-bottom: 10px; overflow-wrap: anywhere; }.mobile-interface-list p { color: #64748b; font-size: 12px; margin-top: 6px; }
</style>
