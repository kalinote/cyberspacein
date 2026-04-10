<template>
  <div class="w-full">
    <AnyValueTreeNode v-model="innerValue" :depth="0" />
  </div>
</template>

<script setup>
/**
 * AnyValueTreeEditor
 *
 * 简介：
 * - 通用的“任意类型值”可视化编辑器，用于编辑 JSON-like 数据，尽量避免用户直接输入 JSON 代码。
 * - 支持：string / number / boolean / null / array / object，允许任意深度嵌套与混合类型数组。
 *
 * 用法：
 * - 基础：
 *   <AnyValueTreeEditor v-model="value" />
 * - 表单提交前校验（可选）：
 *   const errors = editorRef.value?.validate?.() || []
 *   if (errors.length) { 这里自行提示 errors[0] }
 *
 * 说明：
 * - validate 主要用于检查对象键是否为空/重复；不做业务层面的 schema 校验。
 */
import { computed } from 'vue'
import AnyValueTreeNode from './AnyValueTreeNode.vue'

const props = defineProps({
  modelValue: {
    type: [String, Number, Boolean, Array, Object, null],
    default: null
  }
})

const emit = defineEmits(['update:modelValue'])

const innerValue = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

function collectErrors(value, path = 'root') {
  const errors = []
  if (value === null) return errors

  if (Array.isArray(value)) {
    value.forEach((item, idx) => {
      errors.push(...collectErrors(item, `${path}[${idx}]`))
    })
    return errors
  }

  if (typeof value === 'object') {
    const keys = Object.keys(value)
    const seen = new Set()
    for (const k of keys) {
      if (!k || !String(k).trim()) {
        errors.push(`对象键不能为空（位置：${path}）`)
        continue
      }
      const kk = String(k).trim()
      if (seen.has(kk)) {
        errors.push(`对象键重复：${kk}（位置：${path}）`)
      } else {
        seen.add(kk)
      }
    }
    for (const k of keys) {
      errors.push(...collectErrors(value[k], `${path}.${k}`))
    }
  }

  return errors
}

function validate() {
  return collectErrors(props.modelValue)
}

defineExpose({ validate })
</script>

