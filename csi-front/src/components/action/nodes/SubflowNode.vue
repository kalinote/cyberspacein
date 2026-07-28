<template>
  <div class="relative rounded-xl ring-2 ring-teal-200">
    <span class="absolute -top-2 right-2 z-10 rounded bg-teal-700 px-2 py-0.5 text-[10px] text-white">
      封装节点
    </span>
    <GenericNode v-bind="props" />
  </div>
</template>

<script setup>
import GenericNode from './GenericNode.vue'

const props = defineProps({
  id: { type: String, required: true },
  data: { type: Object, default: () => ({}) },
  showHandle: { type: Boolean, default: true },
  disabled: { type: Boolean, default: false }
})
</script>
