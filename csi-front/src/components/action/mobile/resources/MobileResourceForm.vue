<template>
  <div class="mobile-resource-form">
    <nav class="resource-form-steps" aria-label="配置分组"><button v-for="(label, index) in steps" :key="label" type="button" :disabled="disabled" :class="{ active: step === index }" :aria-current="step === index ? 'step' : undefined" @click="step = index">{{ index + 1 }}. {{ label }}</button></nav>
    <p class="resource-form-hint">{{ steps[step] }} · 第 {{ step + 1 }} 组，共 {{ steps.length }} 组</p>
    <el-form label-position="top" :disabled="disabled" @submit.prevent="$emit('save')">
      <template v-if="kind === 'accounts'">
        <template v-if="step === 0"><el-form-item label="平台" required><el-select v-model="draft.platform_id" filterable><el-option v-for="platform in options.platforms" :key="platform.id" :label="platform.name" :value="platform.id" /></el-select></el-form-item><el-form-item label="账号别名" required><el-input v-model="draft.account_name" placeholder="内部展示名称" /></el-form-item></template>
        <template v-if="step === 1"><p class="resource-form-hint">按平台需要填写登录信息，未填写的字段不提交。</p><el-form-item label="用户名"><el-input v-model="draft.credentials.username" autocomplete="off" /></el-form-item><el-form-item label="密码"><el-input v-model="draft.credentials.password" type="password" show-password autocomplete="new-password" /></el-form-item><el-form-item label="手机号"><el-input v-model="draft.credentials.phone" inputmode="tel" /></el-form-item><el-form-item label="邮箱"><el-input v-model="draft.credentials.email" inputmode="email" /></el-form-item></template>
        <template v-if="step === 2"><el-form-item label="频率策略"><el-select v-model="draft.rate_limit.strategy"><el-option label="不限制" value="none" /><el-option label="每分钟" value="minutely" /><el-option label="每小时" value="hourly" /><el-option label="每天" value="daily" /></el-select></el-form-item><el-form-item v-if="draft.rate_limit.strategy !== 'none'" label="最大请求数"><el-input-number v-model="draft.rate_limit.max_requests" :min="0" :precision="0" /></el-form-item></template>
      </template>
      <template v-else-if="kind === 'nodeHandles'">
        <template v-if="step === 0"><el-form-item label="接口名称" required><el-input v-model="draft.handle_name" placeholder="英文字母开头，例如 content" /></el-form-item><el-form-item label="接口类型" required><el-select v-model="draft.type"><el-option label="值类型" value="value" /><el-option label="引用类型" value="reference" /></el-select></el-form-item><el-form-item label="显示标签" required><el-input v-model="draft.label" /></el-form-item><el-form-item label="颜色"><el-color-picker v-model="draft.color" format="hex" :predefine="['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399']" /></el-form-item></template>
        <template v-if="step === 1"><el-form-item label="其他兼容接口"><el-select v-model="draft.other_compatible_interfaces" multiple filterable><el-option v-for="handle in options.handles" :key="handle.id" :label="handle.label" :value="handle.id" /></el-select></el-form-item><el-form-item label="自定义样式"><MobileResourceKeyValues :disabled="disabled" v-model="draft.custom_style" /></el-form-item></template>
      </template>
      <template v-else>
        <template v-if="step === 0"><el-form-item label="节点名称" required><el-input v-model="draft.name" /></el-form-item><el-form-item label="节点描述"><el-input v-model="draft.description" type="textarea" :rows="3" /></el-form-item><el-form-item label="节点类型" required><el-select v-model="draft.type"><el-option v-for="type in options.types" :key="type.value" :label="type.label" :value="type.value" /></el-select></el-form-item><el-form-item label="版本号" required><el-input v-model="draft.version" /></el-form-item></template>
        <template v-if="step === 1">
          <el-form-item label="关联组件" required><el-select v-model="draft.related_components" multiple filterable><el-option v-for="component in options.components" :key="component.id" :label="component.name" :value="component.id" /></el-select></el-form-item>
          <div v-if="draft.related_components.length" class="resource-timeouts"><p>组件超时（秒）</p><label v-for="id in draft.related_components" :key="id"><span>{{ options.components.find(item => item.id === id)?.name || id }}</span><el-input-number v-model="draft.component_timeouts[id]" :min="0" :precision="0" controls-position="right" /></label><small>0 表示不限制该组件的运行时间。</small></div>
          <el-form-item label="运行命令" required><el-input v-model="draft.command" /></el-form-item><el-form-item label="运行参数"><TagInput :disabled="disabled" v-model="draft.command_args" placeholder="例如 main:run" /></el-form-item><el-form-item label="默认配置"><MobileResourceKeyValues :disabled="disabled" v-model="draft.default_configs" /></el-form-item>
        </template>
        <template v-if="step === 2">
          <div class="resource-form-list-heading"><span>{{ draft.handles.length }} 个接口</span><el-button plain @click="draft.handles.push({ id: '', type: '', relabel: '', position: '', custom_style: {} }); selectedHandle = draft.handles.length - 1">添加接口</el-button></div>
          <p v-if="!draft.handles.length" class="resource-form-hint">尚未配置接口，可按需要添加。</p>
          <article v-for="(handle, index) in draft.handles" :key="index" class="resource-form-item">
            <button type="button" class="resource-form-item-heading" :aria-expanded="selectedHandle === index" @click="selectedHandle = selectedHandle === index ? -1 : index"><span>{{ handle.relabel || options.handles.find(item => item.id === handle.id)?.label || `接口 ${index + 1}` }}</span><Icon :icon="selectedHandle === index ? 'mdi:chevron-up' : 'mdi:chevron-down'" /></button>
            <div v-if="selectedHandle === index" class="resource-form-item-body"><el-form-item label="接口" required><el-select v-model="handle.id" filterable><el-option v-for="option in options.handles" :key="option.id" :label="option.label" :value="option.id" /></el-select></el-form-item><el-form-item label="方向" required><el-select v-model="handle.type"><el-option label="输出接口" value="source" /><el-option label="输入接口" value="target" /></el-select></el-form-item><el-form-item label="重新命名"><el-input v-model="handle.relabel" /></el-form-item><el-form-item label="位置" required><el-select v-model="handle.position"><el-option v-for="position in ['left', 'right', 'top', 'bottom']" :key="position" :value="position" :label="position" /></el-select></el-form-item><el-form-item label="自定义样式"><MobileResourceKeyValues :disabled="disabled" v-model="handle.custom_style" /></el-form-item><el-button type="danger" plain @click="draft.handles.splice(index, 1); selectedHandle = -1">移除此接口</el-button></div>
          </article>
        </template>
        <template v-if="step === 3">
          <div class="resource-form-list-heading"><span>{{ draft.inputs.length }} 个输入项</span><el-button plain @click="draft.inputs.push({ name: '', type: '', position: 'center', label: '', description: '', required: false, default: '', options: [], custom_style: {}, custom_props: {} }); selectedInput = draft.inputs.length - 1">添加输入项</el-button></div>
          <p v-if="!draft.inputs.length" class="resource-form-hint">尚未配置输入项，可按需要添加。</p>
          <article v-for="(input, index) in draft.inputs" :key="index" class="resource-form-item">
            <button type="button" class="resource-form-item-heading" :aria-expanded="selectedInput === index" @click="selectedInput = selectedInput === index ? -1 : index"><span>{{ input.label || input.name || `输入项 ${index + 1}` }}</span><Icon :icon="selectedInput === index ? 'mdi:chevron-up' : 'mdi:chevron-down'" /></button>
            <div v-if="selectedInput === index" class="resource-form-item-body"><el-form-item label="字段名" required><el-input v-model="input.name" placeholder="英文字母开头，仅字母、数字、下划线" /></el-form-item><el-form-item label="输入类型" required><el-select v-model="input.type"><el-option v-for="type in INPUT_TYPES" :key="type" :label="type" :value="type" /></el-select></el-form-item><el-form-item label="显示标签" required><el-input v-model="input.label" /></el-form-item><el-form-item :label="input.type === 'comment' ? '说明文本' : '输入描述'"><el-input v-model="input.description" type="textarea" :rows="3" /></el-form-item><el-form-item label="对齐位置" required><el-select v-model="input.position"><el-option v-for="position in ['left', 'right', 'top', 'bottom', 'center']" :key="position" :label="position" :value="position" /></el-select></el-form-item><template v-if="input.type !== 'comment'"><el-form-item label="必填"><el-switch v-model="input.required" /></el-form-item><el-form-item label="默认值"><el-input v-model="input.default" /></el-form-item></template><el-form-item v-if="input.type === 'select'" label="选项"><TagInput :disabled="disabled" v-model="input.options" /></el-form-item><el-form-item label="自定义样式"><MobileResourceKeyValues :disabled="disabled" v-model="input.custom_style" /></el-form-item><el-form-item label="自定义属性"><MobileResourceKeyValues :disabled="disabled" v-model="input.custom_props" /></el-form-item><el-button type="danger" plain @click="draft.inputs.splice(index, 1); selectedInput = -1">移除此输入项</el-button></div>
          </article>
        </template>
      </template>
    </el-form>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { INPUT_TYPES } from '@/utils/action'
