<template>
  <div class="min-h-screen bg-gray-50">
    <Header />
    <section class="bg-linear-to-br from-blue-50 via-white to-indigo-50 py-12 border-b border-blue-100">
      <div class="max-w-7xl mx-auto px-6 grid lg:grid-cols-3 gap-10 items-center">
        <div class="lg:col-span-2">
          <div class="flex items-center gap-2 text-blue-600 text-sm font-medium mb-4"><Icon icon="mdi:graph-outline" class="text-xl" />关联线索 · 验证判断 · 追溯变化</div>
          <h1 class="text-4xl font-bold text-gray-900 mb-4"><span class="text-blue-500">证据链</span>分析中心</h1>
          <p class="text-gray-600 text-lg leading-8 max-w-2xl">将分散的实体、版本与分析线索组织成关系图谱。为每一条联系记录依据，让事件的发展与信息之间的关联清晰可查。</p>
          <div class="flex gap-3 mt-7 flex-wrap">
            <el-button data-evidence-tour="create" type="primary" size="large" :disabled="!canCreate" @click="openCreate('blank')"><Icon icon="mdi:plus" class="mr-2" />新建证据链</el-button>
            <el-button data-evidence-tour="manage" size="large" @click="router.push('/evidence/chains')">管理证据链<Icon icon="mdi:arrow-right" class="ml-2" /></el-button>
            <EvidenceUsageTour :steps="tourSteps" size="large" />
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4" v-loading="loading">
          <div v-for="item in statItems" :key="item.key" class="bg-white border border-blue-100 rounded-xl p-5 shadow-sm">
            <Icon :icon="item.icon" class="text-blue-500 text-xl mb-3" /><div class="text-3xl font-bold text-gray-900">{{ stats ? stats[item.key] : '—' }}</div><div class="text-sm text-gray-500 mt-1">{{ item.label }}</div>
          </div>
        </div>
      </div>
    </section>
    <main class="max-w-7xl mx-auto px-6 py-10 space-y-10">
      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false"><el-button link type="primary" @click="load">重新加载</el-button></el-alert>
      <section data-evidence-tour="templates"><h2 class="text-xl font-bold mb-5">从一个分析场景开始</h2><div class="grid md:grid-cols-4 gap-4">
        <button v-for="item in EVIDENCE_TEMPLATES" :key="item.id" :disabled="!canCreate" class="text-left bg-white border border-gray-200 rounded-xl p-5 hover:border-blue-300 hover:shadow-md transition-all disabled:opacity-50" @click="openCreate(item.id)">
          <Icon :icon="item.icon" class="text-2xl text-blue-500 mb-4" /><h3 class="font-bold mb-2">{{ item.name }}</h3><p class="text-sm text-gray-500 leading-6">{{ item.description }}</p>
        </button>
      </div></section>
      <section data-evidence-tour="recent"><div class="flex items-center justify-between mb-5"><h2 class="text-xl font-bold">最近编辑</h2><router-link to="/evidence/chains" class="text-sm text-blue-600">查看全部 →</router-link></div>
        <div v-if="stats?.recent.length" class="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          <router-link v-for="chain in stats.recent" :key="chain.id" :to="`/evidence/chains/${chain.id}`" class="bg-white rounded-xl p-5 border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all">
            <div class="flex items-center justify-between mb-3"><Icon icon="mdi:graph-outline" class="text-2xl text-blue-500" /><el-tag size="small" :type="chain.status === 'active' ? 'success' : 'info'">{{ CHAIN_STATUS[chain.status] }}</el-tag></div>
            <h3 class="font-semibold text-gray-900 truncate">{{ chain.title }}</h3><p class="text-sm text-gray-500 mt-2 line-clamp-2 h-10">{{ chain.purpose || chain.description || '尚未填写分析目的' }}</p>
            <div class="flex gap-4 mt-5 pt-3 border-t border-gray-100 text-xs text-gray-500"><span>{{ chain.node_count }} 个节点</span><span>{{ chain.edge_count }} 条关系</span><span>{{ chain.subchain_count }} 条子链</span></div>
          </router-link>
        </div>
        <el-empty v-else-if="!loading && !error" description="还没有证据链，从一个线索开始构建" class="bg-white rounded-xl border border-dashed border-gray-200" />
      </section>
      <div class="grid md:grid-cols-3 gap-6 text-sm text-gray-500 pb-4">
        <p><strong class="block text-gray-800 mb-2">实体与虚拟节点</strong>引用已有数据，也可创建事件、判断或集合来组织分析。</p>
        <p><strong class="block text-gray-800 mb-2">持续追踪版本</strong>动态版本节点在读取时检索，自动呈现后来采集的版本。</p>
        <p><strong class="block text-gray-800 mb-2">组合独立子链</strong>引用已有证据链，展开查看内容或进入子链继续编辑。</p>
      </div>
    </main>
    <EvidenceCreateDialog v-model="createVisible" :initial-template="selectedTemplate" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { Icon } from '@iconify/vue';
import Header from '@/components/Header.vue';
import EvidenceCreateDialog from '@/components/evidence/EvidenceCreateDialog.vue';
import EvidenceUsageTour from '@/components/evidence/EvidenceUsageTour.vue';
import { evidenceApi } from '@/api/evidence';
import { EVIDENCE_TEMPLATES, CHAIN_STATUS } from '@/utils/evidence';
import { PERM } from '@/utils/permissions';
import { hasPerm } from '@/utils/permissionKit';
const router = useRouter();
const stats = ref(null);
const loading = ref(false);
const error = ref('');
const createVisible = ref(false);
const selectedTemplate = ref('blank');
const canCreate = computed(() => hasPerm(PERM.operations.evidence.chain.create));
const tourSteps = [{
  title: '1. 创建一条证据链',
  target: '[data-evidence-tour="create"]',
  content: ['填写名称和分析目的，即可开始组织材料。证据链可以围绕用户、事件、一篇文章或任何你关心的问题展开。']
}, {
  title: '2. 从模板开始',
  target: '[data-evidence-tour="templates"]',
  content: ['可选择证明与反证、信息扩展、事件溯源，也可以自由构建。模板提供起始节点与关系，创建后都能继续修改。']
}, {
  title: '3. 管理与查找图谱',
  target: '[data-evidence-tour="manage"]',
  content: ['在管理页按名称、分析目的、标签或状态查找证据链，打开图谱继续编辑。']
}, {
  title: '4. 打开图谱，继续学习操作',
  target: '[data-evidence-tour="recent"]',
  placement: 'top',
  content: ['最近编辑的证据链会显示在这里，点击卡片即可打开。', '图谱编辑页也有“使用引导”，会逐步介绍添加实体、组合子链、建立关系与保存。随时可以重新观看。']
}];
const statItems = [{
  key: 'chains',
  label: '证据链',
  icon: 'mdi:graph-outline'
}, {
  key: 'active',
  label: '分析中',
  icon: 'mdi:progress-clock'
}, {
  key: 'nodes',
  label: '图中节点',
  icon: 'mdi:circle-multiple-outline'
}, {
  key: 'edges',
  label: '已建立关系',
  icon: 'mdi:vector-line'
}];
function openCreate(template) {
  selectedTemplate.value = template;
  createVisible.value = true;
}
async function load() {
  loading.value = true;
  error.value = '';
  try {
    stats.value = (await evidenceApi.overview()).data;
  } catch (e) {
    error.value = e.message || '证据链概览加载失败';
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>
