<template>
    <div class="space-y-4">
        <div class="rounded-lg border border-gray-200 bg-gray-50/80 p-4">
            <p class="text-xs text-gray-500 mb-1">{{ actionLabel }}</p>
            <router-link v-if="payload?.chain_id" :to="`/evidence/chains/${encodeURIComponent(payload.chain_id)}`" target="_blank" class="font-medium text-blue-600 hover:underline">
                {{ payload.title }}
            </router-link>
            <p v-else class="font-medium text-gray-900">{{ payload?.title }}</p>
            <p v-if="payload?.expected_revision" class="mt-1 text-xs text-gray-500">基于修订 {{ payload.expected_revision }}</p>
        </div>
        <div class="rounded-lg border border-blue-100 bg-blue-50/60 p-4">
            <p class="text-xs font-medium text-blue-800 mb-1">操作说明</p>
            <p class="text-sm text-gray-800 whitespace-pre-wrap wrap-break-word">{{ payload?.reason }}</p>
        </div>
        <el-alert v-if="payload?.diff?.deleted" type="warning" :closable="false" show-icon>
            将删除此证据链（{{ payload.diff.node_count }} 个节点、{{ payload.diff.edge_count }} 条关系）。原始实体和被引用的子链保留。
        </el-alert>
        <div v-if="payload?.affected_references?.total" class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <p>有 {{ payload.affected_references.total }} 条父链引用此链，变更会实时影响引用结果。</p>
            <div class="mt-1 flex flex-wrap gap-2">
                <router-link v-for="chain in payload.affected_references.items" :key="chain.chain_id" :to="`/evidence/chains/${encodeURIComponent(chain.chain_id)}`" target="_blank" class="underline">{{ chain.title }}</router-link>
            </div>
        </div>
        <div v-if="payload?.warnings?.length" class="max-h-40 overflow-auto rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
            <p v-for="(warning, index) in payload.warnings" :key="index">{{ warning.message }}</p>
        </div>
        <div v-for="section in sections" :key="section.title" class="rounded-lg border border-gray-200 bg-white p-4">
            <p class="text-sm font-medium text-gray-900 mb-3">{{ section.title }}</p>
            <div class="max-h-80 overflow-auto space-y-3">
                <div v-for="(row, index) in section.rows" :key="index" class="rounded border border-gray-100 p-3">
                    <p class="text-xs font-medium text-gray-700 mb-2 wrap-break-word">{{ row.label }}</p>
                    <div class="grid gap-2 sm:grid-cols-2 text-xs">
                        <div v-if="row.before !== undefined" class="rounded bg-red-50 p-2">
                            <p class="text-red-700 mb-1">变更前</p>
                            <p class="text-gray-700 whitespace-pre-wrap wrap-break-word">{{ row.before }}</p>
                        </div>
                        <div v-if="row.after !== undefined" class="rounded bg-green-50 p-2">
                            <p class="text-green-700 mb-1">变更后</p>
                            <p class="text-gray-700 whitespace-pre-wrap wrap-break-word">{{ row.after }}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <p class="text-xs text-gray-500">校验仅涵盖图结构、引用和摘录匹配，分析判断仍需核实。</p>
    </div>
</template>

<script setup>
import { computed } from 'vue'
import { buildEvidenceApprovalSections } from '@/utils/evidenceApproval'

const props = defineProps({ payload: { type: Object, default: null } })
const sections = computed(() => buildEvidenceApprovalSections(props.payload?.diff))
const actionLabel = computed(() => ({ create: '创建证据链', update: '保存证据链', delete: '删除证据链' })[props.payload?.action] || '证据链操作')
</script>