import TagInput from '@/components/action/nodes/components/TagInput.vue'
import MobileResourceKeyValues from './MobileResourceKeyValues.vue'
const props = defineProps({ kind: { type: String, required: true }, options: { type: Object, required: true }, invalidIndex: { type: Number, default: -1 }, disabled: { type: Boolean, default: false } })
defineEmits(['save'])
const draft = defineModel({ type: Object, required: true })
const step = defineModel('step', { type: Number, default: 0 })
const selectedHandle = ref(-1), selectedInput = ref(-1)
const steps = computed(() => props.kind === 'accounts' ? ['基本资料', '登录信息', '频率限制'] : props.kind === 'nodeHandles' ? ['基本资料', '兼容与样式'] : ['基本资料', '执行配置', '接口', '输入项'])
watch([() => props.invalidIndex, step], ([index]) => { if (step.value === 2) selectedHandle.value = index; if (step.value === 3) selectedInput.value = index })
watch(() => draft.value.related_components, ids => {
  if (props.kind !== 'nodes') return
  for (const id of ids || []) if (draft.value.component_timeouts[id] === undefined) draft.value.component_timeouts[id] = 0
  for (const id of Object.keys(draft.value.component_timeouts)) if (!ids?.includes(id)) delete draft.value.component_timeouts[id]
}, { deep: true })
</script>

