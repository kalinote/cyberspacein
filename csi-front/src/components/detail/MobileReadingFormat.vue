<template>
    <label class="mobile-reading-format">
        <Icon icon="mdi:book-open-page-variant-outline" />
        <span>阅读内容</span>
        <select :value="modelValue" aria-label="阅读内容格式" @change="emit('update:modelValue', $event.target.value)">
            <option v-if="entity.clean_content" value="clean">正文</option>
            <option v-if="!entity.clean_content" value="empty">内容</option>
            <option v-if="entity.safe_raw_content" value="rendered">原文排版</option>
            <option v-if="entity.translate_content" value="translate">翻译</option>
            <option v-if="entity.raw_content" value="raw">原始源代码</option>
            <option v-if="entity.safe_raw_content" value="safe-raw">安全内容代码</option>
            <option v-if="entity.snapshot" value="snapshot">页面快照</option>
        </select>
    </label>
</template>

<script setup>
import { Icon } from '@iconify/vue'
defineProps({
    entity: { type: Object, required: true },
    modelValue: { type: String, default: 'clean' },
})
const emit = defineEmits(['update:modelValue'])
</script>

<style scoped>
.mobile-reading-format { display: flex; align-items: center; gap: 8px; width: 100%; padding-bottom: 12px; margin-bottom: 16px; border-bottom: 1px solid #f1f5f9; color: #64748b; font-size: 13px; }
.mobile-reading-format select { min-width: 0; min-height: 44px; flex: 1; margin-left: auto; padding: 8px; border-radius: 8px; background: #f8fafc; color: #0f172a; font-size: 16px; }
</style>
