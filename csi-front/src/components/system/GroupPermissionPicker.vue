<template>
  <div class="w-full bg-white rounded-xl border border-gray-200 shadow-sm">
    <div class="px-5 py-4 border-b border-gray-100 flex items-start justify-between gap-4">
      <div class="min-w-0">
        <div class="text-sm font-bold text-gray-900">权限分配</div>
        <div class="text-xs text-gray-500 mt-1">左侧树形目录直接勾选权限码，右侧展示已选明细。</div>
      </div>
      <div class="flex items-center gap-3 shrink-0">
        <el-select v-model="category" clearable placeholder="分类" class="w-40!" :disabled="disabled">
          <el-option v-for="c in categoryOptions" :key="c" :label="c" :value="c" />
        </el-select>
        <el-input v-model="searchKeyword" placeholder="搜索权限（名称/权限码）" clearable class="w-72!" :disabled="disabled">
          <template #prefix>
            <Icon icon="mdi:magnify" class="text-gray-400" />
          </template>
        </el-input>
      </div>
    </div>

    <div class="flex min-w-0">
      <div class="w-90 shrink-0 border-r border-gray-100 p-4">
        <div class="flex items-center justify-between mb-3">
          <div class="text-sm font-medium text-gray-700">权限目录</div>
          <div class="text-xs text-gray-400">共 {{ catalogStats.totalPerms }} 个权限码</div>
        </div>

        <div class="rounded-lg border border-gray-100 bg-white">
          <el-tree
            ref="treeRef"
            :data="filteredCatalogTree"
            node-key="key"
            :props="treeProps"
            :default-expand-all="false"
            :highlight-current="true"
            :expand-on-click-node="true"
            :filter-node-method="filterTreeNode"
            @current-change="handleCurrentNodeChange"
            @check="handleTreeCheck"
            show-checkbox
            check-on-click-node
            :check-strictly="false"
            :disabled="disabled"
            class="perm-tree"
          >
            <template #default="{ data }">
              <div class="min-w-0">
                <div class="flex items-center gap-2 min-w-0">
                  <Icon :icon="data.icon || 'mdi:key-outline'" class="text-gray-400 shrink-0" />
                  <span class="text-sm text-gray-800 truncate">{{ data.label }}</span>
                </div>
                <div v-if="treeNodeCode(data)" class="text-[11px] text-gray-400 font-mono truncate mt-0.5">
                  {{ treeNodeCode(data) }}
                </div>
              </div>
            </template>
          </el-tree>
        </div>

        <div v-if="searchEmptyHint" class="mt-3 text-xs text-gray-500">
          {{ searchEmptyHint }}
        </div>
      </div>

      <div class="flex-1 min-w-0 p-4">
        <div class="flex items-start justify-between gap-4 mb-3">
          <div class="min-w-0">
            <div class="text-sm font-medium text-gray-700">当前节点</div>
            <div class="text-xs text-gray-500 mt-1 truncate">
              <span class="font-medium text-gray-800">{{ currentNodeTitle }}</span>
              <span class="ml-2 text-gray-400">{{ currentNodeSubTitle }}</span>
            </div>
          </div>
          <div class="text-xs text-gray-500 shrink-0">
            已选权限：<span class="font-medium text-gray-800">{{ selectedKnownCount }}</span>
          </div>
        </div>

        <div v-if="hasWildcard" class="rounded-lg border border-blue-100 bg-blue-50/40 p-4 text-xs text-blue-700 mb-3">
          当前权限组为最高等级权限组，暂不支持编辑。
        </div>

        <div v-if="catalogStats.missingPerms.length > 0" class="rounded-lg border border-amber-100 bg-amber-50/60 p-3 text-xs text-amber-700 mb-3">
          检测到 {{ catalogStats.missingPerms.length }} 个权限码未在目录中定义：{{ catalogStats.missingPerms.slice(0, 3).join('、') }}<span v-if="catalogStats.missingPerms.length > 3"> 等</span>
        </div>

        <div class="flex items-center justify-between mb-3">
          <div class="text-xs text-gray-500">
            <template v-if="currentNodePermKeys.length > 0">
              当前节点包含 {{ currentNodePermKeys.length }} 个权限码，可在左侧直接勾选
            </template>
            <template v-else>
              请选择树形目录中的模块或权限码查看详情
            </template>
          </div>
          <el-button size="small" text :disabled="disabled || hasWildcard || selectedRows.length === 0" @click="clearAllSelected">清空已选</el-button>
        </div>

        <div class="rounded-lg border border-gray-100 overflow-hidden">
          <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <div class="text-sm font-medium text-gray-700">已选权限码</div>
            <div class="text-xs text-gray-500">共 {{ selectedRows.length }} 项</div>
          </div>
          <el-table :data="selectedRows" size="small" max-height="360" empty-text="暂无已选权限码" style="width: 100%">
            <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="permKey" label="权限码" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="font-mono text-xs text-gray-600">{{ row.permKey }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="category" label="分类" min-width="130" show-overflow-tooltip />
            <el-table-column label="操作" width="76" fixed="right">
              <template #default="{ row }">
                <el-button type="danger" link :disabled="disabled || hasWildcard" @click="removeSinglePerm(row.permKey)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'

defineOptions({ name: 'GroupPermissionPicker' })

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  },
  permCodes: {
    type: Array,
    default: () => []
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])

