<template>
  <div class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100 hover:shadow-xl transition-shadow flex flex-col">
    <div class="mb-4">
      <div class="flex items-start justify-between gap-3 mb-4">
        <h3 class="text-xl font-bold text-gray-900 min-w-0 line-clamp-2">{{ blueprint.title }}</h3>
        <BlueprintPinButton
          compact
          :blueprint="blueprint"
          @change="emit('pin-change', $event)"
        />
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <el-tag
          v-if="blueprint.taskType"
          class="border-0"
          :style="{ backgroundColor: blueprint.taskTypeTagColor, color: blueprint.taskTypeTagTextColor }"
        >
          {{ blueprint.taskType }}
        </el-tag>
        <el-tag
          v-if="blueprint.isTemplate"
          type="warning"
          class="border-0"
        >
          模板
        </el-tag>
      </div>
    </div>

    <div class="space-y-3 mb-6 flex-1">
      <div class="flex items-start space-x-3">
        <Icon icon="mdi:target" class="text-blue-500 text-lg mt-0.5 shrink-0" />
        <div class="flex-1">
          <p class="text-sm text-gray-500 mb-1">任务目标</p>
          <p class="text-sm font-medium text-gray-900 line-clamp-2">{{ blueprint.taskGoal }}</p>
        </div>
      </div>

      <div class="flex items-start space-x-3">
        <Icon icon="mdi:server-network" class="text-green-500 text-lg mt-0.5 shrink-0" />
        <div class="flex-1">
          <p class="text-sm text-gray-500 mb-1">资源分配</p>
          <p class="text-sm font-medium text-gray-900">{{ blueprint.resourceAllocation }}</p>
        </div>
      </div>

      <div class="flex items-start space-x-3">
        <Icon icon="mdi:format-list-numbered" class="text-purple-500 text-lg mt-0.5 shrink-0" />
        <div class="flex-1">
          <p class="text-sm text-gray-500 mb-1">行动步骤</p>
          <div class="flex items-center flex-wrap gap-2 text-sm font-medium text-gray-900">
            <span>{{ blueprint.branchCount }} 个分支，共{{ blueprint.stepCount }} 个步骤</span>
            <div
              class="text-blue-500 cursor-pointer hover:text-blue-600 transition-colors"
              @click.stop="emit('view')"
            >
              查看
            </div>
          </div>
        </div>
      </div>

      <div class="flex items-start space-x-3">
        <Icon icon="mdi:calendar-clock" class="text-amber-500 text-lg mt-0.5 shrink-0" />
        <div class="flex-1">
          <p class="text-sm text-gray-500 mb-1">执行期限</p>
          <p class="text-sm font-medium text-gray-900">{{ blueprint.executionDeadline }}</p>
        </div>
      </div>
    </div>

    <div class="pt-4 border-t border-gray-200 flex flex-col gap-2 mt-auto">
      <div class="flex flex-wrap items-center justify-center gap-2 pb-1">
        <el-tooltip
          v-if="hasPerm(PERM.operations.action.blueprint.update)"
          content="编辑：修改蓝图配置与流程"
          placement="top"
          :show-after="250"
        >
          <el-button
            plain
            circle
            size="small"
            class="ml-0!"
            aria-label="编辑蓝图"
            @click="emit('edit')"
          >
            <Icon icon="mdi:pencil-outline" class="text-base" />
          </el-button>
        </el-tooltip>
        <el-tooltip
          v-if="hasPerm(PERM.operations.action.blueprint.publish)"
          content="发布：生成不可变的蓝图版本"
          placement="top"
          :show-after="250"
        >
          <el-button
            plain
            circle
            size="small"
            class="ml-0!"
            aria-label="发布不可变版本"
            @click="emit('publish')"
          >
            <Icon icon="mdi:tag-arrow-up-outline" class="text-base" />
          </el-button>
        </el-tooltip>
        <el-tooltip
          v-if="canEncapsulate"
          content="封装：将蓝图封装为节点"
          placement="top"
          :show-after="250"
        >
          <el-button
            plain
            circle
            size="small"
            class="ml-0!"
            aria-label="封装为节点"
            @click="emit('encapsulate')"
          >
            <Icon icon="mdi:package-variant-closed" class="text-base" />
          </el-button>
        </el-tooltip>
        <el-tooltip
          content="历史：查看已发布的不可变版本"
          placement="top"
          :show-after="250"
        >
          <el-button
            plain
            circle
            size="small"
            class="ml-0!"
            aria-label="查看发布历史"
            @click="emit('history')"
          >
            <Icon icon="mdi:history" class="text-base" />
          </el-button>
        </el-tooltip>
        <el-tooltip
          content="分支：从当前蓝图创建新分支"
          placement="top"
          :show-after="250"
        >
          <el-button
            plain
            circle
            size="small"
            class="ml-0!"
            aria-label="从此蓝图创建分支"
            @click="emit('branch')"
          >
            <Icon icon="mdi:source-branch" class="text-base" />
          </el-button>
        </el-tooltip>
      </div>
      <BlueprintRunControl
        :disabled="disabled"
        :scheduling-mode="blueprint.defaultSchedulingMode"
        @run="emit('run', $event)"
        @debug="emit('debug', $event)"
      />
      <el-button
        v-if="hasPerm(PERM.operations.action.blueprint.delete)"
        plain
        class="w-full ml-0! text-red-500! border-red-500!"
        @click="emit('delete')"
      >
        <template #icon><Icon icon="mdi:delete-outline" /></template>
        删除该蓝图
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import BlueprintRunControl from '@/components/action/BlueprintRunControl.vue'
import BlueprintPinButton from '@/components/action/BlueprintPinButton.vue'
import { PERM } from '@/utils/permissions'
import { hasAll, hasPerm } from '@/utils/permissionKit'

defineOptions({ name: 'ActionBlueprintCard' })

defineProps({
  blueprint: {
    type: Object,
    required: true
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

const canEncapsulate = computed(() => hasAll([
  PERM.operations.action.blueprint.read,
  PERM.operations.action.blueprint.publish,
  PERM.operations.action.node.create
]))

const emit = defineEmits([
  'pin-change',
  'view',
  'edit',
  'publish',
  'encapsulate',
  'history',
  'branch',
  'run',
  'debug',
  'delete'
])
</script>
