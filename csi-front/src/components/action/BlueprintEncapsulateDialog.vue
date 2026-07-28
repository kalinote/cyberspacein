<template>
  <el-dialog v-model="visible" title="封装为节点" width="680px" destroy-on-close>
    <el-form label-position="top">
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
      <el-divider content-position="left">公开 Handles 预览</el-divider>
      <el-empty v-if="interfaces.length === 0" description="当前蓝图没有公开接口" :image-size="48" />
      <el-table v-else :data="interfaces" size="small">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="direction" label="方向" width="100" />
        <el-table-column prop="interfaceTypeId" label="接口类型" />
      </el-table>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">
        校验并封装
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive } from 'vue'

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
