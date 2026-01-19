<!--
  FunctionalPageHeader - 功能/列表页头部组件
  
  用途：用于列表页面和功能配置页面的头部
  
  适用场景：
  - PlatformList（平台列表）
  - ActionResourceConfig（行动资源配置）
  - ActionHistory（历史行动记录）
  - ActionBlueprintList（行动蓝图列表）
  
  特点：
  - 紧凑的布局设计
  - 支持标题前缀高亮（如"平台"列表）
  - 支持右侧统计卡片或操作按钮
  
  Props:
  - title: 完整标题（当不使用 titlePrefix/titleSuffix 时）
  - titlePrefix: 标题前缀（会被高亮显示）
  - titleSuffix: 标题后缀
  - subtitle: 副标题描述
  - highlightColor: 高亮颜色（默认 'blue-500'）
  - backHandler: 自定义返回处理函数
  
  插槽:
  - title: 自定义标题区域
  - subtitle: 自定义副标题区域
  - actions: 右侧操作区域（如统计卡片）
  
  使用示例：
  <FunctionalPageHeader
    title-prefix="平台"
    title-suffix="列表"
    subtitle="统一管理所有平台信息"
  >
    <template #actions>
      <div class="统计卡片">...</div>
    </template>
  </FunctionalPageHeader>
-->
<template>
  <section class="bg-linear-to-br from-blue-50 to-white py-6 border-b border-gray-200">
    <div class="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-6">
          <el-button 
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
          <div class="border-l border-gray-300 h-8"></div>
          <div>
            <slot name="title">
              <h1 class="text-2xl font-bold text-gray-900 mb-1">
                <span :class="`text-${highlightColor}`">{{ titlePrefix }}</span>{{ titleSuffix }}
              </h1>
            </slot>
            <slot name="subtitle">
              <p v-if="subtitle" class="text-sm text-gray-600">{{ subtitle }}</p>
            </slot>
          </div>
        </div>
        <slot name="actions"></slot>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
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
