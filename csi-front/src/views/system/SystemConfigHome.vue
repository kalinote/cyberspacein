<template>
  <div class="min-h-screen bg-gray-50">
    <Header />
    <FunctionalPageHeader
      title-prefix="系统"
      title-suffix="配置"
      subtitle="集中管理系统级参数与入口，后续可在此扩展告警策略、集成与安全等相关能力。"
    />
    <div class="max-w-480 mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="bg-white rounded-2xl p-8 shadow-sm border border-gray-200">
        <div class="flex items-start gap-4">
          <div class="w-14 h-14 rounded-xl bg-linear-to-br from-blue-500 to-cyan-400 flex items-center justify-center shrink-0">
            <Icon icon="mdi:cog-outline" class="text-white text-3xl" />
          </div>
          <div class="flex-1">
            <h2 class="text-xl font-bold text-gray-900 mb-2">欢迎使用系统配置</h2>
            <p class="text-gray-600 leading-relaxed mb-6">
              此处为系统配置总览占位页。您可通过顶部导航「系统配置」下的子菜单进入告警信息中心，或使用「用户权限管理」维护账号与访问控制。
            </p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div class="rounded-xl border border-blue-100 bg-blue-50/50 p-4">
                <p class="text-sm font-medium text-blue-800 mb-1">快捷提示</p>
                <p class="text-sm text-blue-700/90">告警规则与列表请从子菜单「告警信息」进入。</p>
              </div>
              <div class="rounded-xl border border-gray-200 bg-gray-50 p-4">
                <p class="text-sm font-medium text-gray-800 mb-1">后续规划</p>
                <p class="text-sm text-gray-600">可在此汇总全局开关、第三方集成与审计入口等模块。</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'

defineOptions({ name: 'SystemConfigHome' })
</script>
