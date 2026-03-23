<template>
  <div class="p-4">
    <h3 v-if="sidebarTitle" class="text-sm font-semibold text-gray-500 uppercase mb-3">{{ sidebarTitle }}</h3>
    <div class="space-y-1">
      <template v-for="tab in items" :key="tab.key">
        <div
          class="flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer transition-all"
          :class="
            modelValue === tab.key
              ? 'bg-blue-50 text-blue-600 font-medium shadow-sm border border-blue-200'
              : 'text-gray-600 hover:bg-gray-50'
          "
          @click="emit('update:modelValue', tab.key)"
        >
          <Icon
            v-if="tab.children && tab.children.length > 0"
            :icon="isExpanded(tab.key) ? 'mdi:chevron-down' : 'mdi:chevron-right'"
            class="text-sm cursor-pointer shrink-0"
            @click.stop="toggleExpand(tab.key)"
          />
          <span v-else class="w-5"></span>
          <Icon :icon="tab.icon" class="text-xl shrink-0" />
          <span>{{ tab.label }}</span>
          <span
            v-if="showBadge"
            class="ml-auto text-xs px-2 py-0.5 rounded-full"
            :class="modelValue === tab.key ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'"
          >
            {{ badgeFor(tab.key) }}
          </span>
        </div>
        <div
          v-if="tab.children && tab.children.length > 0 && isExpanded(tab.key)"
          class="ml-4 space-y-1"
        >
          <div
            v-for="child in tab.children"
            :key="child.key"
            class="flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer transition-all"
            :class="
              modelValue === child.key
                ? 'bg-blue-50 text-blue-600 font-medium shadow-sm border border-blue-200'
                : 'text-gray-600 hover:bg-gray-50'
            "
            @click="emit('update:modelValue', child.key)"
          >
            <span class="w-5"></span>
            <Icon :icon="child.icon" class="text-xl shrink-0" />
            <span>{{ child.label }}</span>
            <span
              v-if="showBadge"
              class="ml-auto text-xs px-2 py-0.5 rounded-full"
              :class="modelValue === child.key ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'"
            >
              {{ badgeFor(child.key) }}
            </span>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'

/**
 * @typedef {import('@/utils/configCenterNav.js').ConfigNavItem} ConfigNavItem
 */

const props = defineProps({
  sidebarTitle: {
    type: String,
    default: ''
  },
  /** @type {import('vue').PropType<ConfigNavItem[]>} */
  items: {
    type: Array,
    default: () => []
  },
  modelValue: {
    type: String,
    default: ''
  },
  expandedKeys: {
    type: Array,
    default: () => []
  },
  /** @type {import('vue').PropType<(key: string) => number>|undefined} */
  getBadge: {
    type: Function,
    default: undefined
  }
})

const emit = defineEmits(['update:modelValue', 'update:expandedKeys'])

const showBadge = computed(() => typeof props.getBadge === 'function')

function badgeFor(key) {
  return props.getBadge(key)
}

function isExpanded(key) {
  return props.expandedKeys.includes(key)
}

function toggleExpand(key) {
  const next = new Set(props.expandedKeys)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  emit('update:expandedKeys', [...next])
}
</script>
