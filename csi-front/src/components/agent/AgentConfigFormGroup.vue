<template><details v-if="isMobile" class="agent-config-form-group" :open="initialOpen"><summary>{{ title }}<span>{{ hint }}</span></summary><div><slot /></div></details><slot v-else /></template>
<script setup>
import { useMobileViewport } from '@/composables/useMobileViewport'
defineProps({ title: { type: String, required: true }, hint: { type: String, default: '' }, initialOpen: Boolean })
const { isMobile } = useMobileViewport()
</script>
<style scoped>
.agent-config-form-group{border:1px solid #e2e8f0;border-radius:14px;margin-bottom:14px;background:#fff;min-width:0}.agent-config-form-group>summary{padding:16px;font-size:16px;font-weight:650;color:#0f172a;cursor:pointer;min-height:56px}.agent-config-form-group>summary>span{display:block;font-size:12px;font-weight:400;color:#64748b;margin-top:5px}.agent-config-form-group>div{padding:4px 14px 0}
</style>
