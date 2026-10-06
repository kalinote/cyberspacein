<template>
  <div class="min-h-screen bg-linear-to-b from-white to-gray-50">
    <Header />
    <section class="bg-linear-to-br from-blue-50 to-white py-12">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div class="lg:col-span-2">
            <h1 class="text-4xl font-bold text-gray-900 mb-4"><span class="text-blue-500">证据链</span>分析中心</h1>
            <p class="text-gray-600 text-lg mb-6">将分散的实体、版本与分析线索组织成关系图谱。为每一条联系记录依据，让事件的发展与信息之间的关联清晰可查。</p>
            <div class="flex flex-wrap gap-4" v-loading="loading">
              <div v-for="item in statItems" :key="item.key" class="bg-white rounded-xl p-4 shadow-sm border border-blue-100 flex items-center space-x-3">
                <div class="w-10 h-10 rounded-lg flex items-center justify-center" :class="item.iconClass">
                  <Icon :icon="item.icon" class="text-xl" />
                </div>
                <div>
                  <p class="text-sm text-gray-500">{{ item.label }}</p>
                  <p class="text-xl font-bold text-gray-900">{{ stats ? stats[item.key] : '—' }}</p>
                </div>
              </div>
            </div>
          </div>
          <div class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">快速构建证据链</h3>
            <div class="space-y-4">
              <button data-evidence-tour="create" type="button" :disabled="!canCreate" class="w-full bg-blue-500 text-white py-3 rounded-lg font-medium hover:opacity-90 transition-opacity flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed" @click="openCreate('blank')">
                <Icon icon="mdi:plus" /><span>新建证据链</span>
              </button>
              <button data-evidence-tour="manage" type="button" class="w-full border-2 border-blue-200 text-blue-600 py-3 rounded-lg font-medium hover:bg-blue-50 transition-colors flex items-center justify-center space-x-2" @click="router.push('/evidence/chains')">
                <Icon icon="mdi:graph-outline" /><span>管理证据链</span>
              </button>
              <div class="evidence-home-guide"><EvidenceUsageTour :steps="tourSteps" size="large" /></div>
            </div>
          </div>
        </div>
      </div>
    </section>
    <main>
      <div v-if="error" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        <el-alert :title="error" type="error" show-icon :closable="false">
          <el-button link type="primary" @click="load">重新加载</el-button>
        </el-alert>
      </div>

      <section class="py-12 bg-linear-to-b from-white to-gray-50" aria-labelledby="evidence-templates-title">
        <div data-evidence-tour="templates" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div class="mb-8">
            <h2 id="evidence-templates-title" class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
              <Icon icon="mdi:shape-outline" class="text-blue-600 text-2xl" />
              <span><span class="text-blue-500">分析</span>场景</span>
            </h2>
            <p class="text-sm text-gray-500 mt-2">从分析目的出发，选择合适的起始结构。</p>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <button
              v-for="item in EVIDENCE_TEMPLATES"
              :key="item.id"
              type="button"
              :disabled="!canCreate"
              class="flex flex-col items-start text-left bg-white rounded-2xl p-6 shadow-sm border border-blue-100 hover:border-blue-300 hover:shadow-lg transition-all focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              @click="openCreate(item.id)"
            >
              <div class="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center mb-5">
                <Icon :icon="item.icon" class="text-2xl text-blue-600" />
              </div>
              <h3 class="text-lg font-bold text-gray-900 mb-2">{{ item.name }}</h3>
              <p class="text-sm text-gray-500 leading-6">{{ item.description }}</p>
            </button>
          </div>
        </div>
      </section>

      <section class="py-12 bg-white border-y border-gray-100" aria-labelledby="evidence-recent-title">
        <div data-evidence-tour="recent" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div class="flex flex-wrap items-center justify-between gap-4 mb-8">
            <div>
              <h2 id="evidence-recent-title" class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
                <Icon icon="mdi:history" class="text-blue-600 text-2xl" />
                <span><span class="text-blue-500">最近</span>编辑</span>
              </h2>
              <p class="text-sm text-gray-500 mt-2">继续整理已有线索，查看和完善最近编辑的证据链。</p>
            </div>
            <router-link to="/evidence/chains" class="inline-flex shrink-0 items-center gap-2 py-2 text-sm font-medium text-blue-600 hover:text-blue-500 transition-colors">
              查看全部<Icon icon="mdi:arrow-right" />
            </router-link>
          </div>
          <div v-loading="loading" element-loading-text="正在加载证据链..." class="min-h-52">
            <div v-if="stats?.recent.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <router-link
                v-for="chain in stats.recent"
                :key="chain.id"
                :to="`/evidence/chains/${chain.id}`"
                class="min-w-0 bg-white rounded-2xl p-6 shadow-sm border border-blue-100 hover:border-blue-300 hover:shadow-lg transition-all"
              >
                <div class="flex items-center justify-between gap-3 mb-4">
                  <div class="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center">
                    <Icon icon="mdi:graph-outline" class="text-2xl text-blue-600" />
                  </div>
                  <el-tag size="small" :type="chain.status === 'active' ? 'success' : 'info'">{{ CHAIN_STATUS[chain.status] }}</el-tag>
                </div>
                <h3 class="text-lg font-bold text-gray-900 truncate">{{ chain.title }}</h3>
                <p class="text-sm text-gray-500 mt-2 line-clamp-2 h-12 leading-6">{{ chain.purpose || chain.description || '尚未填写分析目的' }}</p>
                <div class="flex flex-wrap gap-x-4 gap-y-2 mt-5 pt-4 border-t border-gray-100 text-xs text-gray-500">
                  <span>{{ chain.node_count }} 个节点</span>
                  <span>{{ chain.edge_count }} 条关系</span>
                  <span>{{ chain.subchain_count }} 条子链</span>
                </div>
              </router-link>
            </div>
            <el-empty v-else-if="!loading && !error" description="还没有证据链，从一个线索开始构建" class="bg-gray-50 rounded-2xl border border-dashed border-gray-200" />
          </div>
        </div>
      </section>

      <section class="py-12 bg-linear-to-b from-gray-50 to-white" aria-labelledby="evidence-capabilities-title">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div class="mb-8">
            <h2 id="evidence-capabilities-title" class="text-2xl font-bold text-gray-900 flex items-center space-x-2">
              <Icon icon="mdi:graph-outline" class="text-blue-600 text-2xl" />
              <span><span class="text-blue-500">图谱</span>能力</span>
            </h2>
            <p class="text-sm text-gray-500 mt-2">组织分析材料、追踪内容变化，复用已有的关联图谱。</p>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <article class="bg-linear-to-br from-blue-50 to-white rounded-2xl p-6 border border-blue-100 shadow-sm">
              <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center mb-4">
                <Icon icon="mdi:graph-outline" class="text-2xl text-blue-600" />
              </div>
              <h3 class="font-bold text-gray-900 mb-2">实体与虚拟节点</h3>
              <p class="text-sm text-gray-500 leading-6">引用已有数据，也可创建事件、判断或集合来组织分析。</p>
            </article>
            <article class="bg-linear-to-br from-purple-50 to-white rounded-2xl p-6 border border-purple-100 shadow-sm">
              <div class="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center mb-4">
                <Icon icon="mdi:history" class="text-2xl text-purple-600" />
              </div>
              <h3 class="font-bold text-gray-900 mb-2">持续追踪版本</h3>
              <p class="text-sm text-gray-500 leading-6">动态版本节点在读取时检索，自动呈现后来采集的版本。</p>
            </article>
            <article class="bg-linear-to-br from-cyan-50 to-white rounded-2xl p-6 border border-cyan-100 shadow-sm">
              <div class="w-12 h-12 bg-cyan-100 rounded-xl flex items-center justify-center mb-4">
                <Icon icon="mdi:source-branch" class="text-2xl text-cyan-600" />
              </div>
              <h3 class="font-bold text-gray-900 mb-2">组合独立子链</h3>
              <p class="text-sm text-gray-500 leading-6">引用已有证据链，展开查看内容或进入子链继续编辑。</p>
            </article>
          </div>
        </div>
      </section>
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
  icon: 'mdi:graph-outline',
  iconClass: 'bg-blue-100 text-blue-600'
}, {
  key: 'active',
  label: '分析中',
  icon: 'mdi:progress-clock',
  iconClass: 'bg-green-100 text-green-600'
}, {
  key: 'nodes',
  label: '图中节点',
  icon: 'mdi:circle-multiple-outline',
  iconClass: 'bg-amber-100 text-amber-600'
}, {
  key: 'edges',
  label: '已建立关系',
  icon: 'mdi:vector-line',
  iconClass: 'bg-purple-100 text-purple-600'
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

<style scoped>
.evidence-home-guide :deep(.el-button) {
  width: 100%;
  height: auto;
  padding: 12px 16px;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 500;
  line-height: 24px;
  color: #4b5563;
}
.evidence-home-guide :deep(.el-button:hover) {
  background-color: #f9fafb;
}
</style>
