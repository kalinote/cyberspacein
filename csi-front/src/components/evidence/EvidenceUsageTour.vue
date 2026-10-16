<template>
  <el-button :size="size" @click="current = 0; open = true">
    <Icon icon="mdi:help-circle-outline" class="mr-1" />使用引导
  </el-button>
  <el-config-provider :locale="zhCn">
    <el-tour
      v-model="open"
      v-model:current="current"
      :target-area-clickable="false"
      :mask="{ color: 'rgba(15, 23, 42, 0.5)' }"
      :gap="{ offset: 8, radius: 8 }"
      :content-style="{ width: '380px', maxWidth: 'calc(100vw - 32px)' }"
      :scroll-into-view-options="{ block: 'nearest', inline: 'nearest' }"
    >
      <el-tour-step
        v-for="(step, index) in resolvedSteps"
        :key="step.title"
        :target="step.target"
        :title="step.title"
        :placement="step.placement || 'bottom'"
        :prev-button-props="{ children: '上一步' }"
        :next-button-props="{ children: index === resolvedSteps.length - 1 ? '开始使用' : '下一步' }"
      >
        <p v-for="paragraph in step.content" :key="paragraph" class="text-sm leading-6 text-gray-600 mb-2">
          {{ paragraph }}
        </p>
      </el-tour-step>
      <template #indicators="{ current: index, total }">
        <div class="flex items-center gap-3">
          <span class="text-xs text-gray-500">{{ index + 1 }} / {{ total }}</span>
          <el-button link size="small" @click="open = false">结束引导</el-button>
        </div>
      </template>
    </el-tour>
  </el-config-provider>
</template>

<script setup>
import { computed, ref } from 'vue';
import { Icon } from '@iconify/vue';
import zhCn from 'element-plus/es/locale/lang/zh-cn';

const props = defineProps({
  steps: { type: Array, required: true },
  size: { type: String, default: 'default' }
});

const open = ref(false);
const current = ref(0);
const resolvedSteps = computed(() => props.steps.map(step => ({
  ...step,
  target: () => {
    const target = step.target ? document.querySelector(step.target) : null;
    return target?.getClientRects().length ? target : undefined;
  }
})));
</script>
