<template>
    <div v-if="approval" class="min-w-0">
        <ModifyEntityApprovalBody
            v-if="approval.source === APPROVAL_SOURCE_MODIFY_ENTITY"
            :payload="approval.payload"
        />
        <WikiCreateApprovalBody
            v-else-if="approval.source === APPROVAL_SOURCE_WIKI_CREATE"
            :payload="approval.payload"
        />
        <WikiEditApprovalBody
            v-else-if="approval.source === APPROVAL_SOURCE_WIKI_EDIT"
            :payload="approval.payload"
        />
        <div v-else class="rounded-lg border border-amber-100 bg-amber-50/40 p-4">
            <p class="text-sm text-amber-900 mb-2">
                暂未为此来源定制展示：<span class="font-mono">{{ approval.source || '—' }}</span>
            </p>
            <el-collapse class="border-0">
                <el-collapse-item title="payload（JSON）" name="payload">
                    <pre class="rounded bg-white p-2 text-xs text-gray-800 ring-1 ring-gray-100 whitespace-pre-wrap">{{ payloadJson }}</pre>
                </el-collapse-item>
            </el-collapse>
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue'
import ModifyEntityApprovalBody from './ModifyEntityApprovalBody.vue'
import WikiCreateApprovalBody from './WikiCreateApprovalBody.vue'
import WikiEditApprovalBody from './WikiEditApprovalBody.vue'
import {
    APPROVAL_SOURCE_MODIFY_ENTITY,
    APPROVAL_SOURCE_WIKI_CREATE,
    APPROVAL_SOURCE_WIKI_EDIT,
} from '@/utils/agentApproval'
import { stringifyJsonSafe } from '@/utils/agentSse'

const props = defineProps({
    approval: {
        type: Object,
        default: null,
    },
})

const payloadJson = computed(() => stringifyJsonSafe(props.approval?.payload ?? {}, 2))
</script>
