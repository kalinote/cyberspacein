<template>
  <article class="highlight-reading-card">
    <div class="highlight-reading-card__tags">
      <span>{{ entityType === 'article' ? '文章' : entityType === 'forum' ? '论坛' : '资料' }}</span>
      <span v-if="entity.section">{{ entity.section }}</span>
      <span v-if="entity.nsfw" class="warning">NSFW</span>
      <span v-if="entity.aigc">AIGC</span>
    </div>
    <h3>
      <router-link v-if="detailPath" :to="detailPath">{{ plainExcerpt(entity.title, 160) || '无标题' }}</router-link>
      <span v-else>{{ plainExcerpt(entity.title, 160) || '无标题' }}</span>
    </h3>
    <p class="highlight-reading-card__excerpt">{{ plainExcerpt(entity.clean_content, 150) || '暂无分析内容' }}</p>
    <div class="highlight-reading-card__source">
      <Icon icon="mdi:source-repository" />
      <router-link v-if="entity.platform_id && hasAll([PERM.pages.search.access, PERM.operations.content.platform.read])" :to="`/details/platform/${encodeURIComponent(entity.platform_id)}`">{{ entity.platform || '来源平台' }}</router-link>
      <span v-else>{{ entity.platform || '来源未标注' }}</span>
    </div>
    <div class="highlight-reading-card__footer">
      <time :datetime="entity.update_at || undefined">更新于 {{ formatDateTime(entity.update_at, { defaultValue: '时间未记录' }) }}</time>
      <el-button v-if="manageable && canCancel" link type="danger" :loading="entity._highlightLoading" @click="$emit('cancel', entity)">
        <Icon icon="mdi:star-off-outline" />取消重点
      </el-button>
    </div>
    <p v-if="!detailPath" class="highlight-reading-card__permission">暂无正文阅读权限</p>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { hasAll } from '@/utils/permissionKit'
import { PERM } from '@/utils/permissions'
import { formatDateTime } from '@/utils/action/formatters'
import { plainExcerpt, entityDetailPath } from './targetContent'

const props = defineProps({ entity: { type: Object, required: true }, manageable: { type: Boolean, default: false } })
defineEmits(['cancel'])
const entityType = computed(() => String(props.entity.entity_type || '').toLowerCase())
const detailPath = computed(() => entityDetailPath(props.entity))
const canCancel = computed(() => props.entity.uuid && ['article', 'forum'].includes(entityType.value) && hasAll([
  PERM.pages.target.highlights.access, PERM.operations.target.highlight.update
]))
</script>

<style scoped>
.highlight-reading-card { min-width: 0; padding: 16px; background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; }
.highlight-reading-card__tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; color: #64748b; font-size: 11px; }
.highlight-reading-card__tags span { max-width: 100%; overflow-wrap: anywhere; padding: 2px 7px; border-radius: 5px; background: #f1f5f9; }
.highlight-reading-card__tags span:first-child { background: #eff6ff; color: #2563eb; }
.highlight-reading-card__tags .warning { background: #fff1f2; color: #be123c; }
.highlight-reading-card h3 { margin: 0 0 8px; color: #0f172a; font-size: 16px; font-weight: 650; line-height: 1.6; overflow-wrap: anywhere; }
.highlight-reading-card h3 a { display: block; }
.highlight-reading-card h3 a:focus-visible { outline: 2px solid #2563eb; outline-offset: 4px; border-radius: 4px; }
.highlight-reading-card__excerpt { margin: 0 0 12px; color: #64748b; font-size: 13px; line-height: 1.75; overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.highlight-reading-card__source { display: flex; align-items: center; gap: 6px; min-width: 0; color: #64748b; font-size: 12px; }
.highlight-reading-card__source svg { flex-shrink: 0; }
.highlight-reading-card__source a, .highlight-reading-card__source span { overflow-wrap: anywhere; min-width: 0; }
.highlight-reading-card__source a { color: #2563eb; }
.highlight-reading-card__footer { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 4px 8px; margin-top: 8px; color: #94a3b8; font-size: 11px; }
.highlight-reading-card__footer time { overflow-wrap: anywhere; }
.highlight-reading-card__footer .el-button { min-height: 44px; margin: 0; font-size: 12px; gap: 4px; }
.highlight-reading-card__permission { margin: 8px 0 0; color: #94a3b8; font-size: 11px; }
</style>
