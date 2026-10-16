<template>
  <nav v-if="entries.length" class="mobile-knowledge-nav" aria-label="情报资料分类">
    <button v-for="entry in entries" :key="entry.path" :disabled="!hasPerm(entry.permission.access)"
      :class="{ active: entry.path === activePath }" :aria-current="entry.path === activePath ? 'page' : undefined"
      @click="router.push(entry.path)">
      <Icon :icon="entry.icon" /><span>{{ entry.label }}</span>
    </button>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { hasPerm } from '@/utils/permissionKit'
import { KNOWLEDGE_DESTINATIONS } from '@/utils/knowledgeNavigation'

const router = useRouter()
const route = useRoute()
const entries = computed(() => KNOWLEDGE_DESTINATIONS.filter(entry => hasPerm(entry.permission.visible)))
const activePath = computed(() => route.path.startsWith('/evidence') ? '/evidence/chains'
  : route.path.startsWith('/target/wiki') || route.path.startsWith('/details/wiki') ? '/target/wiki'
  : route.path.startsWith('/target/highlights') ? '/target/highlights' : route.path === '/search' ? '/search' : '')
</script>

<style scoped>
.mobile-knowledge-nav { display: flex; gap: 4px; padding: 4px; margin-bottom: 16px; border: 1px solid #e2e8f0; border-radius: 13px; background: #edf2f8; }
.mobile-knowledge-nav button { display: flex; align-items: center; justify-content: center; flex: 1; min-width: 0; gap: 5px; min-height: 44px; border-radius: 9px; color: #65758b; font-size: 13px; }
.mobile-knowledge-nav button.active { background: #fff; color: #2563eb; font-weight: 600; box-shadow: 0 1px 3px #0f172a0a; }
.mobile-knowledge-nav svg { flex-shrink: 0; font-size: 18px; }
.mobile-knowledge-nav button:disabled { opacity: .45; cursor: not-allowed; }
.mobile-knowledge-nav button:focus-visible { outline: 2px solid #2563eb; outline-offset: -2px; }
</style>
