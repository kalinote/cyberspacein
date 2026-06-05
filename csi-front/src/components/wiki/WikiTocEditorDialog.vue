<template>
  <el-dialog
    v-model="visible"
    title="编辑页面目录"
    width="520px"
    destroy-on-close
    @open="onOpen"
    @closed="onClosed"
  >
    <p class="text-xs text-gray-500 mb-3">
      仅管理正文章节；「注释」「参考资料」由系统自动追加。导语不在此编辑，请在正文区修改。
    </p>
    <div class="flex flex-wrap gap-2 mb-3">
      <el-button size="small" @click="addRootSection">
        <Icon icon="mdi:plus" class="mr-1" />
        添加一级章节
      </el-button>
      <el-button size="small" :disabled="!canAddChild" @click="addChildSection">
        <Icon icon="mdi:subdirectory-arrow-right" class="mr-1" />
        添加子章节
      </el-button>
      <el-button size="small" type="danger" plain :disabled="!selectedNode" @click="removeSelected">
        删除选中
      </el-button>
    </div>
    <div class="rounded-lg border border-gray-200 p-2 max-h-80 overflow-y-auto">
      <el-tree
        ref="treeRef"
        :data="treeData"
        node-key="id"
        :props="{ label: 'label', children: 'children' }"
        highlight-current
        default-expand-all
        @current-change="onCurrentChange"
      >
        <template #default="{ data }">
          <div class="flex items-center gap-2 min-w-0 py-0.5" @click.stop>
            <span
              v-if="data.number"
              class="text-xs font-mono text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded shrink-0 min-w-[1.5rem] text-center"
            >
              {{ data.number }}
            </span>
            <el-input
              v-model="data.title"
              size="small"
              class="min-w-0 flex-1"
              @input="data.label = data.title"
              @click.stop
            />
          </div>
        </template>
      </el-tree>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="handleApply">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  collectSectionIds,
  contentChildrenToTreeNodes,
  createEmptySectionNode,
  syncWikiTocTreeNumbers,
  treeNodesToContentChildren,
} from '@/utils/wikiTree.js'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  /** @type {import('vue').PropType<import('@/utils/wikiContent.js').WikiContentNode[]>} */
  children: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:modelValue', 'apply'])

const visible = ref(props.modelValue)
/** @type {import('vue').Ref<import('@/utils/wikiTree.js').WikiTocTreeNode[]>} */
const treeData = ref([])
/** @type {import('vue').Ref<import('@/utils/wikiTree.js').WikiTocTreeNode|null>} */
const selectedNode = ref(null)
const treeRef = ref(null)

const canAddChild = computed(() => Boolean(selectedNode.value))

watch(
  () => props.modelValue,
  (val) => {
    visible.value = val
  }
)

watch(visible, (val) => {
  emit('update:modelValue', val)
})

function refreshTreeNumbers() {
  syncWikiTocTreeNumbers(treeData.value)
}

function onOpen() {
  treeData.value = contentChildrenToTreeNodes(props.children)
  refreshTreeNumbers()
  selectedNode.value = null
}

function onClosed() {
  treeData.value = []
  selectedNode.value = null
}

function onCurrentChange(data) {
  selectedNode.value = data || null
}

function allSectionIds() {
  const ids = collectSectionIds({ section: 'main', children: treeNodesToContentChildren(treeData.value) })
  return ids
}

function pushEmptySectionNode(title, parent = null) {
  const node = createEmptySectionNode(title, allSectionIds())
  const [treeNode] = contentChildrenToTreeNodes([node])
  if (!treeNode) return
  if (parent) {
    if (!parent.children) parent.children = []
    parent.children.push(treeNode)
  } else {
    treeData.value.push(treeNode)
  }
  refreshTreeNumbers()
}

function addRootSection() {
  pushEmptySectionNode('新章节')
}

function addChildSection() {
  if (!selectedNode.value) return
  const parent = findTreeNode(treeData.value, selectedNode.value.id)
  if (!parent) return
  pushEmptySectionNode('新子章节', parent)
}

/**
 * @param {import('@/utils/wikiTree.js').WikiTocTreeNode[]} nodes
 * @param {string} id
 */
function findTreeNode(nodes, id) {
  for (const node of nodes) {
    if (node.id === id) return node
    if (node.children?.length) {
      const found = findTreeNode(node.children, id)
      if (found) return found
    }
  }
  return null
}

async function removeSelected() {
  if (!selectedNode.value) return
  try {
    await ElMessageBox.confirm(`确定删除章节「${selectedNode.value.title || selectedNode.value.label}」？`, '删除章节', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  removeNodeById(treeData.value, selectedNode.value.id)
  refreshTreeNumbers()
  selectedNode.value = null
}

/**
 * @param {import('@/utils/wikiTree.js').WikiTocTreeNode[]} nodes
 * @param {string} id
 */
function removeNodeById(nodes, id) {
  const idx = nodes.findIndex((n) => n.id === id)
  if (idx >= 0) {
    nodes.splice(idx, 1)
    return true
  }
  for (const node of nodes) {
    if (node.children?.length && removeNodeById(node.children, id)) return true
  }
  return false
}

function handleApply() {
  emit('apply', treeNodesToContentChildren(treeData.value))
  visible.value = false
}
</script>
