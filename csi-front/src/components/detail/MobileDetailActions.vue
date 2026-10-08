<template>
    <MobileActionBar aria-label="材料研判操作">
        <div class="mobile-detail-actions">
            <button type="button" :class="{ selected: isPriorityTarget }" :aria-pressed="isPriorityTarget" :disabled="!canHighlight || highlightLoading" @click="canHighlight && emit('toggle-priority')">
                <Icon :icon="isPriorityTarget ? 'mdi:star' : 'mdi:star-outline'" />
                <span>{{ isPriorityTarget ? '取消重点' : '重点标记' }}</span>
            </button>
            <AddToEvidenceButton :entity="entity" />
            <AgentStartButton
                button-text="发起分析"
                loading-text="启动中"
                :disabled="analyzing || !canAnalyze"
                :loading="analyzing"
                :agent-options="agentOptions"
                :default-injection-param="defaultInjectionParam"
                icon="mdi:brain"
                block
                @click.capture="!canAnalyze && $event.stopPropagation()"
                @started="emit('started', $event)"
            />
        </div>
    </MobileActionBar>
</template>

<script setup>
import { Icon } from '@iconify/vue'
import { computed } from 'vue'
import MobileActionBar from '@/components/mobile/MobileActionBar.vue'
import AddToEvidenceButton from '@/components/evidence/AddToEvidenceButton.vue'
import AgentStartButton from '@/components/agent/AgentStartButton.vue'
import { hasPerm } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'

defineProps({
    entity: { type: Object, required: true },
    isPriorityTarget: { type: Boolean, default: false },
    analyzing: { type: Boolean, default: false },
    highlightLoading: { type: Boolean, default: false },
    agentOptions: { type: Array, default: () => [] },
    defaultInjectionParam: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['toggle-priority', 'started'])
const canHighlight = computed(() => hasPerm(PERM.operations.target.highlight.update))
const canAnalyze = computed(() => hasPerm(PERM.operations.agent.agent.execute) && hasPerm(PERM.operations.agent.agent.read))
</script>

<style scoped>
.mobile-detail-actions { display: flex; align-items: center; width: 100%; gap: 8px; }
.mobile-detail-actions > * { flex: 1; min-width: 0; }
.mobile-detail-actions > button { display: flex; align-items: center; justify-content: center; gap: 4px; min-height: 44px; color: #475569; font-size: 13px; white-space: nowrap; }
.mobile-detail-actions > button.selected { color: #b45309; }
.mobile-detail-actions > button:disabled { color: #94a3b8; cursor: not-allowed; }
.mobile-detail-actions :deep(.el-button) { margin-left: 0; font-size: 13px; }
.mobile-detail-actions :deep(button) { min-height: 44px; }
.mobile-detail-actions :deep(.w-full > button) { gap: 4px; padding: 10px 7px; font-size: 13px; white-space: nowrap; }
</style>
