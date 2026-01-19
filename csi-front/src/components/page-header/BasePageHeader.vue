<!--
  BasePageHeader - 基础页面头部组件
  
  用途：作为其他页面头部组件的基础，封装统一的返回按钮和蓝色渐变样式
  
  适用场景：通常不直接使用，而是被其他 PageHeader 组件继承
  
  Props:
  - showBack: 是否显示返回按钮（默认 true）
  - backHandler: 自定义返回处理函数（默认使用 router.back()）
  
  插槽:
  - default: 主内容区域
  - actions: 右侧操作区域
  
  使用示例：
  <BasePageHeader>
    <h1>页面标题</h1>
  </BasePageHeader>
-->
<template>
  <section class="bg-linear-to-br from-blue-50 to-white py-6 border-b border-gray-200">
    <div class="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-6">
          <el-button 
            v-if="showBack"
            type="primary" 
            link 
            @click="handleBack" 
            class="shrink-0"
          >
            <template #icon>
              <Icon icon="mdi:arrow-left" />
            </template>
            返回
          </el-button>
          <div v-if="showBack" class="border-l border-gray-300 h-8"></div>
          <slot></slot>
        </div>
        <slot name="actions"></slot>
      </div>
    </div>
  </section>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'

const props = defineProps({
  showBack: {
    type: Boolean,
    default: true
  },
  backHandler: {
    type: Function,
    default: null
  }
})

const router = useRouter()

const handleBack = () => {
  if (props.backHandler) {
    props.backHandler()
  } else {
    router.back()
  }
}
</script>
