<template>
  <div class="h-screen flex flex-col bg-gray-50">
    <Header />

    <FunctionalPageHeader
      title-prefix="分析引擎"
      title-suffix="配置"
      subtitle="管理分析选项、模型资源、提示词模板与工具等配置"
    >
      <template #actions>
        <div class="flex items-center gap-3">
          <div class="bg-white rounded-lg px-4 py-2 shadow-sm border border-blue-100 flex items-center gap-3">
            <Icon icon="mdi:format-list-checks" class="text-blue-600 text-xl" />
            <div>
              <p class="text-xs text-gray-500">分析选项</p>
              <p class="text-lg font-bold text-gray-900">{{ statistics.analysisOptions }}</p>
            </div>
          </div>
          <div class="bg-white rounded-lg px-4 py-2 shadow-sm border border-green-100 flex items-center gap-3">
            <Icon icon="mdi:server" class="text-green-600 text-xl" />
            <div>
              <p class="text-xs text-gray-500">模型资源</p>
              <p class="text-lg font-bold text-gray-900">{{ statistics.modelResources }}</p>
            </div>
          </div>
        </div>
      </template>
    </FunctionalPageHeader>

    <div class="flex-1 flex overflow-hidden">
      <div class="bg-white w-72 border-r border-gray-200 shrink-0 overflow-y-auto">
        <div class="p-4">
          <h3 class="text-sm font-semibold text-gray-500 uppercase mb-3">配置类型</h3>
          <div class="space-y-1">
            <div
              v-for="tab in engineTabs"
              :key="tab.key"
              class="flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer transition-all"
              :class="activeTab === tab.key
                ? 'bg-blue-50 text-blue-600 font-medium shadow-sm border border-blue-200'
                : 'text-gray-600 hover:bg-gray-50'"
              @click="activeTab = tab.key"
            >
              <span class="w-5"></span>
              <Icon :icon="tab.icon" class="text-xl shrink-0" />
              <span>{{ tab.label }}</span>
              <span
                class="ml-auto text-xs px-2 py-0.5 rounded-full"
                :class="activeTab === tab.key ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'"
              >
                {{ getResourceCount(tab.key) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div class="flex-1 flex flex-col overflow-hidden">
        <div class="bg-white px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <Icon :icon="getCurrentTabIcon()" class="text-2xl text-blue-600" />
            <h2 class="text-xl font-bold text-gray-900">{{ getCurrentTabLabel() }}</h2>
          </div>
          <div class="flex items-center gap-3">
            <el-input
              v-model="searchKeyword"
              :placeholder="'搜索' + getCurrentTabLabel() + '...'"
              clearable
              class="w-64"
              @keyup.enter="activeTab === 'modelResources' ? handleModelSearch() : activeTab === 'promptTemplates' ? handlePromptTemplateSearch() : null"
            >
              <template #prefix>
                <Icon icon="mdi:magnify" class="text-gray-400" />
              </template>
            </el-input>
            <el-button
              v-if="activeTab === 'modelResources' || activeTab === 'promptTemplates'"
              type="default"
              @click="activeTab === 'modelResources' ? handleModelSearch() : handlePromptTemplateSearch()"
            >
              <template #icon><Icon icon="mdi:magnify" /></template>
              搜索
            </el-button>
            <el-button type="primary" @click="handleAdd">
              <template #icon>
                <Icon icon="mdi:plus" />
              </template>
              新增{{ getCurrentTabLabel() }}
            </el-button>
          </div>
        </div>

        <div class="flex-1 overflow-auto p-6">
          <div v-if="activeTab === 'analysisEngines'" class="space-y-4">
            <div class="min-h-[200px]">
              <div
                v-for="(item, index) in filteredAnalysisOptions"
                :key="item.id"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-blue-100">
                      <Icon :icon="item.icon" class="text-2xl text-blue-600" />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-bold text-gray-900">{{ item.label }}</h3>
                        <el-tag size="small" class="border-0 bg-gray-100 text-gray-700">
                          {{ item.value }}
                        </el-tag>
                      </div>
                      <p v-if="item.description" class="text-sm text-gray-600 mb-3">{{ item.description }}</p>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 ml-4">
                    <el-button type="primary" link @click="handleAction('查看', item.label)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <el-button type="primary" link @click="handleAction('编辑', item.label)">
                      <template #icon><Icon icon="mdi:pencil" /></template>
                      编辑
                    </el-button>
                    <el-button type="danger" link @click="handleAction('删除', item.label)">
                      <template #icon><Icon icon="mdi:delete" /></template>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
              <div v-if="filteredAnalysisOptions.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>
          </div>

          <div v-else-if="activeTab === 'modelResources'" class="space-y-4">
            <div v-loading="modelListLoading" element-loading-text="加载中..." class="min-h-[200px]">
              <div
                v-for="(item, index) in modelList"
                :key="item.id"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-green-100">
                      <Icon icon="mdi:server" class="text-2xl text-green-600" />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-bold text-gray-900">{{ item.name }}</h3>
                        <el-tag size="small" class="border-0" type="success">已配置</el-tag>
                      </div>
                      <p v-if="item.description" class="text-sm text-gray-600 mb-2">{{ item.description }}</p>
                      <div class="flex items-center gap-6 text-sm flex-wrap">
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:link-variant" class="text-blue-500" />
                          <span class="text-gray-600">API 地址:</span>
                          <span class="font-mono text-xs text-gray-900">{{ item.base_url }}</span>
                        </div>
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:key" class="text-purple-500" />
                          <span class="text-gray-600">API Key:</span>
                          <span class="font-mono text-xs text-gray-900">{{ maskApiKey(item.api_key) }}</span>
                        </div>
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:brain" class="text-orange-500" />
                          <span class="text-gray-600">模型:</span>
                          <span class="font-medium text-gray-900">{{ item.model }}</span>
                        </div>
                        <div v-if="item.updated_at" class="flex items-center gap-2">
                          <Icon icon="mdi:clock-outline" class="text-gray-500" />
                          <span class="text-gray-600">更新时间:</span>
                          <span class="text-gray-700">{{ formatModelDate(item.updated_at) }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 ml-4">
                    <el-button type="primary" link @click="handleAction('查看', item.name)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <el-button type="primary" link @click="handleAction('编辑', item.name)">
                      <template #icon><Icon icon="mdi:pencil" /></template>
                      编辑
                    </el-button>
                    <el-button type="danger" link @click="handleAction('删除', item.name)">
                      <template #icon><Icon icon="mdi:delete" /></template>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
              <div v-if="!modelListLoading && modelList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>
            <div v-if="!modelListLoading && modelList.length > 0" class="flex justify-center pt-4">
              <el-pagination
                v-model:current-page="modelPagination.page"
                v-model:page-size="modelPagination.pageSize"
                :page-sizes="[10, 20, 50]"
                :total="modelPagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handleModelPageChange"
                @size-change="handleModelPageSizeChange"
              />
            </div>
          </div>

          <div v-else-if="activeTab === 'promptTemplates'" class="space-y-4">
            <div v-loading="promptTemplateListLoading" element-loading-text="加载中..." class="min-h-[200px]">
              <div
                v-for="(item, index) in promptTemplateList"
                :key="item.id"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-amber-100">
                      <Icon icon="mdi:file-document-edit" class="text-2xl text-amber-600" />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-bold text-gray-900">{{ item.name }}</h3>
                      </div>
                      <p class="text-sm text-gray-600 mb-3 line-clamp-2">{{ getPromptTemplatePreview(item) }}</p>
                      <div class="flex items-center gap-2 text-sm text-gray-500">
                        <Icon icon="mdi:clock-outline" />
                        <span>更新于 {{ formatModelDate(item.updated_at) }}</span>
                      </div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 ml-4">
                    <el-button type="primary" link @click="handleAction('查看', item.name)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <el-button type="primary" link @click="handleAction('编辑', item.name)">
                      <template #icon><Icon icon="mdi:pencil" /></template>
                      编辑
                    </el-button>
                    <el-button type="danger" link @click="handleAction('删除', item.name)">
                      <template #icon><Icon icon="mdi:delete" /></template>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
              <div v-if="!promptTemplateListLoading && promptTemplateList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>
            <div v-if="!promptTemplateListLoading && promptTemplateList.length > 0" class="flex justify-center pt-4">
              <el-pagination
                v-model:current-page="promptTemplatePagination.page"
                v-model:page-size="promptTemplatePagination.pageSize"
                :page-sizes="[10, 20, 50]"
                :total="promptTemplatePagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handlePromptTemplatePageChange"
                @size-change="handlePromptTemplatePageSizeChange"
              />
            </div>
          </div>

          <div v-else-if="activeTab === 'tools'" class="space-y-4">
            <div class="min-h-[200px]">
              <div
                v-for="(item, index) in filteredTools"
                :key="item.id"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-purple-100">
                      <Icon icon="mdi:tools" class="text-2xl text-purple-600" />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-bold text-gray-900">{{ item.name }}</h3>
                        <el-tag size="small" class="border-0 bg-purple-100 text-purple-700">
                          {{ item.type }}
                        </el-tag>
                      </div>
                      <p class="text-sm text-gray-600">{{ item.description }}</p>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 ml-4">
                    <el-button type="primary" link @click="handleAction('查看', item.name)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <el-button type="primary" link @click="handleAction('编辑', item.name)">
                      <template #icon><Icon icon="mdi:pencil" /></template>
                      编辑
                    </el-button>
                    <el-button type="danger" link @click="handleAction('删除', item.name)">
                      <template #icon><Icon icon="mdi:delete" /></template>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
              <div v-if="filteredTools.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="modelDialogVisible"
      title="新增模型资源"
      width="560px"
      :close-on-click-modal="false"
      @close="handleModelDialogClose"
    >
      <el-form
        ref="modelFormRef"
        :model="modelFormData"
        :rules="modelFormRules"
        label-width="100px"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="modelFormData.name" placeholder="请输入名称" clearable />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="modelFormData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入描述（可选）"
            clearable
          />
        </el-form-item>
        <el-form-item label="API 地址" prop="base_url">
          <el-input v-model="modelFormData.base_url" placeholder="请输入 base_url" clearable />
        </el-form-item>
        <el-form-item label="API Key" prop="api_key">
          <el-input v-model="modelFormData.api_key" type="password" placeholder="请输入 api_key" clearable show-password />
        </el-form-item>
        <el-form-item label="模型" prop="model">
          <el-input v-model="modelFormData.model" placeholder="请输入模型名称" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleModelDialogClose">取消</el-button>
        <el-button type="primary" :loading="modelSubmitLoading" @click="handleModelSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="promptTemplateDialogVisible"
      title="新增提示词模板"
      width="960px"
      :close-on-click-modal="false"
      @close="handlePromptTemplateDialogClose"
    >
      <el-form
        ref="promptTemplateFormRef"
        :model="promptTemplateFormData"
        :rules="promptTemplateFormRules"
        label-width="100px"
      >
        <el-form-item label="标题" prop="name">
          <el-input v-model="promptTemplateFormData.name" placeholder="请输入提示词标题" clearable />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="promptTemplateFormData.description"
            type="textarea"
            :rows="4"
            placeholder="请输入描述（可选）"
            clearable
          />
        </el-form-item>
        <el-tabs v-model="promptTemplateActiveTab">
          <el-tab-pane label="系统提示词" name="system_prompt">
            <el-form-item label="系统提示词" prop="system_prompt">
              <MonacoEditor
                v-model="promptTemplateFormData.system_prompt"
                language="markdown"
                :read-only="false"
                :min-height="560"
              />
            </el-form-item>
          </el-tab-pane>
          <el-tab-pane label="用户提示词" name="user_prompt">
            <el-form-item label="用户提示词" prop="user_prompt">
              <MonacoEditor
                v-model="promptTemplateFormData.user_prompt"
                language="markdown"
                :read-only="false"
                :min-height="560"
              />
            </el-form-item>
          </el-tab-pane>
        </el-tabs>
      </el-form>
      <template #footer>
        <el-button @click="handlePromptTemplateDialogClose">取消</el-button>
        <el-button type="primary" :loading="promptTemplateSubmitLoading" @click="handlePromptTemplateSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import MonacoEditor from '@/components/MonacoEditor.vue'
import { ElMessage } from 'element-plus'
import { agentApi } from '@/api/agent'
import { getPaginatedData } from '@/utils/request'

const activeTab = ref('analysisEngines')
const searchKeyword = ref('')

const engineTabs = [
  { key: 'analysisEngines', label: '分析引擎', icon: 'mdi:brain' },
  { key: 'modelResources', label: '模型资源', icon: 'mdi:server' },
  { key: 'promptTemplates', label: '提示词模板', icon: 'mdi:file-document-edit' },
  { key: 'tools', label: '工具', icon: 'mdi:tools' }
]

const analysisOptionsList = ref([
  { id: '1', label: '内容分析', icon: 'mdi:text-box', value: 'content', description: '对文本内容进行结构化与主题分析' },
  { id: '2', label: '共识分析', icon: 'mdi:account-group', value: 'consensus', description: '分析群体观点与共识度' },
  { id: '3', label: '情感分析', icon: 'mdi:emoticon-happy-outline', value: 'emotion', description: '识别文本情感倾向与强度' },
  { id: '4', label: '多模态分析', icon: 'mdi:image-filter-none', value: 'multimodal', description: '结合图文等多模态信息进行分析' },
  { id: '5', label: '传播路径分析', icon: 'mdi:share-variant', value: 'propagation', description: '追踪信息传播路径与节点' },
  { id: '6', label: '证据链溯源分析', icon: 'mdi:link-variant', value: 'evidence', description: '构建与追溯证据链' }
])

const modelList = ref([])
const modelListLoading = ref(false)
const modelPagination = ref({ page: 1, pageSize: 10, total: 0, totalPages: 0 })
const modelLoadedOnce = ref(false)

const fetchModelList = async () => {
  modelListLoading.value = true
  try {
    const result = await getPaginatedData(agentApi.getModelList, {
      search: searchKeyword.value.trim() || undefined,
      page: modelPagination.value.page,
      page_size: modelPagination.value.pageSize
    })
    modelList.value = result.items
    modelPagination.value = { ...modelPagination.value, ...result.pagination }
    modelLoadedOnce.value = true
  } catch (e) {
    modelList.value = []
  } finally {
    modelListLoading.value = false
  }
}

const promptTemplateList = ref([])
const promptTemplateListLoading = ref(false)
const promptTemplatePagination = ref({ page: 1, pageSize: 10, total: 0, totalPages: 0 })
const promptTemplateLoadedOnce = ref(false)

const fetchPromptTemplateList = async () => {
  promptTemplateListLoading.value = true
  try {
    const result = await getPaginatedData(agentApi.getPromptTemplateList, {
      search: searchKeyword.value.trim() || undefined,
      page: promptTemplatePagination.value.page,
      page_size: promptTemplatePagination.value.pageSize
    })
    promptTemplateList.value = result.items
    promptTemplatePagination.value = { ...promptTemplatePagination.value, ...result.pagination }
    promptTemplateLoadedOnce.value = true
  } catch (e) {
    promptTemplateList.value = []
  } finally {
    promptTemplateListLoading.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'modelResources' && !modelLoadedOnce.value) fetchModelList()
  if (tab === 'promptTemplates' && !promptTemplateLoadedOnce.value) fetchPromptTemplateList()
})

const maskApiKey = (key) => {
  if (!key) return '***'
  if (key.length <= 4) return '***'
  return '***' + key.slice(-4)
}

const formatModelDate = (dateStr) => {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    return d.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return dateStr
  }
}

const toolsList = ref([
  { id: '1', name: '网页检索', description: '根据查询检索相关网页内容', type: '检索' },
  { id: '2', name: '知识库查询', description: '从配置的知识库中检索知识片段', type: '检索' },
  { id: '3', name: '代码执行', description: '在沙箱中执行代码片段', type: '执行' }
])

const statistics = computed(() => ({
  analysisOptions: analysisOptionsList.value.length,
  modelResources: modelPagination.value.total,
  promptTemplates: promptTemplatePagination.value.total,
  tools: toolsList.value.length
}))

const getResourceCount = (tabKey) => {
  const map = {
    analysisOptions: analysisOptionsList.value.length,
    modelResources: modelPagination.value.total,
    promptTemplates: promptTemplatePagination.value.total,
    tools: toolsList.value.length
  }
  return map[tabKey] ?? 0
}

const getPromptTemplatePreview = (item) => {
  if (item.description) return item.description
  const text = (item.system_prompt || item.user_prompt || '').trim()
  return text.length > 80 ? text.slice(0, 80) + '...' : text || '-'
}

const getCurrentTabIcon = () => {
  const tab = engineTabs.find(t => t.key === activeTab.value)
  return tab?.icon ?? 'mdi:help'
}

const getCurrentTabLabel = () => {
  const tab = engineTabs.find(t => t.key === activeTab.value)
  return tab?.label ?? ''
}

const filterByKeyword = (list, fields) => {
  const kw = searchKeyword.value.trim().toLowerCase()
  if (!kw) return list
  return list.filter(item =>
    fields.some(f => String(item[f] ?? '').toLowerCase().includes(kw))
  )
}

const filteredAnalysisOptions = computed(() =>
  filterByKeyword(analysisOptionsList.value, ['label', 'value', 'description'])
)
const filteredTools = computed(() =>
  filterByKeyword(toolsList.value, ['name', 'description', 'type'])
)

const handleModelPageChange = (page) => {
  modelPagination.value.page = page
  fetchModelList()
}
const handleModelPageSizeChange = (pageSize) => {
  modelPagination.value.pageSize = pageSize
  modelPagination.value.page = 1
  fetchModelList()
}
const handleModelSearch = () => {
  modelPagination.value.page = 1
  fetchModelList()
}

const handlePromptTemplatePageChange = (page) => {
  promptTemplatePagination.value.page = page
  fetchPromptTemplateList()
}
const handlePromptTemplatePageSizeChange = (pageSize) => {
  promptTemplatePagination.value.pageSize = pageSize
  promptTemplatePagination.value.page = 1
  fetchPromptTemplateList()
}
const handlePromptTemplateSearch = () => {
  promptTemplatePagination.value.page = 1
  fetchPromptTemplateList()
}

const modelDialogVisible = ref(false)
const modelFormRef = ref(null)
const modelSubmitLoading = ref(false)
const modelFormData = ref({
  name: '',
  description: '',
  base_url: '',
  api_key: '',
  model: ''
})
const modelFormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  base_url: [{ required: true, message: '请输入 API 地址', trigger: 'blur' }],
  api_key: [{ required: true, message: '请输入 API Key', trigger: 'blur' }],
  model: [{ required: true, message: '请输入模型', trigger: 'blur' }]
}

