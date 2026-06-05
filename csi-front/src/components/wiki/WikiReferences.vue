<template>
  <section id="references" class="scroll-mt-24">
    <div class="flex items-center justify-between gap-2 border-b border-gray-100 pb-2 mb-3">
      <h2 class="text-xl font-bold text-gray-900 flex items-center gap-2 m-0">
        <Icon icon="mdi:book-open-variant" class="text-blue-500" />
        参考资料
      </h2>
      <slot name="actions" />
    </div>
    <ol v-if="references.length" class="wiki-references-list">
      <li
        v-for="ref in references"
        :key="ref.id"
        :id="`ref-${ref.id}`"
        class="wiki-ref-item"
      >
        <span class="wiki-ref-index">{{ ref.id }}.</span>
        <p class="wiki-ref-content">
          <span class="wiki-ref-text">{{ ref.text }}</span>
          <router-link
            v-if="ref.url && isAppRoute(ref.url)"
            :to="ref.url"
            class="wiki-ref-go"
            :aria-label="`查看参考资料 ${ref.id} 来源`"
            :title="`查看参考资料 ${ref.id} 来源`"
          >
            <Icon icon="mdi:link-variant" class="wiki-ref-go-icon" aria-hidden="true" />
          </router-link>
          <a
            v-else-if="ref.url"
            :href="ref.url"
            target="_blank"
            rel="noopener noreferrer"
            class="wiki-ref-go"
            :aria-label="`查看参考资料 ${ref.id} 来源（新窗口）`"
            :title="`查看参考资料 ${ref.id} 来源`"
          >
            <Icon icon="mdi:open-in-new" class="wiki-ref-go-icon" aria-hidden="true" />
          </a>
        </p>
      </li>
    </ol>
    <p v-else class="text-sm text-gray-400 m-0">暂无参考资料</p>
  </section>
</template>

<script setup>
import { Icon } from '@iconify/vue'

function isAppRoute(url) {
  return typeof url === 'string' && url.startsWith('/') && !url.startsWith('//')
}

defineProps({
  references: {
    type: Array,
    default: () => [],
  },
})
</script>

<style scoped>
.wiki-references-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.35rem 1.75rem;
  list-style: none;
  padding: 0;
  margin: 0;
}

@media (min-width: 768px) {
  .wiki-references-list {
    grid-template-columns: 1fr 1fr;
  }
}

.wiki-ref-item {
  display: flex;
  align-items: flex-start;
  gap: 0.2rem;
  font-size: 0.8125rem;
  line-height: 1.35;
  color: #374151;
  text-align: left;
  scroll-margin-top: 6rem;
  padding: 0.1rem 0.2rem;
  border-radius: 0.25rem;
  transition: background-color 0.2s ease, box-shadow 0.2s ease;
}

.wiki-ref-item.wiki-ref-highlight {
  background-color: #eff6ff;
  box-shadow: inset 0 0 0 1px #bfdbfe;
}

.wiki-ref-index {
  flex-shrink: 0;
  font-weight: 500;
  color: #6b7280;
  min-width: 1.35rem;
  padding-top: 0.05em;
}

.wiki-ref-content {
  flex: 1;
  min-width: 0;
  margin: 0;
  text-align: left;
  word-break: break-word;
}

.wiki-ref-text {
  color: inherit;
}

.wiki-ref-go {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  vertical-align: -0.12em;
  margin-left: 0.2em;
  padding: 0.05em;
  color: #2563eb;
  text-decoration: none;
  border-radius: 0.2rem;
  transition: color 0.15s ease, background-color 0.15s ease;
}

.wiki-ref-go:hover {
  color: #1d4ed8;
  background-color: #eff6ff;
}

.wiki-ref-go-icon {
  width: 0.875rem;
  height: 0.875rem;
  flex-shrink: 0;
}
</style>
