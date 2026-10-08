<template>
  <div class="config-center-layout h-screen flex flex-col bg-gray-50" :class="{ 'mobile-config-center': isMobile }">
    <Header v-if="!isMobile" />
    <FunctionalPageHeader
      v-if="!isMobile"
      :title-prefix="titlePrefix"
      :title-suffix="titleSuffix"
      :subtitle="subtitle"
      :highlight-color="highlightColor"
    >
      <template #actions>
        <slot name="actions"></slot>
      </template>
    </FunctionalPageHeader>

    <section v-if="isMobile" class="mobile-config-heading">
      <button v-if="!directoryVisible" type="button" @click="directoryVisible = true"><Icon icon="mdi:chevron-left" />模块目录</button>
      <h1>{{ directoryVisible ? titlePrefix + titleSuffix : currentItem?.label || titlePrefix + titleSuffix }}</h1>
      <p>{{ directoryVisible ? subtitle : '查看配置详情，或选择项目进行修改' }}</p>
    </section>
    <nav v-if="isMobile && directoryVisible" class="mobile-config-directory" :aria-label="sidebarTitle || '配置模块'">
      <section v-for="item in navItems" :key="item.key">
        <button type="button" :disabled="item.disabled" @click="emit('update:modelValue', item.key); directoryVisible = false">
          <Icon :icon="item.icon" /><strong>{{ item.label }}</strong><span v-if="getBadge">{{ getBadge(item.key) >= 0 ? getBadge(item.key) : '—' }}</span><Icon :icon="item.disabled ? 'mdi:lock-outline' : 'mdi:chevron-right'" />
        </button>
        <div v-if="item.children?.length" class="mobile-config-children">
          <button v-for="child in item.children" :key="child.key" type="button" :disabled="child.disabled" @click="emit('update:modelValue', child.key); directoryVisible = false">
            <Icon :icon="child.icon" /><span>{{ child.label }}</span><small v-if="getBadge">{{ getBadge(child.key) >= 0 ? getBadge(child.key) : '—' }}</small><Icon :icon="child.disabled ? 'mdi:lock-outline' : 'mdi:chevron-right'" />
          </button>
        </div>
      </section>
      <p v-if="!navItems.length" class="text-center text-gray-500 py-8">暂无可访问的配置模块</p>
    </nav>
    <div v-show="!isMobile || !directoryVisible" class="config-center-body flex-1 flex overflow-hidden">
      <template v-if="!isMobile && $slots.sidebar">
        <slot name="sidebar"></slot>
      </template>
      <div
        v-else-if="!isMobile"
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

      <div class="config-center-content flex-1 flex flex-col overflow-hidden">
        <slot name="toolbar"></slot>
        <div class="config-center-items flex-1 overflow-auto p-6">
          <slot></slot>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { findNavItemByKey } from '@/utils/configCenterNav'
import './mobileConfig.css'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import ConfigCenterSidebar from '@/components/layout/ConfigCenterSidebar.vue'

/**
 * @typedef {import('@/utils/configCenterNav.js').ConfigNavItem} ConfigNavItem
 */

const props = defineProps({
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
const { isMobile } = useMobileViewport()
const directoryVisible = ref(true)
const currentItem = computed(() => findNavItemByKey(props.navItems, props.modelValue))
</script>
