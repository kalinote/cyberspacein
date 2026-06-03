<template>
    <div class="flex flex-col flex-1 min-h-0 min-w-0 overflow-hidden">
        <div
            v-if="!sessionId"
            class="flex-1 flex flex-col items-center justify-center p-6 text-center text-gray-500"
        >
            <Icon icon="mdi:brain" class="text-4xl text-blue-400 mb-3" />
            <p class="text-sm font-medium text-gray-600">暂无分析会话</p>
            <p class="text-xs mt-2 text-gray-400">请先在信息栏通过「分析此实体」启动分析任务</p>
        </div>
        <template v-else>
            <AgentRealtimeEventsPanel
                class="flex-1 min-h-0"
                :timeline-items="timelineItems"
                :register-events-scroll-el="registerEventsScrollEl"
                :on-events-scroll="onEventsScroll"
                empty-text="等待事件推送"
            >
                <template #header-extra>
                    <el-link type="primary" class="text-xs shrink-0" @click="emit('open-fullscreen')">
                        <template #icon>
                            <Icon icon="mdi:open-in-new" />
                        </template>
                        全屏查看
                    </el-link>
                </template>
            </AgentRealtimeEventsPanel>
            <AgentTodosPanel
                :todos="todos"
                :todo-status-icon="todoStatusIcon"
                :todo-status-icon-color="todoStatusIconColor"
            />
            <div class="shrink-0 flex justify-end px-3 pt-2 bg-white border-t border-gray-100">
                <AgentAutoApproveSwitch />
            </div>
            <AgentContinueChatBar
                :user-prompt="userPrompt"
                :send-loading="sendLoading"
                :cancel-loading="cancelLoading"
                :can-send-message="canSendMessage"
                :can-cancel="canCancel"
                :has-session="true"
                :sse-connected="sseConnected"
                :status-label="statusLabel"
                :status-tag-type="statusTagType"
                @update:user-prompt="emit('update:userPrompt', $event)"
                @keydown.ctrl.enter.prevent="emit('send')"
                @send="emit('send')"
                @cancel="emit('cancel')"
            />
        </template>
    </div>
</template>

<script setup>
import { Icon } from '@iconify/vue'
import AgentRealtimeEventsPanel from '@/components/agent/AgentRealtimeEventsPanel.vue'
import AgentContinueChatBar from '@/components/agent/AgentContinueChatBar.vue'
import AgentTodosPanel from '@/components/agent/AgentTodosPanel.vue'
import AgentAutoApproveSwitch from '@/components/agent/AgentAutoApproveSwitch.vue'

defineProps({
    sessionId: {
        type: String,
        default: '',
    },
    timelineItems: {
        type: Array,
        default: () => [],
    },
    registerEventsScrollEl: {
        type: Function,
        default: undefined,
    },
    onEventsScroll: {
        type: Function,
        default: undefined,
    },
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
    todos: {
        type: Array,
        default: () => [],
    },
    todoStatusIcon: {
        type: Function,
        default: () => 'mdi:circle-outline',
    },
    todoStatusIconColor: {
        type: Function,
        default: () => 'text-gray-400',
    },
})

const emit = defineEmits(['open-fullscreen', 'update:userPrompt', 'send', 'cancel'])
</script>
