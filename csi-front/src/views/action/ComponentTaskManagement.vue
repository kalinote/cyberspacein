<template>
  <div class="h-screen flex flex-col bg-gray-50">
    <Header />

    <FunctionalPageHeader
      title-prefix="组件任务"
      title-suffix="管理"
      subtitle="管理组件任务与调度"
    >
      <template #actions>
        <div class="flex items-center gap-3">
          <div class="bg-white rounded-lg px-4 py-2 shadow-sm border border-blue-100 flex items-center gap-3">
            <Icon icon="mdi:clipboard-text-outline" class="text-blue-600 text-xl" />
            <div>
              <p class="text-xs text-gray-500">任务数</p>
              <p class="text-lg font-bold text-gray-900">{{ statistics.task_count }}</p>
            </div>
          </div>
          <div class="bg-white rounded-lg px-4 py-2 shadow-sm border border-green-100 flex items-center gap-3">
            <Icon icon="mdi:calendar-clock" class="text-green-600 text-xl" />
            <div>
              <p class="text-xs text-gray-500">调度数</p>
              <p class="text-lg font-bold text-gray-900">{{ statistics.schedule_count }}</p>
            </div>
          </div>
        </div>
      </template>
    </FunctionalPageHeader>

    <div class="flex-1 flex overflow-hidden">
      <div class="bg-white w-72 border-r border-gray-200 shrink-0 overflow-y-auto">
        <div class="p-4">
          <h3 class="text-sm font-semibold text-gray-500 uppercase mb-3">组件任务</h3>
          <div class="space-y-1">
            <div
              v-for="tab in sidebarTabs"
              :key="tab.key"
              class="flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer transition-all"
              :class="activeTab === tab.key
                ? 'bg-blue-50 text-blue-600 font-medium shadow-sm border border-blue-200'
                : 'text-gray-600 hover:bg-gray-50'"
              @click="activeTab = tab.key"
            >
              <span class="w-5"></span>
              <Icon :icon="tab.icon" class="text-xl shrink-0" />
              <span>{{ tab.label }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="flex-1 flex flex-col overflow-hidden">
        <div class="bg-white px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <Icon :icon="currentTabIcon" class="text-2xl text-blue-600" />
            <h2 class="text-xl font-bold text-gray-900">{{ currentTabLabel }}</h2>
          </div>
          <div class="flex items-center gap-3">
            <el-input
              v-model="searchKeyword"
              :placeholder="activeTab === 'tasks' ? '搜索任务...' : '搜索调度...'"
              clearable
              class="w-64"
            >
              <template #prefix>
                <Icon icon="mdi:magnify" class="text-gray-400" />
              </template>
            </el-input>
            <el-button type="primary" @click="handleAdd">
              <template #icon>
                <Icon icon="mdi:plus" />
              </template>
              新增{{ currentTabLabel }}
            </el-button>
          </div>
        </div>

        <div class="flex-1 overflow-auto p-6">
          <div class="flex flex-col items-center justify-center py-16">
            <Icon icon="mdi:wrench" class="text-6xl text-gray-300 mb-4" />
            <p class="text-gray-500 text-lg mb-2">功能开发中</p>
            <p class="text-gray-400 text-sm">{{ currentTabLabel }}内容即将上线</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'

export default {
  name: 'ComponentTaskManagement',
  components: {
    Header,
    Icon,
    FunctionalPageHeader
  },
  data() {
    return {
      activeTab: 'tasks',
      searchKeyword: '',
      statistics: {
        task_count: 0,
        schedule_count: 0
      },
      sidebarTabs: [
        { key: 'tasks', label: '任务', icon: 'mdi:clipboard-text-outline' },
        { key: 'schedule', label: '调度', icon: 'mdi:calendar-clock' }
      ]
    }
  },
  methods: {
    handleAdd() {
      this.$message.info(`新增${this.currentTabLabel}功能开发中`)
    }
  },
  computed: {
    currentTabIcon() {
      const tab = this.sidebarTabs.find(t => t.key === this.activeTab)
      return tab ? tab.icon : 'mdi:help'
    },
    currentTabLabel() {
      const tab = this.sidebarTabs.find(t => t.key === this.activeTab)
      return tab ? tab.label : ''
    }
  }
}
</script>
