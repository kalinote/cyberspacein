<template>
  <el-dialog :model-value="modelValue" :title="title" width="660px" @update:model-value="$emit('update:modelValue', $event)">
    <div class="flex gap-3 mb-4"><el-input v-model="query" clearable placeholder="搜索证据链" aria-label="搜索引用证据链" @keyup.enter="page = 1; load()" /><el-button @click="page = 1; load()">搜索</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" class="mb-3" />
    <div v-loading="loading" class="min-h-40 max-h-96 overflow-auto">
      <button v-for="chain in items" :key="chain.id" :disabled="chain.id === excludeId || busy" class="w-full text-left p-4 mb-2 rounded-lg border border-gray-200 hover:border-blue-400 disabled:opacity-40" @click="$emit('select', chain)"><div class="font-medium">{{ chain.title }} <span v-if="chain.id === excludeId" class="text-xs">（当前证据链）</span></div><p class="text-xs text-gray-500 mt-2">{{ chain.node_count }} 个节点 · {{ chain.edge_count }} 条关系 · {{ chain.purpose || '未填写目的' }}</p></button>
      <el-empty v-if="!items.length && !loading && !error" description="暂无可选证据链" :image-size="60" />
    </div>
    <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="prev, pager, next" class="mt-4 justify-center" @current-change="load" />
    <template #footer><slot name="footer" /><el-button @click="$emit('update:modelValue', false)">取消</el-button></template>
  </el-dialog>
</template>
<script setup>
import { ref, watch } from 'vue';
import { evidenceApi } from '@/api/evidence';
const props = defineProps({
  modelValue: Boolean,
  title: {
    type: String,
    default: '引用已有子链'
  },
  excludeId: {
    type: String,
    default: ''
  },
  busy: Boolean
});
defineEmits(['update:modelValue', 'select']);
const query = ref(''),
  items = ref([]),
  page = ref(1),
  total = ref(0),
  loading = ref(false),
  error = ref('');
let sequence = 0;
async function load() {
  const id = ++sequence;
  loading.value = true;
  error.value = '';
  try {
    const response = await evidenceApi.list({
      q: query.value,
      page: page.value,
      page_size: 10
    });
    if (id === sequence) {
      items.value = response.data.items;
      total.value = response.data.total;
    }
  } catch (e) {
    if (id === sequence) error.value = e.message;
  } finally {
    if (id === sequence) loading.value = false;
  }
}
watch(() => props.modelValue, value => {
  if (value) {
    page.value = 1;
    load();
  } else ++sequence;
});
</script>
