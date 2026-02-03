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
              <p class="text-xs text-gray-500">分析引擎</p>
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
              v-if="activeTab !== 'tools'"
              v-model="searchKeyword"
              :placeholder="'搜索' + getCurrentTabLabel() + '...'"
              clearable
              class="w-64"
              @keyup.enter="activeTab === 'analysisEngines' ? handleAgentSearch() : activeTab === 'modelResources' ? handleModelSearch() : activeTab === 'promptTemplates' ? handlePromptTemplateSearch() : null"
            >
              <template #prefix>
                <Icon icon="mdi:magnify" class="text-gray-400" />
              </template>
            </el-input>
            <el-button
              v-if="activeTab === 'analysisEngines' || activeTab === 'modelResources' || activeTab === 'promptTemplates'"
              type="default"
              @click="activeTab === 'analysisEngines' ? handleAgentSearch() : activeTab === 'modelResources' ? handleModelSearch() : handlePromptTemplateSearch()"
            >
              <template #icon><Icon icon="mdi:magnify" /></template>
              搜索
            </el-button>
            <el-button v-if="activeTab !== 'tools'" type="primary" @click="handleAdd">
              <template #icon>
                <Icon icon="mdi:plus" />
              </template>
              新增{{ getCurrentTabLabel() }}
            </el-button>
          </div>
        </div>

        <div class="flex-1 overflow-auto p-6">
          <div v-if="activeTab === 'analysisEngines'" class="space-y-4">
            <div v-loading="agentListLoading" element-loading-text="加载中..." class="min-h-[200px]">
              <div
                v-for="(item, index) in agentList"
                :key="item.id"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-blue-100">
                      <Icon icon="mdi:brain" class="text-2xl text-blue-600" />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-bold text-gray-900">{{ item.name }}</h3>
                      </div>
                      <p v-if="item.description" class="text-sm text-gray-600 mb-2">{{ item.description }}</p>
                      <div class="flex items-center gap-6 text-sm flex-wrap">
                        <div v-if="item.llm_config && Object.keys(item.llm_config).length" class="flex items-center gap-2">
                          <Icon icon="mdi:cog" class="text-orange-500" />
                          <span class="text-gray-600">LLM 配置:</span>
                          <span class="text-gray-700">{{ Object.keys(item.llm_config).length }} 项</span>
                        </div>
                        <div v-if="item.tools?.length" class="flex items-center gap-2">
                          <Icon icon="mdi:tools" class="text-purple-500" />
                          <span class="text-gray-600">工具:</span>
                          <span class="text-gray-700">{{ item.tools.join(', ') }}</span>
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
              <div v-if="!agentListLoading && agentList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>
            <div v-if="!agentListLoading && agentList.length > 0" class="flex justify-center pt-4">
              <el-pagination
                v-model:current-page="agentPagination.page"
                v-model:page-size="agentPagination.pageSize"
                :page-sizes="[10, 20, 50]"
                :total="agentPagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handleAgentPageChange"
                @size-change="handleAgentPageSizeChange"
              />
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
            <div v-loading="toolsListLoading" element-loading-text="加载中..." class="min-h-[200px]">
              <div
                v-for="(item, index) in toolsList"
                :key="item.name + '-' + index"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start gap-4">
                  <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-purple-100">
                    <Icon icon="mdi:tools" class="text-2xl text-purple-600" />
                  </div>
                  <div class="flex-1 min-w-0">
                    <h3 class="text-lg font-bold text-gray-900 mb-2">{{ item.name }}</h3>
                    <p v-if="item.description" class="text-sm text-gray-600 mb-3 whitespace-pre-line">{{ item.description }}</p>
                    <div v-if="item.parameters?.length" class="mt-3">
                      <p class="text-sm font-medium text-gray-700 mb-2">参数</p>
                      <el-table :data="item.parameters" size="small" border>
                        <el-table-column prop="name" label="参数名称" min-width="120" />
                        <el-table-column prop="description" label="参数描述" min-width="160">
                          <template #default="{ row }">
                            <span class="whitespace-pre-line">{{ row.description ?? '-' }}</span>
                          </template>
                        </el-table-column>
                        <el-table-column prop="type" label="类型" width="100" />
                        <el-table-column label="必填" width="70" align="center">
                          <template #default="{ row }">
                            <el-tag v-if="row.required" size="small" type="danger">是</el-tag>
                            <el-tag v-else size="small" type="info">否</el-tag>
                          </template>
                        </el-table-column>
                        <el-table-column label="默认值" min-width="100">
                          <template #default="{ row }">
                            {{ row.default !== undefined && row.default !== null ? String(row.default) : '-' }}
                          </template>
                        </el-table-column>
                      </el-table>
                    </div>
                  </div>
                </div>
              </div>
              <div v-if="!toolsListLoading && toolsList.length === 0" class="flex flex-col items-center justify-center py-16">
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

    <el-dialog
      v-model="agentDialogVisible"
      title="新增分析引擎"
      width="560px"
      :close-on-click-modal="false"
      @close="handleAgentDialogClose"
      @opened="loadAgentDialogOptions"
    >
      <el-form
        ref="agentFormRef"
        :model="agentFormData"
        :rules="agentFormRules"
        label-width="120px"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="agentFormData.name" placeholder="请输入名称" clearable />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="agentFormData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入描述（可选）"
            clearable
          />
        </el-form-item>
        <el-form-item label="提示词模板" prop="prompt_template_id">
          <el-select
            v-model="agentFormData.prompt_template_id"
            placeholder="请选择提示词模板"
            class="w-full"
            filterable
            :loading="agentPromptOptionsLoading"
          >
            <el-option
              v-for="item in promptTemplateOptionsForAgent"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模型" prop="model_id">
          <el-select
            v-model="agentFormData.model_id"
            placeholder="请选择模型"
            class="w-full"
            filterable
            :loading="agentModelOptionsLoading"
          >
            <el-option
              v-for="item in modelOptionsForAgent"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="LLM 配置" prop="llm_config">
          <KeyValueEditor v-model="agentFormData.llm_config" />
        </el-form-item>
        <el-form-item label="工具" prop="tools">
          <el-select
            v-model="agentFormData.tools"
            placeholder="请选择工具（可多选）"
            class="w-full"
            multiple
            filterable
            :loading="agentToolsOptionsLoading"
          >
            <el-option
              v-for="name in agentToolsListOptions"
              :key="name"
              :label="name"
              :value="name"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleAgentDialogClose">取消</el-button>
        <el-button type="primary" :loading="agentSubmitLoading" @click="handleAgentSubmit">确定</el-button>
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
import KeyValueEditor from '@/components/action/nodes/components/KeyValueEditor.vue'
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