<style scoped>
.resource-form-steps { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-bottom: 16px; }
.resource-form-steps button { min-height: 44px; border-radius: 9px; color: #64748b; background: #f1f5f9; font-size: 13px; }
.resource-form-steps button.active { color: #2563eb; background: #eff6ff; font-weight: 650; box-shadow: inset 0 0 0 1px #bfdbfe; }
.resource-form-hint { margin: 0 0 18px; color: #64748b; font-size: 12px; line-height: 1.75; }
.resource-form-list-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; color: #64748b; font-size: 13px; margin-bottom: 12px; }
.resource-form-item { margin-bottom: 12px; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; }
.resource-form-item-heading { display: flex; align-items: center; justify-content: space-between; gap: 10px; text-align: left; min-height: 52px; width: 100%; padding: 12px; color: #1e293b; font-size: 14px; background: #f8fafc; }
.resource-form-item-heading span { overflow-wrap: anywhere; }
.resource-form-item-body { padding: 14px 12px; }
.resource-timeouts { padding: 12px; margin-bottom: 20px; background: #f8fafc; border-radius: 10px; }
.resource-timeouts p { font-size: 13px; font-weight: 600; margin-bottom: 12px; }
.resource-timeouts label { display: grid; gap: 6px; margin: 12px 0; font-size: 12px; overflow-wrap: anywhere; }
.resource-timeouts small { color: #64748b; font-size: 11px; }
.mobile-resource-form :deep(.el-select), .mobile-resource-form :deep(.el-input-number) { width: 100%; }
.mobile-resource-form :deep(.el-button) { min-height: 44px; }
.mobile-resource-form :deep(.el-tag) { height: auto; min-height: 28px; white-space: normal; overflow-wrap: anywhere; }
.mobile-resource-form :deep(.el-tag__content) { overflow-wrap: anywhere; }
</style>