const handleAdd = () => {
  if (activeTab.value === 'modelResources') {
    modelDialogVisible.value = true
  } else if (activeTab.value === 'promptTemplates') {
    promptTemplateDialogVisible.value = true
  } else {
    ElMessage.info('功能开发中')
  }
}

const handleModelDialogClose = () => {
  modelDialogVisible.value = false
  modelFormRef.value?.resetFields()
  modelFormData.value = { name: '', description: '', base_url: '', api_key: '', model: '' }
}

const handleModelSubmit = async () => {
  if (!modelFormRef.value) return
  try {
    await modelFormRef.value.validate()
    modelSubmitLoading.value = true
    await agentApi.createModel({
      name: modelFormData.value.name,
      description: modelFormData.value.description || undefined,
      base_url: modelFormData.value.base_url,
      api_key: modelFormData.value.api_key,
      model: modelFormData.value.model
    })
    ElMessage.success('新增成功')
    handleModelDialogClose()
    modelPagination.value.page = 1
    fetchModelList()
  } catch (e) {
    if (e !== false) console.error('新增模型失败:', e)
  } finally {
    modelSubmitLoading.value = false
  }
}

const DEFAULT_SYSTEM_PROMPT_TEMPLATE = `【注意】提示词模板仍需优化
## Role: 互联网舆情监测 Agent

## Capability: 
1. 具备 SQL/API 数据库访问权限。
2. 擅长对非结构化文本进行语义聚类。

## Workflow:
1. 分析用户指令，生成数据库检索参数。
2. 执行查询并对原始结果进行预处理（去重、脱敏）。
3. 运用“多维交叉分析法”生成洞察。
4. 以 Markdown 报告形式输出。

## Constraints:
- 必须引用原始数据来源。
- 总结字数不超过 800 字，重点内容加粗。
- 若数据量少于 5 条，需注明“样本量较小”。`