const treeProps = {
  label: 'label',
  children: 'children'
}

function treeNodeCode(data) {
  return data?.perm?.permKey || data?.permKey || ''
}

function normalizePerm(item) {
  return {
    permKey: item?.permKey || '',
    name: item?.name || item?.permKey || '',
    desc: item?.desc || '',
    tags: Array.isArray(item?.tags) ? item.tags : [],
    category: item?.category || '',
    enabled: Boolean(item?.enabled)
  }
}

function createCategoryNode(pathParts) {
  const cleanParts = pathParts.filter(Boolean)
  return {
    key: `category:${cleanParts.join('/')}`,
    label: cleanParts[cleanParts.length - 1] || '未分类',
    icon: 'mdi:folder-outline',
    children: [],
    childrenMap: {}
  }
}

function buildCatalogTree(perms) {
  const roots = []
  const rootMap = {}
  for (const raw of perms || []) {
    const perm = normalizePerm(raw)
    if (!perm.permKey) continue
    const parts = String(perm.category || '').split('/').map(s => s.trim()).filter(Boolean)
    const categoryParts = parts.length > 0 ? parts : ['未分类']

    const rootKey = categoryParts[0]
    if (!rootMap[rootKey]) {
      const rootNode = createCategoryNode([rootKey])
      rootMap[rootKey] = rootNode
      roots.push(rootNode)
    }

    let cursor = rootMap[rootKey]
    for (let i = 1; i < categoryParts.length; i += 1) {
      const path = categoryParts.slice(0, i + 1)
      const key = path.join('/')
      if (!cursor.childrenMap[key]) {
        const childNode = createCategoryNode(path)
        cursor.childrenMap[key] = childNode
        cursor.children.push(childNode)
      }
      cursor = cursor.childrenMap[key]
    }

    cursor.children.push({
      key: perm.permKey,
      label: perm.name || perm.permKey,
      icon: 'mdi:key-outline',
      perm
    })
  }

  function finalize(nodes) {
    return (nodes || [])
      .map(node => {
        const children = finalize(node.children || [])
        return {
          key: node.key,
          label: node.label,
          icon: node.icon,
          perm: node.perm,
          children
        }
      })
      .sort((a, b) => String(a.label || '').localeCompare(String(b.label || '')))
  }

  return finalize(roots)
}

function flattenPerms(nodes) {
  const list = []
  const stack = Array.isArray(nodes) ? [...nodes] : []
  while (stack.length > 0) {
    const node = stack.shift()
    if (!node) continue
    if (node.perm && node.perm.permKey) list.push(node.perm)
    if (Array.isArray(node.children) && node.children.length > 0) stack.push(...node.children)
  }
  return list
}

function collectNodePermKeys(node) {
  if (!node) return []
  const set = new Set()
  if (node.perm?.permKey) set.add(node.perm.permKey)
  for (const p of flattenPerms(node.children || [])) {
    if (p?.permKey) set.add(p.permKey)
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b))
}

function filterTreeByCategory(nodes, cat) {
  if (!cat) return nodes
  const out = []
  for (const n of nodes || []) {
    const children = Array.isArray(n.children) ? filterTreeByCategory(n.children, cat) : []
    const nodeCat = String(n?.perm?.category || '').trim()
    const hit = nodeCat === cat || nodeCat.startsWith(`${cat}/`)
    if (children.length > 0 || hit) {
      out.push({ ...n, children })
    }
  }
  return out
}

const category = ref('')
const searchKeyword = ref('')
const treeRef = ref(null)
const currentNode = ref(null)

const catalogTree = computed(() => buildCatalogTree(props.permCodes))
const filteredCatalogTree = computed(() => filterTreeByCategory(catalogTree.value, category.value))
const sourcePerms = computed(() => flattenPerms(catalogTree.value))
const allPerms = computed(() => flattenPerms(filteredCatalogTree.value))

const permMetaByKey = computed(() => {
  const map = {}
  for (const p of sourcePerms.value) map[p.permKey] = p
  return map
})

