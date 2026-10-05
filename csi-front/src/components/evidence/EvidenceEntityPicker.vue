<template>
  <el-dialog :model-value="modelValue" title="添加实体与版本" width="900px" destroy-on-close @update:model-value="$emit('update:modelValue', $event)">
    <template v-if="!versionNode">
      <div class="flex gap-3 flex-wrap mb-4">
        <el-select v-model="source" style="width: 160px" aria-label="实体来源" @change="page = 1; selected = {}; load()"><el-option label="全部实体" value="all" /><el-option label="重点实体库" value="highlights" /><el-option label="专题事件" value="wiki" /></el-select>
        <el-input v-model="query" placeholder="输入关键词检索" class="flex-1" clearable aria-label="实体关键词" @keyup.enter="page = 1; load()" />
        <el-button type="primary" @click="page = 1; load()">检索</el-button>
      </div>
      <div v-if="source !== 'wiki'" class="flex gap-3 items-center mb-3 text-xs text-gray-500"><span>实体类型</span><el-radio-group v-model="entityType" size="small" @change="page = 1; load()"><el-radio-button value="">全部</el-radio-button><el-radio-button value="article">文章</el-radio-button><el-radio-button value="forum">帖子 / 评论</el-radio-button></el-radio-group></div>
      <el-alert v-if="error" :title="error" type="error" :closable="false" class="mb-3" />
      <div v-loading="loading" class="min-h-60 max-h-100 overflow-auto border border-gray-200 rounded-lg">
        <div v-for="item in items" :key="keyOf(item)" class="flex gap-3 p-4 border-b border-gray-100 items-start">
          <el-checkbox :model-value="Boolean(selected[keyOf(item)])" :aria-label="`选择${plainEntityTitle(item.title)}`" @change="toggleSelected(item, $event)" />
          <div class="min-w-0 flex-1"><p class="font-medium text-gray-800">{{ plainEntityTitle(item.title) }}</p><p class="text-xs text-gray-400 mt-1">{{ item.entity_type }} · {{ item.platform || '专题事件' }} · {{ item.last_edit_at || item.update_at || '时间未提供' }}</p><p class="text-xs text-gray-500 line-clamp-2 mt-2">{{ plainEntityTitle(item.clean_content || item.sourceNote || '暂无摘要') }}</p></div>
          <el-button v-if="item.entity_type !== 'wiki'" link type="primary" @click="openVersions(item)">选择版本</el-button>
        </div>
        <el-empty v-if="!items.length && !loading && !error" description="暂无结果，请调整关键词或来源" :image-size="60" />
      </div>
      <div class="mt-4 flex items-center justify-between gap-3"><span class="text-sm text-gray-500">已选择 {{ Object.keys(selected).length }} 个实体</span><el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="prev, pager, next" @current-change="load" /></div>
    </template>
    <template v-else>
      <el-button link type="primary" @click="versionNode = null">← 返回实体选择</el-button>
      <h3 class="font-semibold mt-4">{{ versionNode.label }}</h3><p class="text-xs text-gray-400 mt-2">{{ versionNode.version_source.platform }} · 原始数据 {{ versionNode.version_source.source_id }}</p>
      <el-radio-group v-model="versionMode" class="my-5"><el-radio v-if="allowDynamic" value="dynamic">全部版本（包含未来版本）</el-radio><el-radio value="selected">选择指定版本</el-radio></el-radio-group>
      <el-alert v-if="versionMode === 'dynamic'" title="保存此数据的引用规则，每次读取时检索全部版本。" type="info" :closable="false" class="mb-3" />
      <el-alert v-if="error" :title="error" type="error" :closable="false" class="mb-3" />
      <div v-loading="loading" class="max-h-80 overflow-auto border border-gray-200 rounded-lg">
        <div v-for="item in versions" :key="item.uuid" class="flex gap-3 p-4 border-b border-gray-100">
          <el-checkbox v-if="versionMode === 'selected'" :model-value="Boolean(versionSelection[keyOf(item)])" :aria-label="`选择版本${item.uuid}`" @change="toggleVersion(item, $event)" />
          <div class="min-w-0"><p class="text-xs text-blue-600 mb-1">采集：{{ item.crawled_at || '未知' }} · 编辑：{{ item.last_edit_at || '未知' }}</p><p class="font-medium">{{ plainEntityTitle(item.title) }}</p><p class="text-xs text-gray-500 mt-1 line-clamp-2">{{ item.clean_content }}</p><p class="text-xs text-gray-400 mt-1">{{ item.uuid }}</p></div>
        </div>
        <el-empty v-if="!versions.length && !loading" description="当前未检索到版本" :image-size="50" />
      </div>
      <div class="mt-3 flex justify-between text-xs text-gray-500"><span>共 {{ versionTotal }} 个版本 · 已选 {{ Object.keys(versionSelection).length }} 个</span><el-pagination v-model:current-page="versionPage" :page-size="20" :total="versionTotal" layout="prev, pager, next" @current-change="loadVersions" /></div>
    </template>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <template v-if="!versionNode"><el-button :disabled="!Object.keys(selected).length" @click="addSelection('collection')">组成固定集合</el-button><el-button type="primary" :disabled="!Object.keys(selected).length" @click="addSelection('entity')">添加独立节点</el-button></template>
      <template v-else><el-button v-if="versionMode === 'selected'" :disabled="!Object.keys(versionSelection).length" @click="addVersions('entity')">作为独立节点</el-button><el-button type="primary" :disabled="loading || (versionMode === 'selected' && !Object.keys(versionSelection).length)" @click="addVersions('collection')">{{ versionMode === 'dynamic' ? '添加动态版本节点' : '添加固定版本集合' }}</el-button></template>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { searchApi } from '@/api/search';
