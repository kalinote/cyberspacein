<template>
    <header class="mobile-detail-header">
        <div class="mobile-detail-meta">
            <span>{{ entity.author_name || entity.spider_name || '来源未知' }}</span>
            <span v-if="entity.publish_at">{{ formatDateTime(entity.publish_at) }}</span>
        </div>
        <h1>{{ entity.title || '无标题' }}</h1>
        <div class="mobile-detail-tags">
            <el-tag v-if="entity.nsfw" type="danger" size="small">NSFW</el-tag>
            <el-tag v-if="entity.aigc" type="warning" size="small">AIGC</el-tag>
            <el-tag v-if="entity.floor" size="small">{{ entity.floor }}楼</el-tag>
            <button type="button" @click="sourceVisible = true">
                <Icon icon="mdi:information-outline" /> 来源与资料
                <Icon icon="mdi:chevron-right" />
            </button>
        </div>
        <MobileSheet v-model="sourceVisible" title="来源与资料">
            <div class="mobile-source-links">
                <a v-if="entity.url" :href="entity.url" target="_blank" rel="noopener noreferrer">
                    <Icon icon="mdi:open-in-new" /> 查看原文
                </a>
                <router-link v-if="entity.topic_thread_uuid && entity.thread_type !== 'thread'" :to="`/details/forum/${entity.topic_thread_uuid}`">
                    <Icon icon="mdi:forum-outline" /> 查看主贴
                </router-link>
            </div>
            <dl class="mobile-source-list">
                <div v-for="item in infoItems" :key="item.key">
                    <dt>{{ item.label }}</dt>
                    <dd>
                        <router-link v-if="item.to" :to="item.to">{{ item.value }}</router-link>
                        <span v-else>{{ item.value }}</span>
                    </dd>
                </div>
                <div><dt>唯一标识</dt><dd>{{ entity.uuid }}</dd></div>
            </dl>
            <div class="mobile-source-tags">
                <el-tag v-if="entity.spider_name" size="small">{{ entity.spider_name }}</el-tag>
                <el-tag v-if="entity.section" size="small">{{ entity.section }}</el-tag>
                <el-tag v-if="entity.category_tag" size="small">{{ entity.category_tag }}</el-tag>
                <el-tag v-if="entity.entity_type" size="small">{{ entity.entity_type }}</el-tag>
                <el-tag v-for="label in statusLabels" :key="label" size="small">{{ label }}</el-tag>
                <el-tag v-for="tag in entity.tags" :key="tag" type="info" size="small">{{ tag }}</el-tag>
            </div>
        </MobileSheet>
    </header>
</template>

<script setup>
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { formatDateTime } from '@/utils/action'

defineProps({
    entity: { type: Object, required: true },
    infoItems: { type: Array, default: () => [] },
    statusLabels: { type: Array, default: () => [] },
})
const sourceVisible = ref(false)
</script>

<style scoped>
.mobile-detail-header { padding: 20px 20px 12px; background: #fff; }
.mobile-detail-meta { display: flex; flex-wrap: wrap; gap: 6px 12px; color: #64748b; font-size: 12px; }
.mobile-detail-header h1 { margin: 12px 0; color: #0f172a; font-size: 25px; font-weight: 700; line-height: 1.45; overflow-wrap: anywhere; }
.mobile-detail-tags, .mobile-source-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.mobile-detail-tags button { display: inline-flex; align-items: center; gap: 5px; min-height: 44px; color: #2563eb; font-size: 13px; }
.mobile-source-links { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.mobile-source-links a { display: inline-flex; align-items: center; gap: 6px; min-height: 44px; color: #2563eb; }
.mobile-source-list > div { display: grid; grid-template-columns: 85px minmax(0, 1fr); gap: 12px; padding: 12px 0; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
.mobile-source-list dt { color: #64748b; }
.mobile-source-list dd { margin: 0; color: #0f172a; overflow-wrap: anywhere; }
.mobile-source-list a { color: #2563eb; }
.mobile-source-tags { margin-top: 20px; }
</style>