const toolsList = ref([])
const toolsListLoading = ref(false)
const toolsLoadedOnce = ref(false)

const fetchToolsList = async () => {
  toolsListLoading.value = true
  try {
    const res = await agentApi.getToolsList()
    toolsList.value = Array.isArray(res?.data) ? res.data : []
    toolsLoadedOnce.value = true
  } catch (e) {
    toolsList.value = []
  } finally {
    toolsListLoading.value = false
  }
}

const agentList = ref([])
const agentListLoading = ref(false)
const agentPagination = ref({ page: 1, pageSize: 10, total: 0, totalPages: 0 })
const agentLoadedOnce = ref(false)

const fetchAgentList = async () => {
  agentListLoading.value = true
  try {
    const result = await getPaginatedData(agentApi.getAgentList, {
      search: searchKeyword.value.trim() || undefined,
      page: agentPagination.value.page,
      page_size: agentPagination.value.pageSize
    })
    agentList.value = result.items
    agentPagination.value = { ...agentPagination.value, ...result.pagination }
    agentLoadedOnce.value = true
  } catch (e) {
    agentList.value = []
  } finally {
    agentListLoading.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'analysisEngines' && !agentLoadedOnce.value) fetchAgentList()
  if (tab === 'modelResources' && !modelLoadedOnce.value) fetchModelList()
  if (tab === 'promptTemplates' && !promptTemplateLoadedOnce.value) fetchPromptTemplateList()
  if (tab === 'tools' && !toolsLoadedOnce.value) fetchToolsList()
}, { immediate: true })

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

const statistics = computed(() => ({
  analysisEngines: agentPagination.value.total,
  analysisOptions: agentPagination.value.total,
  modelResources: modelPagination.value.total,
  promptTemplates: promptTemplatePagination.value.total,
  tools: toolsList.value.length
}))

const getResourceCount = (tabKey) => statistics.value[tabKey] ?? 0

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

const handleAgentPageChange = (page) => {
  agentPagination.value.page = page
  fetchAgentList()
}
const handleAgentPageSizeChange = (pageSize) => {
  agentPagination.value.pageSize = pageSize
  agentPagination.value.page = 1
  fetchAgentList()
}
const handleAgentSearch = () => {
  agentPagination.value.page = 1
  fetchAgentList()
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

const agentDialogVisible = ref(false)
const agentFormRef = ref(null)
const agentSubmitLoading = ref(false)
const agentFormData = ref({
  name: '',
  description: '',
  prompt_template_id: '',
  model_id: '',
  llm_config: {},
  tools: []
})
const agentFormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  prompt_template_id: [{ required: true, message: '请选择提示词模板', trigger: 'change' }],
  model_id: [{ required: true, message: '请选择模型', trigger: 'change' }]
}
const agentToolsListOptions = ref([])
const agentToolsOptionsLoading = ref(false)
const promptTemplateOptionsForAgent = ref([])
const agentPromptOptionsLoading = ref(false)
const modelOptionsForAgent = ref([])
const agentModelOptionsLoading = ref(false)