import { wikiApi } from '@/api/wiki';
import { evidenceApi } from '@/api/evidence';
import { makeEvidenceNode, plainEntityTitle } from '@/utils/evidence';
const props = defineProps({
  modelValue: Boolean,
  allowDynamic: {
    type: Boolean,
    default: true
  },
  initialEntity: {
    type: Object,
    default: null
  }
});
const emit = defineEmits(['update:modelValue', 'add']);
const query = ref(''),
  source = ref('all'),
  entityType = ref(''),
  page = ref(1),
  items = ref([]),
  total = ref(0),
  selected = ref({}),
  loading = ref(false),
  error = ref('');
const versionNode = ref(null),
  versionMode = ref('dynamic'),
  versions = ref([]),
  versionPage = ref(1),
  versionTotal = ref(0),
  versionSelection = ref({});
let requestId = 0;
function keyOf(item) {
  return `${item.entity_type}:${item.uuid}`;
}
function toggleSelected(item, enabled) {
  if (enabled) selected.value[keyOf(item)] = item;else delete selected.value[keyOf(item)];
}
function toggleVersion(item, enabled) {
  if (enabled) versionSelection.value[keyOf(item)] = item;else delete versionSelection.value[keyOf(item)];
}
async function load() {
  const id = ++requestId;
  loading.value = true;
  error.value = '';
  try {
    const response = source.value === 'wiki' ? await wikiApi.listPages({
      q: query.value,
      page: page.value,
      page_size: 10
    }) : await searchApi.searchEntity({
      keywords: query.value.trim() || undefined,
      search_mode: 'keyword',
      entity_type: entityType.value ? [entityType.value] : undefined,
      is_highlighted: source.value === 'highlights' ? true : undefined,
      page: page.value,
      page_size: 10,
      sort_by: query.value.trim() ? 'relevance' : 'crawled_at',
      sort_order: 'desc'
    });
    const data = response.data || response;
    if (id !== requestId) return;
    items.value = source.value === 'wiki' ? data.items.map(item => ({
      ...item,
      entity_type: 'wiki',
      uuid: item.id
    })) : data.items;
    total.value = data.total;
  } catch (e) {
    if (id === requestId) {
      error.value = e.message;
      items.value = [];
    }
  } finally {
    if (id === requestId) loading.value = false;
  }
}
async function openVersions(item) {
  const id = ++requestId;
  loading.value = true;
  error.value = '';
  try {
    const node = makeEvidenceNode('entity', {
      entity: {
        entity_type: item.entity_type,
        uuid: item.uuid
      },
      label: plainEntityTitle(item.title)
    });
    const response = await evidenceApi.resolve(node);
    if (id !== requestId) return;
    const entity = response.data.items[0];
    if (!entity.source_id || !entity.platform) {
      ElMessage.warning('该实体缺少来源平台或原始数据标识，无法确定版本范围');
      return;
    }
    versionNode.value = makeEvidenceNode('versions', {
      label: plainEntityTitle(entity.title),
      version_source: {
        entity_type: entity.entity_type,
        source_id: entity.source_id,
        platform: entity.platform
      }
    });
    versionPage.value = 1;
    versionMode.value = props.allowDynamic ? 'dynamic' : 'selected';
    versionSelection.value = {};
    versions.value = [];
    await loadVersions();
  } catch (e) {
    if (id === requestId) error.value = e.message;
  } finally {
    if (id === requestId) loading.value = false;
  }
}
async function loadVersions() {
  const id = ++requestId;
  loading.value = true;
  error.value = '';
  try {
    const response = await evidenceApi.resolve(versionNode.value, versionPage.value, 20);
    if (id === requestId) {
      versions.value = response.data.items;
      versionTotal.value = response.data.total;
    }
  } catch (e) {
    if (id === requestId) error.value = e.message;
  } finally {
    if (id === requestId) loading.value = false;
  }
}
function nodesFromSelection(selection, kind, label = '') {
  const entries = Object.values(selection);
  const refs = entries.map(item => ({
    entity_type: item.entity_type,
    uuid: item.uuid
  }));
  return kind === 'collection' ? [makeEvidenceNode('collection', {
    label: label || `${plainEntityTitle(entries[0].title).slice(0, 260)} · 集合`,
    members: refs
  })] : entries.map((item, index) => makeEvidenceNode('entity', {
    label: plainEntityTitle(item.title),
    entity: refs[index]
  }));
}
function addSelection(kind) {
  emit('add', nodesFromSelection(selected.value, kind));
  emit('update:modelValue', false);
}
function addVersions(kind) {
  emit('add', versionMode.value === 'dynamic' ? [versionNode.value] : nodesFromSelection(versionSelection.value, kind, `${versionNode.value.label.slice(0, 270)} · 指定版本`));
  emit('update:modelValue', false);
}
watch(() => props.modelValue, async value => {
  ++requestId;
  if (!value) return;
  selected.value = {};
  versionNode.value = null;
  error.value = '';
  source.value = 'all';
  query.value = '';
  page.value = 1;
  if (props.initialEntity) {
    const entity = props.initialEntity;
    items.value = [entity];
    total.value = 1;
    selected.value[keyOf(entity)] = entity;
    loading.value = false;
  } else await load();
});
</script>
