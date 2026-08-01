<template>
  <div v-if="compact" class="inline-flex items-center">
    <el-button type="primary" link size="small" :disabled="disabled" @click="emit('run')">
      <template #icon><Icon icon="mdi:rocket-launch" /></template>
      执行
    </el-button>
    <el-dropdown
      trigger="click"
      placement="bottom-end"
      :disabled="disabled"
      @command="handleCommand"
    >
      <el-button
        type="primary"
        link
        circle
        size="small"
        :disabled="disabled"
        aria-label="更多运行方式"
        class="ml-0! px-1!"
        @click.stop
      >
        <Icon icon="mdi:chevron-down" />
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="debug">
            <Icon icon="mdi:bug-outline" class="mr-2 text-slate-500" />
            调试运行
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>

  <el-dropdown
    v-else
    split-button
    type="primary"
    class="run-split-button w-full"
    :disabled="disabled"
    @click="emit('run')"
    @command="handleCommand"
  >
    <span class="inline-flex items-center justify-center gap-2">
      <Icon icon="mdi:rocket-launch" />
      立即执行行动
    </span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="debug">
          <Icon icon="mdi:bug-outline" class="mr-2 text-slate-500" />
          调试运行
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
import { Icon } from '@iconify/vue'

defineProps({
  disabled: {
    type: Boolean,
    default: false
  },
  compact: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['run', 'debug'])

const handleCommand = command => {
  if (command === 'debug') emit('debug')
}
</script>

<style scoped>
.run-split-button {
  display: flex;
  width: 100%;
}

.run-split-button :deep(.el-button-group) {
  display: flex;
  width: 100%;
}

.run-split-button :deep(.el-button-group > .el-button:first-child) {
  flex: 1 1 auto;
}

.run-split-button :deep(.el-dropdown__caret-button) {
  flex: 0 0 auto;
}
</style>