const DEFAULT_USER_PROMPT_TEMPLATE = `【注意】提示词模板仍需优化
### 1. 任务背景 (Context)
我目前正在处理 [项目名称/具体场景]，目标是解决 [具体痛点/实现什么目的]。

### 2. 核心任务 (Task)
请基于系统设定的角色，为我执行以下操作：
- [具体子任务 1]
- [具体子任务 2]

### 3. 输入数据/参考资料 (Input/Data)
以下是你要处理的具体内容：
---
[在此粘贴你的原始文本、数据、链接或代码]
使用 {{ template_params }} 可以在实体分析时自动填充实体参数，如 {{ uuid }} 将在运行时自动替换为实体uuid
---

### 4. 特定要求 (Requirements)
- 语气风格：[如：专业/幽默/简洁]
- 重点关注：[如：性能优化/合规性/视觉美感]
- 避坑指南：[如：不要使用任何专业术语/不要提及竞争对手名称]

### 5. 输出交付物 (Output)
请以 [JSON / Markdown表格 / 三段式报告] 的形式输出。`

const promptTemplateDialogVisible = ref(false)
const promptTemplateActiveTab = ref('system_prompt')
const promptTemplateFormRef = ref(null)
const promptTemplateSubmitLoading = ref(false)
const promptTemplateFormData = ref({
  name: '',
  description: '',
  system_prompt: DEFAULT_SYSTEM_PROMPT_TEMPLATE,
  user_prompt: DEFAULT_USER_PROMPT_TEMPLATE
})
const promptTemplateFormRules = {
  name: [{ required: true, message: '请输入提示词标题', trigger: 'blur' }],
  system_prompt: [{ required: true, message: '请输入系统提示词', trigger: 'blur' }],
  user_prompt: [{ required: true, message: '请输入用户提示词', trigger: 'blur' }]
}

