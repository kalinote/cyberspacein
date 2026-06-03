<template>
    <div class="flex items-center gap-2 shrink-0">
        <el-switch v-model="autoApprove" size="small" />
        <span class="text-sm text-gray-600 whitespace-nowrap">自动执行</span>
        <el-tooltip
            content="开启后工具调用无需人工审批；关闭时需逐项批准"
            placement="top"
        >
            <Icon icon="mdi:help-circle-outline" class="text-gray-400 text-base cursor-help" />
        </el-tooltip>
    </div>
</template>

<script setup>
import { Icon } from '@iconify/vue'
import { useAgentAutoApprove } from '@/composables/useAgentAutoApprove'

const { autoApprove } = useAgentAutoApprove()
</script>
