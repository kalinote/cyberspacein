<template>
  <dl class="resource-fields">
    <template v-for="field in fields" :key="field.label"><dt>{{ field.label }}</dt><dd><pre v-if="field.value && typeof field.value === 'object'">{{ JSON.stringify(field.value, null, 2) }}</pre><span v-else>{{ field.value === false ? '否' : field.value === true ? '是' : field.value ?? '—' }}</span></dd></template>
  </dl>
</template>

<script setup>
defineProps({ fields: { type: Array, default: () => [] } })
</script>

<style scoped>
.resource-fields { margin: 0; display: grid; gap: 6px; }
.resource-fields dt { color: #64748b; font-size: 12px; margin-top: 8px; }
.resource-fields dd { margin: 0; color: #1e293b; font-size: 14px; line-height: 1.65; overflow-wrap: anywhere; }
.resource-fields pre { max-height: 240px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; background: #f1f5f9; padding: 10px; border-radius: 8px; font-size: 12px; }
</style>
