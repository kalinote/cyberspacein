<!--
  DetailPageHeader - 详情页头部组件
  
  用途：用于展示实体详情页面的头部，包含丰富的信息展示
  
  适用场景：
  - PlatformDetail（平台详情）
  - ForumDetail（论坛帖子详情）
  - ArticleDetail（文章详情）
  
  特点：
  - 支持显示 Logo 图标
  - 支持大标题和副标题
  - 支持标签展示
  - 支持外部链接
  - 包含装饰性背景元素
  
  Props:
  - title: 主标题
  - subtitle: 副标题（如 UUID）
  - logo: Logo 图片 URL
  - tags: 标签数组 [{ text: '标签文本', type: 'success' }]
  - links: 链接数组 [{ text: '链接文本', url: 'URL', icon: 'icon-name' }]
  - backHandler: 自定义返回处理函数
  
  插槽:
  - logo: 自定义 Logo 区域
  - title: 自定义标题区域
  - tags: 自定义标签区域
  - extra: 额外内容（在标签后面显示）
  
  使用示例：
  <DetailPageHeader
    :title="platformDetail.name"
    :subtitle="platformDetail.uuid"
    :logo="platformDetail.logo"
    :tags="[
      { text: '活跃', type: 'success' },
      { text: 'forum', type: 'primary' }
    ]"
    :links="[
      { text: '访问平台', url: platformDetail.url, icon: 'mdi:open-in-new' }
    ]"
  />
-->
<template>
  <section class="relative overflow-hidden bg-linear-to-br from-white to-blue-50 pt-12 pb-8">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <el-button 
        type="primary" 
        link 
        @click="handleBack" 
        class="mb-6"
      >
        <template #icon>
          <Icon icon="mdi:arrow-left" />
        </template>
        返回
      </el-button>
      
      <div class="flex items-start space-x-6">
        <div 
          v-if="logo || $slots.logo"
          class="w-20 h-20 bg-white rounded-2xl shadow-lg border border-gray-200 flex items-center justify-center overflow-hidden shrink-0"
        >
          <slot name="logo">
            <img 
              v-if="logo" 
              :src="logo" 
              :alt="title" 
              class="w-full h-full object-contain" 
            />
            <Icon v-else icon="mdi:web" class="text-blue-600 text-4xl" />
          </slot>
        </div>
        
        <div class="flex-1">
          <slot name="title">
            <h1 class="text-4xl md:text-5xl font-bold text-gray-900 mb-2">
              {{ title }}
            </h1>
            <p v-if="subtitle" class="text-gray-600 mb-4 font-mono text-sm">
              {{ subtitle }}
            </p>
          </slot>
          
          <div v-if="tags.length > 0 || $slots.tags" class="flex flex-wrap items-center gap-3">
            <slot name="tags">
              <el-tag
                v-for="(tag, index) in tags"
                :key="index"
                :type="tag.type || ''"
                size="default"
              >
                {{ tag.text }}
              </el-tag>
            </slot>
            
            <el-link
              v-for="(link, index) in links"
              :key="`link-${index}`"
              :href="link.url"
              target="_blank"
              type="primary"
              class="text-sm"
            >
              <template #icon>
                <Icon :icon="link.icon || 'mdi:open-in-new'" />
              </template>
              {{ link.text }}
            </el-link>
            
            <slot name="extra"></slot>
          </div>
        </div>
      </div>
    </div>
    
    <div class="absolute top-10 right-10 w-64 h-64 bg-blue-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20"></div>
    <div class="absolute bottom-10 left-10 w-64 h-64 bg-cyan-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20"></div>
  </section>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  subtitle: {
    type: String,
    default: ''
  },
  logo: {
    type: String,
    default: ''
  },
  tags: {
    type: Array,
    default: () => []
  },
  links: {
    type: Array,
    default: () => []
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
