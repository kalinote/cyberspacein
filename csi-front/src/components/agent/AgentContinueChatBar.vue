<template>
    <div class="shrink-0 border-t border-gray-100 p-3 space-y-2 bg-white">
        <div v-if="showStatus" class="flex flex-wrap items-center gap-1.5 text-xs">
            <el-tag v-if="sseConnected" type="success" size="small">已连接</el-tag>
            <el-tag v-else-if="hasSession" type="warning" size="small">未连接</el-tag>
            <el-tag v-if="statusLabel" :type="statusTagType" size="small">{{ statusLabel }}</el-tag>
        </div>
        <el-input
            :model-value="userPrompt"
            type="textarea"
            :autosize="{ minRows: compact ? 2 : 3, maxRows: compact ? 4 : 8 }"
            :placeholder="placeholder"
            :disabled="!hasSession"
            resize="none"
            @update:model-value="emit('update:userPrompt', $event)"
            @keydown.ctrl.enter.prevent="emit('send')"
        />
        <div class="flex gap-2">
            <el-button
                type="primary"
                size="small"
                class="flex-1"
                :loading="sendLoading"
                :disabled="!canSendMessage"
                @click="emit('send')"
            >
                发送
            </el-button>
            <el-button
                type="warning"
                size="small"
                :loading="cancelLoading"
                :disabled="!canCancel"
                @click="emit('cancel')"
            >
                取消
            </el-button>
        </div>
    </div>
</template>

<script setup>
defineProps({
    userPrompt: {
        type: String,
        default: '',
    },
    sendLoading: {
        type: Boolean,
        default: false,
    },
    cancelLoading: {
        type: Boolean,
        default: false,
    },
    canSendMessage: {
        type: Boolean,
        default: false,
    },
    canCancel: {
        type: Boolean,
        default: false,
    },
    hasSession: {
        type: Boolean,
        default: false,
    },
    sseConnected: {
        type: Boolean,
        default: false,
    },
    statusLabel: {
        type: String,
        default: '',
    },
    statusTagType: {
        type: String,
        default: 'info',
    },
    showStatus: {
        type: Boolean,
        default: true,
    },
    compact: {
        type: Boolean,
        default: true,
    },
    placeholder: {
        type: String,
        default: '描述你的分析需求，通过 / 使用命令，通过 @ 引用实体',
    },
})

const emit = defineEmits(['update:userPrompt', 'send', 'cancel'])
</script>
