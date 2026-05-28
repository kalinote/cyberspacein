<template>
  <div class="wiki-page-meta rounded-xl border border-gray-200 bg-gray-50/60 px-4 py-3 mb-6 text-sm">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <p v-if="sourceNote" class="text-gray-600 min-w-0 m-0">
        {{ sourceNote }}
      </p>
      <div v-else class="min-w-0" />
      <div class="flex items-center gap-2 shrink-0 ml-auto">
        <span class="text-gray-600 font-medium">编辑模式</span>
        <el-switch
          :model-value="editMode"
          active-text="开"
          inactive-text="关"
          @update:model-value="emit('update:editMode', $event)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  sourceNote: {
    type: String,
    default: '',
  },
  editMode: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:editMode'])
</script>
