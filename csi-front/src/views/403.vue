<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center p-6">
    <el-card class="w-full max-w-md">
      <div class="flex flex-col items-center text-center">
        <div class="text-6xl font-bold text-red-500 leading-none mb-4">403</div>
        <h2 class="text-xl font-bold text-gray-900 mb-2">无权限访问</h2>
        <p class="text-gray-600 mb-6">当前账号没有访问该页面的权限。</p>
        <el-button type="primary" @click="router.push('/')">返回首页</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

defineOptions({ name: '403' })

const router = useRouter()
</script>

