<template>
  <el-dialog v-model="visible" title="发布蓝图版本" width="560px">
    <el-alert
      title="发布后会生成不可变 Revision；后续修改蓝图不会改变已发布版本。"
      type="info"
      :closable="false"
    />
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="$emit('submit')">确认发布</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  submitting: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'submit'])
const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value)
})
</script>
