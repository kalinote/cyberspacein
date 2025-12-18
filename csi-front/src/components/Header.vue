<template>
  <header class="sticky top-0 z-50 bg-white/90 backdrop-blur-sm border-b border-blue-100 transition-all duration-300">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center h-16">
        <div class="flex items-center">
          <div class="flex items-center space-x-2">
            <div class="w-8 h-8 bg-linear-to-br from-blue-500 to-cyan-400 rounded-lg flex items-center justify-center">
              <Icon icon="mdi:database-search" class="text-white text-lg" />
            </div>
            <span class="text-xl font-bold text-gray-800">CyberSpace<span class="text-blue-500">IN</span></span>
          </div>

          <nav class="hidden md:flex ml-10 space-x-8">
            <router-link to="/" class="text-gray-600 hover:text-blue-600 font-medium px-3 py-2 rounded-md hover:bg-blue-50 transition-colors" active-class="!text-blue-600 !bg-blue-50">概览</router-link>
            <router-link to="/search" class="text-gray-600 hover:text-blue-600 font-medium px-3 py-2 rounded-md hover:bg-blue-50 transition-colors" active-class="!text-blue-600 !bg-blue-50">信息检索</router-link>
            <router-link to="/action" class="text-gray-600 hover:text-blue-600 font-medium px-3 py-2 rounded-md hover:bg-blue-50 transition-colors" active-class="!text-blue-600 !bg-blue-50">行动部署</router-link>
            <router-link to="/agent" class="text-gray-600 hover:text-blue-600 font-medium px-3 py-2 rounded-md hover:bg-blue-50 transition-colors" active-class="!text-blue-600 !bg-blue-50">智能体</router-link>
            <a href="#" class="text-gray-600 hover:text-blue-600 font-medium px-3 py-2 rounded-md hover:bg-blue-50 transition-colors">报告</a>
            <router-link to="/alert" class="text-gray-600 hover:text-blue-600 font-medium px-3 py-2 rounded-md hover:bg-blue-50 transition-colors" active-class="!text-blue-600 !bg-blue-50">告警信息</router-link>
          </nav>
        </div>

        <div class="flex items-center space-x-4">
          <div class="hidden md:block">
            <el-input
              placeholder="快速检索..."
              :prefix-icon="'Search'"
              style="width: 260px"
              clearable
            />
          </div>
          <div class="w-8 h-8 bg-linear-to-br from-blue-100 to-cyan-100 rounded-full flex items-center justify-center cursor-pointer">
            <Icon icon="mdi:account" class="text-blue-600" />
          </div>
        </div>
      </div>
    </div>
  </header>
</template>

<script>
import { Icon } from '@iconify/vue'

export default {
  name: 'Header',
  components: {
    Icon
  }
}
</script>
