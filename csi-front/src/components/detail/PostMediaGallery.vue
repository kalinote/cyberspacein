<template>
  <section v-if="media.length" class="post-media" aria-label="贴文媒体">
    <div class="post-media-heading"><h3>媒体内容</h3><span>{{ media.length }} 项</span></div>
    <div class="post-media-grid" :class="{ 'post-media-grid--single': imageUrls.length <= 1 }">
      <figure v-for="item in media" :key="item.key" class="post-media-item" :class="{ 'post-media-item--wide': item.type !== 'image' }">
        <el-image v-if="item.type === 'image'" :src="item.url" :alt="item.name" fit="contain" loading="lazy"
          :preview-src-list="imageUrls" :initial-index="imageUrls.indexOf(item.url)" preview-teleported hide-on-click-modal>
          <template #error><div class="post-media-unavailable"><Icon icon="mdi:image-off-outline" /><span>图片暂时无法加载</span></div></template>
        </el-image>
        <template v-else-if="item.type === 'video' || item.type === 'audio'">
          <div v-if="failedUrls.has(item.url)" class="post-media-unavailable"><Icon icon="mdi:alert-circle-outline" /><span>媒体暂时无法播放，可打开文件查看</span></div>
          <video v-else-if="item.type === 'video'" :src="item.url" :poster="item.poster || undefined" :aria-label="item.name"
            controls playsinline preload="metadata" @error="failedUrls.add(item.url)">当前浏览器不支持视频播放。</video>
          <audio v-else :src="item.url" :aria-label="item.name" controls preload="metadata" @error="failedUrls.add(item.url)">当前浏览器不支持音频播放。</audio>
        </template>
        <a v-else class="post-media-file" :href="item.url" target="_blank" rel="noopener noreferrer"><Icon icon="mdi:file-document-outline" /><span>{{ item.name }}</span><Icon icon="mdi:open-in-new" /></a>
        <figcaption>
          <span>{{ item.name }}</span>
          <span v-if="item.status === 'failed' || item.status === 'skipped'" class="post-media-status">{{ item.status === 'failed' ? '归档失败，使用来源地址' : '未归档，使用来源地址' }}</span>
          <a :href="item.url" target="_blank" rel="noopener noreferrer">打开文件<Icon icon="mdi:open-in-new" /></a>
        </figcaption>
      </figure>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { normalizePostMedia } from '@/utils/postMedia'

const props = defineProps({ post: { type: Object, required: true } })
const media = computed(() => normalizePostMedia(props.post))
const imageUrls = computed(() => media.value.filter(item => item.type === 'image').map(item => item.url))
const failedUrls = ref(new Set())
watch(() => props.post, () => { failedUrls.value = new Set() })
</script>

<style scoped>
.post-media { margin-top: 28px; }
.post-media-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.post-media-heading h3 { font-size: 15px; font-weight: 600; color: #334155; }
.post-media-heading > span { color: #94a3b8; font-size: 12px; }
.post-media-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.post-media-grid--single { grid-template-columns: minmax(0, 1fr); }
.post-media-item { min-width: 0; margin: 0; overflow: hidden; border: 1px solid #e2e8f0; border-radius: 12px; background: #f8fafc; }
.post-media-item--wide { grid-column: 1 / -1; }
.post-media-item :deep(.el-image) { display: block; width: 100%; height: 280px; background: #f1f5f9; }
.post-media-grid--single :deep(.el-image) { height: auto; min-height: 180px; max-height: 600px; }
.post-media-grid--single :deep(.el-image__inner) { max-height: 600px; }
video { display: block; width: 100%; max-height: 560px; background: #0f172a; }
audio { display: block; width: calc(100% - 24px); margin: 20px 12px; }
figcaption { display: flex; align-items: center; flex-wrap: wrap; gap: 6px 12px; padding: 10px 12px; font-size: 12px; color: #64748b; overflow-wrap: anywhere; }
figcaption a { display: inline-flex; align-items: center; gap: 4px; margin-left: auto; color: #2563eb; min-height: 28px; }
.post-media-status { color: #b45309; }
.post-media-file { display: flex; align-items: center; gap: 12px; padding: 24px 16px; color: #2563eb; font-size: 14px; overflow-wrap: anywhere; }
.post-media-file > svg { flex-shrink: 0; font-size: 24px; }
.post-media-unavailable { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; min-height: 150px; padding: 20px; color: #64748b; font-size: 13px; }
.post-media-unavailable > svg { font-size: 28px; }
@media (max-width: 767px) {
  .post-media-grid { gap: 8px; }
  .post-media-item :deep(.el-image) { height: 170px; }
  .post-media-grid--single :deep(.el-image) { height: auto; }
  figcaption { gap: 4px; padding: 8px; }
  figcaption a { min-height: 36px; }
}
</style>
