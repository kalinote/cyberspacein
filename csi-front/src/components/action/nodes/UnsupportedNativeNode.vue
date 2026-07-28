<template>
  <div class="min-w-64 rounded-lg border border-red-300 bg-red-50 p-4 text-red-800 shadow-sm">
    <p class="text-sm font-semibold">{{ data?.config?.name || '后端原生节点' }}</p>
    <p class="mt-2 text-xs">
      不支持此节点渲染器：
      {{ rendererKey }}@{{ contractVersion }}
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  id: { type: String, required: true },
  data: { type: Object, default: () => ({}) },
  showHandle: { type: Boolean, default: true },
  disabled: { type: Boolean, default: false }
})

const rendererKey = computed(() => (
  props.data?.config?.extension?.renderer_key || 'unknown'
))
const contractVersion = computed(() => (
  props.data?.config?.extension?.contract_version || 'unknown'
))
</script>