const loadAgentDialogOptions = async () => {
  agentToolsOptionsLoading.value = true
  try {
    const res = await agentApi.getToolsListForAgent()
    agentToolsListOptions.value = Array.isArray(res?.data) ? res.data : []
  } catch (e) {
    agentToolsListOptions.value = []
  } finally {
    agentToolsOptionsLoading.value = false
  }
  if (promptTemplateOptionsForAgent.value.length === 0) {
    agentPromptOptionsLoading.value = true
    try {
      const result = await getPaginatedData(agentApi.getPromptTemplateList, { page: 1, page_size: 100 })
      promptTemplateOptionsForAgent.value = result.items || []
    } catch (e) {
      promptTemplateOptionsForAgent.value = []
    } finally {
      agentPromptOptionsLoading.value = false
    }
  }
  if (modelOptionsForAgent.value.length === 0) {
    agentModelOptionsLoading.value = true
    try {
      const res = await agentApi.getModelsList()
      modelOptionsForAgent.value = Array.isArray(res?.data) ? res.data : []
    } catch (e) {
      modelOptionsForAgent.value = []
    } finally {
      agentModelOptionsLoading.value = false
    }
  }
}

const resetAgentForm = () => {
  agentFormData.value = {
    name: '',
    description: '',
    prompt_template_id: '',
    model_id: '',
    llm_config: {},
    tools: []
  }
  agentFormRef.value?.resetFields()
}

const handleAgentDialogClose = () => {
  agentDialogVisible.value = false
  resetAgentForm()
}

const handleAgentSubmit = async () => {
  if (!agentFormRef.value) return
  try {
    await agentFormRef.value.validate()
    agentSubmitLoading.value = true
    await agentApi.createAgent({
      name: agentFormData.value.name,
      description: agentFormData.value.description || undefined,
      prompt_template_id: agentFormData.value.prompt_template_id,
      model_id: agentFormData.value.model_id,
      llm_config: agentFormData.value.llm_config || {},
      tools: agentFormData.value.tools || []
    })
    ElMessage.success('新增成功')
    handleAgentDialogClose()
    agentPagination.value.page = 1
    fetchAgentList()
  } catch (e) {
    if (e !== false) console.error('新增分析引擎失败:', e)
  } finally {
    agentSubmitLoading.value = false
  }
}

const openAgentDialog = () => {
  agentDialogVisible.value = true
}

const handleAdd = () => {
  if (activeTab.value === 'analysisEngines') {
    openAgentDialog()
  } else if (activeTab.value === 'modelResources') {
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

const DEFAULT_SYSTEM_PROMPT_TEMPLATE = `---
创建者查看，记得删除
# 文本翻译任务样本提示词
---
## Role: 文本翻译 Agent

## Capability: 
1. 可以通过多种工具来实现目标
2. 具备有限的数据访问能力，你只能访问提供的 \`uuid\` 的数据
3. 具备有限的数据字段修改的能力，你只能修改 \`translate_content\` 字段。

## Workflow:
1. 分析任务目标，通过工具创建 Todos，在每一步完成后设置完成 Todo，随时回顾 Todos 以确认步骤进度。
1. 通过工具读取对应 \`uuid\` 和 \`entity_type\` 的 \`clean_content\` 字段
2. 如果 \`clean_content\` 字段内容为空或None，则立即结束并上报失败
3. 对 \`clean_content\` 字段内容进行翻译，将内容原文翻译成指定的语言。
4. 将翻译内容写入到对应 \`uuid\` 和 \`entity_type\` 的 \`translate_content\` 字段。
5. 按照规定格式输出最终结果。

## Constraints:
- 进度透明: Todos 必须具备可读性，作为用户监控进度的唯一凭证。
- 数据安全: 严禁尝试读取或修改本指令授权之外的任何字段。
- 翻译准则:
    - 语境重建: 针对 HTML 提取导致的破碎文本，必须先根据上下文拼接成完整意群再翻译，严禁碎片化直译。
    - 专业标注: 专业词汇保留原文（如：\`深度学习 (Deep Learning)\`）。
    - 译者辅助: 仅在俚语或文化差异极大时使用 \`(译者注: ...)\`。
- 格式保持: 在处理混乱格式时，应通过换行符重新构建合理的段落结构。
- 终态定义: 任何路径的终点必须包含原因说明。成功统一标识为“任务完成”。`

const DEFAULT_USER_PROMPT_TEMPLATE = `---
创建者查看，记得删除
# 文本翻译任务样本提示词
**注意：** 使用 {{ template_params }} 可以在实体分析时自动填充实体参数，如 {{ uuid }} 将在运行时自动替换为实体uuid
---
# 🚀 启动翻译任务

### 1. 翻译目标 (Target)
- UUID: {{ uuid }}
- Entity Type: {{ entity_type }}

### 2. 翻译参数 (Context)
- 目标语言: **中文 (zh-CN)**
---
**请按照系统设定的 Workflow 开始执行：创建 Todos -> 读取数据 -> 执行翻译 -> 回写字段。**`

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