const handlePromptTemplateDialogClose = () => {
  promptTemplateDialogVisible.value = false
  promptTemplateActiveTab.value = 'system_prompt'
  promptTemplateFormRef.value?.resetFields()
  promptTemplateFormData.value = { name: '', description: '', system_prompt: DEFAULT_SYSTEM_PROMPT_TEMPLATE, user_prompt: DEFAULT_USER_PROMPT_TEMPLATE }
}

const handlePromptTemplateSubmit = async () => {
  if (!promptTemplateFormRef.value) return
  try {
    await promptTemplateFormRef.value.validate()
    promptTemplateSubmitLoading.value = true
    await agentApi.createPromptTemplate({
      name: promptTemplateFormData.value.name,
      description: promptTemplateFormData.value.description || undefined,
      system_prompt: promptTemplateFormData.value.system_prompt,
      user_prompt: promptTemplateFormData.value.user_prompt
    })
    ElMessage.success('新增成功')
    handlePromptTemplateDialogClose()
    promptTemplatePagination.value.page = 1
    fetchPromptTemplateList()
  } catch (e) {
    if (e !== false) {
      const data = promptTemplateFormData.value
      if (!data.system_prompt?.trim()) promptTemplateActiveTab.value = 'system_prompt'
      else if (!data.user_prompt?.trim()) promptTemplateActiveTab.value = 'user_prompt'
      console.error('新增提示词模板失败:', e)
    }
  } finally {
    promptTemplateSubmitLoading.value = false
  }
}

const handleAction = (action, name) => {
  ElMessage.info(`功能开发中：${action} ${name}`)
}
</script>