const hasWildcard = computed(() => Array.isArray(props.modelValue) && props.modelValue.includes('*'))
const selectedUnknownPerms = computed(() => {
  const list = []
  for (const code of props.modelValue || []) {
    if (!code || code === '*') continue
    if (!permMetaByKey.value[code]) list.push(code)
  }
  return Array.from(new Set(list)).sort((a, b) => a.localeCompare(b))
})

const selectedKnownPermKeys = computed(() => {
  const list = []
  for (const code of props.modelValue || []) {
    if (permMetaByKey.value[code]) list.push(code)
  }
  return Array.from(new Set(list)).sort((a, b) => a.localeCompare(b))
})
const selectedKnownCount = computed(() => selectedKnownPermKeys.value.length)
const selectedRows = computed(() =>
  selectedKnownPermKeys.value
    .map(key => permMetaByKey.value[key])
    .filter(Boolean)
    .sort((a, b) => String(a.permKey || '').localeCompare(String(b.permKey || '')))
)

const catalogStats = computed(() => ({
  totalPerms: allPerms.value.length,
  missingPerms: selectedUnknownPerms.value
}))

function filterTreeNode(keyword, data) {
  if (!keyword) return true
  const k = String(keyword).trim().toLowerCase()
  if (!k) return true
  const label = String(data?.label || '').toLowerCase()
  const code = String(treeNodeCode(data) || '').toLowerCase()
  return label.includes(k) || code.includes(k)
}

watch(searchKeyword, (val) => {
  treeRef.value?.filter?.(val)
})

watch(category, () => {
  treeRef.value?.setCurrentKey?.(null)
  currentNode.value = null
  treeRef.value?.filter?.(searchKeyword.value)
})

const categoryOptions = computed(() => {
  const set = new Set()
  for (const p of sourcePerms.value) {
    const c = String(p?.category || '').trim()
    if (c) set.add(c.split('/')[0])
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b))
})

const searchEmptyHint = computed(() => {
  const k = String(searchKeyword.value || '').trim()
  if (!k) return ''
  return `未找到与“${k}”匹配的权限节点`
})

function handleCurrentNodeChange(node) {
  currentNode.value = node || null
}

const currentNodePermKeys = computed(() => collectNodePermKeys(currentNode.value))

const currentNodeTitle = computed(() => {
  if (!currentNode.value) return '未选择'
  return currentNode.value.label || '未命名节点'
})

const currentNodeSubTitle = computed(() => {
  if (!currentNode.value) return '请在左侧选择一个模块或权限码'
  const code = currentNode.value.perm?.permKey || currentNode.value.permKey
  if (code) return code
  return '该模块下的权限码列表'
})

function emitPermissions(nextKnownPermKeys) {
  const next = Array.from(new Set([...(nextKnownPermKeys || []), ...selectedUnknownPerms.value])).sort((a, b) => a.localeCompare(b))
  emit('update:modelValue', next)
}

function syncTreeCheckedKeys() {
  if (!treeRef.value?.setCheckedKeys) return
  treeRef.value.setCheckedKeys(selectedKnownPermKeys.value, false)
}

watch([sourcePerms, selectedKnownPermKeys], () => {
  syncTreeCheckedKeys()
}, { immediate: true })

function handleTreeCheck(_node, checkedInfo) {
  if (props.disabled) return
  if (hasWildcard.value) return
  const checkedKeys = Array.isArray(checkedInfo?.checkedKeys) ? checkedInfo.checkedKeys : []
  const nextPermKeys = checkedKeys.filter(key => typeof key === 'string' && Boolean(permMetaByKey.value[key]))
  emitPermissions(nextPermKeys)
}

function removeSinglePerm(permKey) {
  if (props.disabled) return
  if (hasWildcard.value) return
  const next = selectedKnownPermKeys.value.filter(key => key !== permKey)
  emitPermissions(next)
}

function clearAllSelected() {
  if (props.disabled) return
  if (hasWildcard.value) return
  emitPermissions([])
}
</script>

<style scoped>
.perm-tree {
  padding: 6px 0;
}

.perm-tree :deep(.el-tree-node__content) {
  height: auto;
  align-items: flex-start;
  padding-top: 8px;
  padding-bottom: 8px;
}

.perm-tree :deep(.el-tree-node__content:hover) {
  background-color: rgba(59, 130, 246, 0.06);
}

.perm-tree :deep(.el-tree-node.is-current > .el-tree-node__content) {
  background-color: rgba(59, 130, 246, 0.10);
}

.perm-tree :deep(.el-tree-node__expand-icon) {
  margin-top: 2px;
}

.perm-tree :deep(.el-tree-node__label) {
  width: 100%;
  white-space: normal;
  line-height: 1.25;
}

.perm-tree :deep(.el-checkbox) {
  margin-right: 8px;
}

</style>
