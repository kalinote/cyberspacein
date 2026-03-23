<template>
  <div class="h-screen flex flex-col bg-gray-50">
    <Header />
    <FunctionalPageHeader
      :title-prefix="titlePrefix"
      :title-suffix="titleSuffix"
      :subtitle="subtitle"
      :highlight-color="highlightColor"
    >
      <template #actions>
        <slot name="actions"></slot>
      </template>
    </FunctionalPageHeader>

    <div class="flex-1 flex overflow-hidden">
      <template v-if="$slots.sidebar">
        <slot name="sidebar"></slot>
      </template>
      <div
        v-else
        class="bg-white w-72 border-r border-gray-200 shrink-0 overflow-y-auto"
      >
        <ConfigCenterSidebar
          :sidebar-title="sidebarTitle"
          :items="navItems"
          :model-value="modelValue"
          :expanded-keys="expandedKeys"
          :get-badge="getBadge"
          @update:model-value="emit('update:modelValue', $event)"
          @update:expanded-keys="emit('update:expandedKeys', $event)"
        />
      </div>

      <div class="flex-1 flex flex-col overflow-hidden">
        <slot name="toolbar"></slot>
        <div class="flex-1 overflow-auto p-6">
          <slot></slot>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import ConfigCenterSidebar from '@/components/layout/ConfigCenterSidebar.vue'

/**
 * @typedef {import('@/utils/configCenterNav.js').ConfigNavItem} ConfigNavItem
 */

defineProps({
  titlePrefix: {
    type: String,
    default: ''
  },
  titleSuffix: {
    type: String,
    default: ''
  },
  subtitle: {
    type: String,
    default: ''
  },
  highlightColor: {
    type: String,
    default: 'blue-500'
  },
  sidebarTitle: {
    type: String,
    default: ''
  },
  /** @type {import('vue').PropType<ConfigNavItem[]>} */
  navItems: {
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
</script>
