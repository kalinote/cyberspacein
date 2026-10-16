<template>
  <el-tooltip
    v-if="hasPerm(PERM.operations.action.blueprint.update)"
    :content="blueprint.isPinned ? '取消置顶后将从所有用户的主页移除' : '置顶后所有用户均可在主页看到'"
    placement="top"
    :show-after="250"
  >
    <el-button
      :type="blueprint.isPinned ? 'primary' : ''"
      :circle="compact"
      :plain="compact"
      :link="!compact"
      :loading="saving"
      :aria-label="blueprint.isPinned ? '取消置顶' : '置顶到主页'"
      :aria-pressed="Boolean(blueprint.isPinned)"
      size="small"
      class="ml-0! shrink-0"
      @click.stop="togglePin"
    >
      <Icon v-if="!saving" :icon="blueprint.isPinned ? 'mdi:pin' : 'mdi:pin-outline'" class="text-base" />
      <span v-if="!compact">{{ blueprint.isPinned ? '取消置顶' : '置顶到主页' }}</span>
    </el-button>
  </el-tooltip>
</template>

<script setup>
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage } from 'element-plus'
import { actionApi } from '@/api/action'
import { PERM } from '@/utils/permissions'
import { hasPerm } from '@/utils/permissionKit'

const props = defineProps({
  blueprint: {
    type: Object,
    required: true
  },
  compact: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['change'])
const saving = ref(false)

/** 切换蓝图的全局置顶状态，成功后通知调用方。 */
const togglePin = async () => {
  if (saving.value || !hasPerm(PERM.operations.action.blueprint.update)) return
  saving.value = true
  try {
    const response = await actionApi.updateBlueprintPin(props.blueprint.id, !props.blueprint.isPinned)
    emit('change', response.data.is_pinned)
    ElMessage.success(response.data.is_pinned ? '已置顶到主页（全局生效）' : '已取消主页置顶（全局生效）')
  } catch {
    // 请求层统一展示错误，保留原有置顶状态。
  } finally {
    saving.value = false
  }
}
</script>
