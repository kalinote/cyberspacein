<!--
  SimplePageHeader - 简单页头部组件
  
  用途：用于编辑器和全屏工作区页面的简洁头部
  
  适用场景：
  - NewActionBlueprint（创建行动蓝图）
  - ActionDetail（行动详情/执行界面）
  
  特点：
  - 扁平化设计，无渐变背景
  - 极简布局，节省空间
  - 适合需要最大化内容区域的页面
  
  Props:
  - title: 标题文本
  - backHandler: 自定义返回处理函数
  
  插槽:
  - default: 自定义标题区域（会替换默认标题）
  - actions: 右侧操作区域
  
  使用示例：
  <SimplePageHeader title="创建标准行动蓝图" />
  
  或使用插槽自定义：
  <SimplePageHeader>
    <span class="text-xl font-bold">{{ dynamicTitle }}</span>
  </SimplePageHeader>
-->
<template>
  <div class="px-5 py-3 bg-white border-b border-gray-200 flex items-center shrink-0">
    <el-button 
      type="primary" 
      link 
      @click="handleBack" 
      class="mb-0!"
    >
      <template #icon>
        <Icon icon="mdi:arrow-left" />
      </template>
      返回
    </el-button>
    
    <slot>
      <span v-if="title" class="text-xl font-bold text-gray-800 ml-4">{{ title }}</span>
    </slot>
    
    <slot name="actions"></slot>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'

const props = defineProps({
  title: {
    type: String,
    default: ''
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
