<template>
  <ConfigCenterLayout
    title-prefix="分析引擎"
    title-suffix="配置"
    subtitle="管理分析选项、模型资源、提示词模板与工具等配置"
    sidebar-title="配置类型"
    :nav-items="engineTabs"
    v-model="activeTab"
    :get-badge="getResourceCount"
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
    <template #toolbar>
      <div class="bg-white px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <Icon :icon="currentTabIcon" class="text-2xl text-blue-600" />
          <h2 class="text-xl font-bold text-gray-900">{{ currentTabLabel }}</h2>
        </div>
        <div class="flex items-center gap-3">
          <el-input
            v-if="activeTab !== 'tools'"
            v-model="searchKeyword"
            :placeholder="'搜索' + currentTabLabel + '...'"
            clearable
            class="w-64"
            @keyup.enter="activeTab === 'analysisEngines' ? handleAgentSearch() : activeTab === 'modelResources' ? handleModelSearch() : activeTab === 'promptTemplates' ? handlePromptTemplateSearch() : activeTab === 'workspaces' ? handleWorkspaceSearch() : null"
          >
            <template #prefix>
              <Icon icon="mdi:magnify" class="text-gray-400" />
            </template>
          </el-input>
          <el-button
            v-if="activeTab === 'analysisEngines' || activeTab === 'modelResources' || activeTab === 'promptTemplates' || activeTab === 'workspaces'"
            type="default"
            @click="activeTab === 'analysisEngines' ? handleAgentSearch() : activeTab === 'modelResources' ? handleModelSearch() : activeTab === 'promptTemplates' ? handlePromptTemplateSearch() : handleWorkspaceSearch()"
          >
            <template #icon><Icon icon="mdi:magnify" /></template>
            搜索
          </el-button>
          <el-button v-if="activeTab !== 'tools'" type="primary" @click="handleAdd">
            <template #icon>
              <Icon icon="mdi:plus" />
            </template>
            新增{{ currentTabLabel }}
          </el-button>
        </div>
      </div>
    </template>
          <div v-if="activeTab === 'analysisEngines'" class="space-y-4">
            <div v-loading="agentListLoading" element-loading-text="加载中..." class="min-h-50">
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
                    <el-button type="primary" link @click="openAgentDetail(item)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <el-button type="primary" link @click="openAgentEdit(item)">
                      <template #icon><Icon icon="mdi:pencil" /></template>
                      编辑
                    </el-button>
                    <el-button type="danger" link @click="handleDeleteAgent(item)">
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
            <div v-loading="modelListLoading" element-loading-text="加载中..." class="min-h-50">
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
            <div v-loading="promptTemplateListLoading" element-loading-text="加载中..." class="min-h-50">
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
                    <el-button type="primary" link @click="openPromptTemplateDetail(item)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <el-button type="primary" link @click="openPromptTemplateEdit(item)">
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

          <div v-else-if="activeTab === 'workspaces'" class="space-y-4">
            <div v-loading="workspaceListLoading" element-loading-text="加载中..." class="min-h-50">
              <div
                v-for="(item, index) in workspaceList"
                :key="item.id || index"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-indigo-100">
                      <Icon icon="mdi:view-dashboard-variant" class="text-2xl text-indigo-600" />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-bold text-gray-900">{{ item.name }}</h3>
                      </div>
                      <p v-if="item.description" class="text-sm text-gray-600 mb-2 whitespace-pre-line">{{ item.description }}</p>
                      <div class="flex items-center gap-6 text-sm flex-wrap">
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:server" class="text-green-600" />
                          <span class="text-gray-600">模型白名单:</span>
                          <span class="text-gray-900">{{ Array.isArray(item.model_config_ids) ? item.model_config_ids.length : 0 }} 项</span>
                        </div>
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:file-document-edit" class="text-amber-600" />
                          <span class="text-gray-600">模板白名单:</span>
                          <span class="text-gray-900">{{ Array.isArray(item.prompt_template_ids) ? item.prompt_template_ids.length : 0 }} 项</span>
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
                    <el-button type="primary" link @click="openWorkspaceDetail(item)">
                      <template #icon><Icon icon="mdi:eye" /></template>
                      查看
                    </el-button>
                    <el-button type="primary" link @click="openWorkspaceEdit(item)">
                      <template #icon><Icon icon="mdi:pencil" /></template>
                      编辑
                    </el-button>
                    <el-button type="danger" link @click="handleDeleteWorkspace(item)">
                      <template #icon><Icon icon="mdi:delete" /></template>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>
              <div v-if="!workspaceListLoading && workspaceList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>
            <div v-if="!workspaceListLoading && workspaceList.length > 0" class="flex justify-center pt-4">
              <el-pagination
                v-model:current-page="workspacePagination.page"
                v-model:page-size="workspacePagination.pageSize"
                :page-sizes="[10, 20, 50]"
                :total="workspacePagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handleWorkspacePageChange"
                @size-change="handleWorkspacePageSizeChange"
              />
            </div>
          </div>

          <div v-else-if="activeTab === 'tools'" class="space-y-4">
            <div v-loading="toolsListLoading" element-loading-text="加载中..." class="min-h-50">
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
  </ConfigCenterLayout>

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
      :title="editingPromptTemplateId ? '编辑提示词模板' : '新增提示词模板'"
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
      v-model="promptTemplateDetailVisible"
      title="提示词模板详情"
      width="960px"
      :close-on-click-modal="true"
    >
      <div v-loading="promptTemplateDetailLoading" element-loading-text="加载中..." class="min-h-50">
        <template v-if="promptTemplateDetail">
          <div class="space-y-4">
            <div>
              <div class="text-sm text-gray-500 mb-1">名称</div>
              <div class="text-base font-medium text-gray-900">{{ promptTemplateDetail.name }}</div>
            </div>
            <div v-if="promptTemplateDetail.description">
              <div class="text-sm text-gray-500 mb-1">描述</div>
              <div class="text-sm text-gray-700 whitespace-pre-line">{{ promptTemplateDetail.description }}</div>
            </div>
            <div class="flex items-center gap-4 text-sm text-gray-500">
              <span>创建时间：{{ formatModelDate(promptTemplateDetail.created_at) }}</span>
              <span>更新时间：{{ formatModelDate(promptTemplateDetail.updated_at) }}</span>
            </div>
            <el-tabs v-model="promptTemplateDetailActiveTab">
              <el-tab-pane label="系统提示词" name="system_prompt">
                <div class="text-sm text-gray-500 mb-1">系统提示词</div>
                <MonacoEditor
                  :model-value="promptTemplateDetail.system_prompt || ''"
                  language="markdown"
                  :read-only="true"
                  :min-height="360"
                />
              </el-tab-pane>
              <el-tab-pane label="用户提示词" name="user_prompt">
                <div class="text-sm text-gray-500 mb-1">用户提示词</div>
                <MonacoEditor
                  :model-value="promptTemplateDetail.user_prompt || ''"
                  language="markdown"
                  :read-only="true"
                  :min-height="360"
                />
              </el-tab-pane>
            </el-tabs>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="promptTemplateDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="agentDialogVisible"
      :title="editingAgentId ? '编辑分析引擎' : '新增分析引擎'"
      width="560px"
      :close-on-click-modal="false"
      @closed="afterAgentDialogClosed"
      @opened="loadAgentDialogOptions"
    >
      <el-form
        ref="agentFormRef"
        :model="agentFormData"
        :rules="agentFormRules"
        label-width="120px"
      >
        <el-form-item label="工作区" prop="workspace_id">
          <el-select
            v-model="agentFormData.workspace_id"
            placeholder="请选择工作区"
            class="w-full"
            filterable
            clearable
            :loading="agentWorkspaceOptionsLoading"
            @change="handleAgentWorkspaceChange"
            :disabled="Boolean(editingAgentId)"
          >
            <el-option
              v-for="item in workspaceOptionsForAgent"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
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
            placeholder="请选择提示词模板（仅白名单）"
            class="w-full"
            filterable
            :loading="agentWorkspaceDetailLoading || agentPromptOptionsLoading"
            :disabled="!agentFormData.workspace_id"
          >
            <el-option
              v-for="item in promptTemplateOptionsForAgentFiltered"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模型" prop="model_config_id">
          <el-select
            v-model="agentFormData.model_config_id"
            placeholder="请选择模型（仅白名单）"
            class="w-full"
            filterable
            :loading="agentWorkspaceDetailLoading || agentModelOptionsLoading"
            :disabled="!agentFormData.workspace_id"
          >
            <el-option
              v-for="item in modelOptionsForAgentFiltered"
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
            placeholder="请选择工具（仅白名单，可多选）"
            class="w-full"
            multiple
            filterable
            :loading="agentWorkspaceDetailLoading || agentToolsOptionsLoading"
            :disabled="!agentFormData.workspace_id"
          >
            <el-option
              v-for="name in agentToolsListOptionsFiltered"
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

    <el-dialog
      v-model="agentDetailVisible"
      title="分析引擎详情"
      width="720px"
      :close-on-click-modal="true"
    >
      <div v-loading="agentDetailLoading" element-loading-text="加载中..." class="min-h-30">
        <template v-if="agentDetail">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="分析引擎ID">{{ agentDetail.id }}</el-descriptions-item>
            <el-descriptions-item label="工作区ID">{{ agentDetail.workspace_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="名称">{{ agentDetail.name }}</el-descriptions-item>
            <el-descriptions-item label="描述">
              <span class="whitespace-pre-line">{{ agentDetail.description || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="模型配置ID">{{ agentDetail.model_config_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="提示词模板ID">{{ agentDetail.prompt_template_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="工具">
              {{ Array.isArray(agentDetail.tools) && agentDetail.tools.length ? agentDetail.tools.join(', ') : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="LLM 配置">
              <pre class="m-0 p-2 bg-gray-50 rounded text-xs max-h-60 overflow-auto">{{ JSON.stringify(agentDetail.llm_config || {}, null, 2) }}</pre>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ agentDetail.created_at ? formatModelDate(agentDetail.created_at) : '-' }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ agentDetail.updated_at ? formatModelDate(agentDetail.updated_at) : '-' }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
      <template #footer>
        <el-button @click="agentDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="workspaceDialogVisible"
      :title="editingWorkspaceId ? '编辑工作区' : '新增工作区'"
      width="640px"
      :close-on-click-modal="false"
      @close="handleWorkspaceDialogClose"
      @opened="loadWorkspaceDialogOptions"
    >
      <el-form
        ref="workspaceFormRef"
        :model="workspaceFormData"
        :rules="workspaceFormRules"
        label-width="120px"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="workspaceFormData.name" placeholder="请输入工作区名称" clearable maxlength="64" show-word-limit />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="workspaceFormData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入描述（可选）"
            clearable
          />
        </el-form-item>
        <el-form-item label="模型白名单" prop="model_config_ids">
          <el-select
            v-model="workspaceFormData.model_config_ids"
            class="w-full"
            multiple
            filterable
            clearable
            placeholder="选择可用模型配置（可多选）"
            :loading="workspaceModelOptionsLoading"
          >
            <el-option
              v-for="opt in workspaceModelOptions"
              :key="opt.id"
              :label="opt.name"
              :value="opt.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模板白名单" prop="prompt_template_ids">
          <el-select
            v-model="workspaceFormData.prompt_template_ids"
            class="w-full"
            multiple
            filterable
            clearable
            placeholder="选择可用提示词模板（可多选）"
            :loading="workspacePromptTemplateOptionsLoading"
          >
            <el-option
              v-for="opt in workspacePromptTemplateOptions"
              :key="opt.id"
              :label="opt.name"
              :value="opt.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="工具白名单" prop="enabled_tools">
          <el-select
            v-model="workspaceFormData.enabled_tools"
            class="w-full"
            multiple
            filterable
            clearable
            placeholder="选择可用工具（可多选）"
            :loading="workspaceToolsOptionsLoading"
          >
            <el-option
              v-for="t in workspaceToolsOptions"
              :key="t.name"
              :label="t.name"
              :value="t.name"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="font-mono text-xs text-gray-900">{{ t.name }}</span>
                <span class="text-xs text-gray-500 truncate max-w-80">{{ t.description || '' }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleWorkspaceDialogClose">取消</el-button>
        <el-button type="primary" :loading="workspaceSubmitLoading" @click="handleWorkspaceSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="workspaceDetailVisible"
      title="工作区详情"
      width="720px"
      :close-on-click-modal="true"
    >
      <div v-loading="workspaceDetailLoading" element-loading-text="加载中..." class="min-h-30">
        <template v-if="workspaceDetail">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="工作区ID">{{ workspaceDetail.id }}</el-descriptions-item>
            <el-descriptions-item label="名称">{{ workspaceDetail.name }}</el-descriptions-item>
            <el-descriptions-item label="描述">
              <span class="whitespace-pre-line">{{ workspaceDetail.description || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="模型白名单">
              {{ Array.isArray(workspaceDetail.model_config_ids) && workspaceDetail.model_config_ids.length ? workspaceDetail.model_config_ids.join(', ') : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="模板白名单">
              {{ Array.isArray(workspaceDetail.prompt_template_ids) && workspaceDetail.prompt_template_ids.length ? workspaceDetail.prompt_template_ids.join(', ') : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="工具白名单">
              {{ Array.isArray(workspaceDetail.enabled_tools) && workspaceDetail.enabled_tools.length ? workspaceDetail.enabled_tools.join(', ') : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ workspaceDetail.created_at ? formatModelDate(workspaceDetail.created_at) : '-' }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ workspaceDetail.updated_at ? formatModelDate(workspaceDetail.updated_at) : '-' }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
      <template #footer>
        <el-button @click="workspaceDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import ConfigCenterLayout from '@/components/layout/ConfigCenterLayout.vue'
import { findNavItemByKey } from '@/utils/configCenterNav'
import MonacoEditor from '@/components/MonacoEditor.vue'
import KeyValueEditor from '@/components/action/nodes/components/KeyValueEditor.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { agentApi } from '@/api/agent'
import { getPaginatedData } from '@/utils/request'
import { formatDateTime } from '@/utils/action'

const activeTab = ref('analysisEngines')
const searchKeyword = ref('')

const engineTabs = [
  { key: 'workspaces', label: '工作区', icon: 'mdi:view-dashboard-variant' },
  { key: 'analysisEngines', label: '分析引擎', icon: 'mdi:brain' },
  { key: 'modelResources', label: '模型资源', icon: 'mdi:server' },
  { key: 'promptTemplates', label: '提示词模板', icon: 'mdi:file-document-edit' },
  { key: 'tools', label: '工具', icon: 'mdi:tools' }
]

const currentTabMeta = computed(() => findNavItemByKey(engineTabs, activeTab.value))
const currentTabIcon = computed(() => currentTabMeta.value?.icon ?? 'mdi:help')
const currentTabLabel = computed(() => currentTabMeta.value?.label ?? '')

const statisticsData = ref({
  agent_count: 0,
  model_count: 0,
  prompt_template_count: 0,
  tools_count: 0
})

const fetchStatistics = async () => {
  try {
    const res = await agentApi.getConfigStatistics()
    const data = res?.data
    if (data) {
      statisticsData.value = {
        agent_count: data.agent_count ?? 0,
        model_count: data.model_count ?? 0,
        prompt_template_count: data.prompt_template_count ?? 0,
        tools_count: data.tools_count ?? 0
      }
    }
  } catch {
    statisticsData.value = { agent_count: 0, model_count: 0, prompt_template_count: 0, tools_count: 0 }
  }
}

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

const workspaceList = ref([])
const workspaceListLoading = ref(false)
const workspacePagination = ref({ page: 1, pageSize: 10, total: 0, totalPages: 0 })
const workspaceLoadedOnce = ref(false)

const fetchWorkspaceList = async () => {
  workspaceListLoading.value = true
  try {
    const result = await getPaginatedData(agentApi.getWorkspaceList, {
      search: searchKeyword.value.trim() || undefined,
      page: workspacePagination.value.page,
      page_size: workspacePagination.value.pageSize
    })
    workspaceList.value = result.items
    workspacePagination.value = { ...workspacePagination.value, ...result.pagination }
    workspaceLoadedOnce.value = true
  } catch (e) {
    workspaceList.value = []
  } finally {
    workspaceListLoading.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'analysisEngines' && !agentLoadedOnce.value) fetchAgentList()
  if (tab === 'modelResources' && !modelLoadedOnce.value) fetchModelList()
  if (tab === 'promptTemplates' && !promptTemplateLoadedOnce.value) fetchPromptTemplateList()
  if (tab === 'workspaces' && !workspaceLoadedOnce.value) fetchWorkspaceList()
  if (tab === 'tools' && !toolsLoadedOnce.value) fetchToolsList()
}, { immediate: true })

onMounted(() => {
  fetchStatistics()
})

const maskApiKey = (key) => {
  if (!key) return '***'
  if (key.length <= 4) return '***'
  return '***' + key.slice(-4)
}

const formatModelDate = (dateStr) => formatDateTime(dateStr, { includeSecond: true })

const statistics = computed(() => ({
  analysisEngines: statisticsData.value.agent_count,
  analysisOptions: statisticsData.value.agent_count,
  modelResources: statisticsData.value.model_count,
  promptTemplates: statisticsData.value.prompt_template_count,
  workspaces: workspacePagination.value.total ?? 0,
  tools: statisticsData.value.tools_count
}))

const getResourceCount = (tabKey) => statistics.value[tabKey] ?? 0

const getPromptTemplatePreview = (item) => {
  if (item.description) return item.description
  const text = (item.system_prompt || item.user_prompt || '').trim()
  return text.length > 80 ? text.slice(0, 80) + '...' : text || '-'
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

const handleWorkspacePageChange = (page) => {
  workspacePagination.value.page = page
  fetchWorkspaceList()
}
const handleWorkspacePageSizeChange = (pageSize) => {
  workspacePagination.value.pageSize = pageSize
  workspacePagination.value.page = 1
  fetchWorkspaceList()
}
const handleWorkspaceSearch = () => {
  workspacePagination.value.page = 1
  fetchWorkspaceList()
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

const workspaceDialogVisible = ref(false)
const workspaceFormRef = ref(null)
const workspaceSubmitLoading = ref(false)
const editingWorkspaceId = ref(null)
const workspaceFormData = ref({
  name: '',
  description: '',
  model_config_ids: [],
  prompt_template_ids: [],
  enabled_tools: []
})
const workspaceFormRules = {
  name: [
    { required: true, message: '请输入工作区名称', trigger: 'blur' },
    { min: 1, max: 64, message: '名称长度需为 1~64', trigger: 'blur' }
  ]
}

const workspaceModelOptions = ref([])
const workspacePromptTemplateOptions = ref([])
const workspaceModelOptionsLoading = ref(false)
const workspacePromptTemplateOptionsLoading = ref(false)
const workspaceToolsOptions = ref([])
const workspaceToolsOptionsLoading = ref(false)

const workspaceDetailVisible = ref(false)
const workspaceDetail = ref(null)
const workspaceDetailLoading = ref(false)

const loadWorkspaceDialogOptions = async () => {
  if (workspaceModelOptions.value.length === 0) {
    workspaceModelOptionsLoading.value = true
    try {
      const res = await agentApi.getModelsList()
      workspaceModelOptions.value = Array.isArray(res?.data) ? res.data : []
    } catch {
      workspaceModelOptions.value = []
    } finally {
      workspaceModelOptionsLoading.value = false
    }
  }

  if (workspacePromptTemplateOptions.value.length === 0) {
    workspacePromptTemplateOptionsLoading.value = true
    try {
      const result = await getPaginatedData(agentApi.getPromptTemplateList, { page: 1, page_size: 100 })
      workspacePromptTemplateOptions.value = Array.isArray(result?.items) ? result.items : []
    } catch {
      workspacePromptTemplateOptions.value = []
    } finally {
      workspacePromptTemplateOptionsLoading.value = false
    }
  }

  if (workspaceToolsOptions.value.length === 0) {
    workspaceToolsOptionsLoading.value = true
    try {
      const res = await agentApi.getToolsList()
      workspaceToolsOptions.value = Array.isArray(res?.data) ? res.data : []
    } catch {
      workspaceToolsOptions.value = []
    } finally {
      workspaceToolsOptionsLoading.value = false
    }
  }
}

const resetWorkspaceForm = () => {
  workspaceFormData.value = { name: '', description: '', model_config_ids: [], prompt_template_ids: [], enabled_tools: [] }
  workspaceFormRef.value?.resetFields()
}

const handleWorkspaceDialogClose = () => {
  workspaceDialogVisible.value = false
  editingWorkspaceId.value = null
  resetWorkspaceForm()
}

const agentDialogVisible = ref(false)
const agentFormRef = ref(null)
const agentSubmitLoading = ref(false)
const agentFormData = ref({
  workspace_id: '',
  name: '',
  description: '',
  prompt_template_id: '',
  model_config_id: '',
  llm_config: {},
  tools: []
})
const agentFormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  workspace_id: [{ required: true, message: '请选择工作区', trigger: 'change' }],
  prompt_template_id: [{ required: true, message: '请选择提示词模板', trigger: 'change' }],
  model_config_id: [{ required: true, message: '请选择模型', trigger: 'change' }]
}
const agentToolsListOptions = ref([])
const agentToolsOptionsLoading = ref(false)
const promptTemplateOptionsForAgent = ref([])
const agentPromptOptionsLoading = ref(false)
const modelOptionsForAgent = ref([])
const agentModelOptionsLoading = ref(false)

const workspaceOptionsForAgent = ref([])
const agentWorkspaceOptionsLoading = ref(false)
const agentWorkspaceDetailLoading = ref(false)
const agentWorkspaceDetail = ref(null)

const allowedPromptTemplateIdSet = computed(() => {
  const ids = agentWorkspaceDetail.value?.prompt_template_ids
  if (!Array.isArray(ids)) return new Set()
  return new Set(ids)
})

const allowedModelConfigIdSet = computed(() => {
  const ids = agentWorkspaceDetail.value?.model_config_ids
  if (!Array.isArray(ids)) return new Set()
  return new Set(ids)
})

const allowedToolNameSet = computed(() => {
  const names = agentWorkspaceDetail.value?.enabled_tools
  if (!Array.isArray(names)) return new Set()
  return new Set(names)
})

const promptTemplateOptionsForAgentFiltered = computed(() => {
  const set = allowedPromptTemplateIdSet.value
  if (!agentFormData.value.workspace_id) return []
  return (promptTemplateOptionsForAgent.value || []).filter((t) => t?.id && set.has(t.id))
})

const modelOptionsForAgentFiltered = computed(() => {
  const set = allowedModelConfigIdSet.value
  if (!agentFormData.value.workspace_id) return []
  return (modelOptionsForAgent.value || []).filter((m) => m?.id && set.has(m.id))
})

const agentToolsListOptionsFiltered = computed(() => {
  const set = allowedToolNameSet.value
  if (!agentFormData.value.workspace_id) return []
  return (agentToolsListOptions.value || []).filter((name) => set.has(name))
})

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

  if (workspaceOptionsForAgent.value.length === 0) {
    agentWorkspaceOptionsLoading.value = true
    try {
      const result = await getPaginatedData(agentApi.getWorkspaceList, { page: 1, page_size: 100 })
      workspaceOptionsForAgent.value = Array.isArray(result?.items) ? result.items : []
    } catch {
      workspaceOptionsForAgent.value = []
    } finally {
      agentWorkspaceOptionsLoading.value = false
    }
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

async function loadAgentWorkspaceDetail(workspaceId) {
  agentWorkspaceDetail.value = null
  if (!workspaceId) return null

  agentWorkspaceDetailLoading.value = true
  try {
    const res = await agentApi.getWorkspaceDetail(workspaceId)
    agentWorkspaceDetail.value = res?.data ?? null
    return agentWorkspaceDetail.value
  } catch {
    agentWorkspaceDetail.value = null
    ElMessage.error('获取工作区详情失败')
    return null
  } finally {
    agentWorkspaceDetailLoading.value = false
  }
}

const handleAgentWorkspaceChange = async () => {
  const workspaceId = agentFormData.value.workspace_id
  agentFormData.value.prompt_template_id = ''
  agentFormData.value.model_config_id = ''
  agentFormData.value.tools = []
  await loadAgentWorkspaceDetail(workspaceId)
}

const resetAgentForm = () => {
  agentFormData.value = {
    workspace_id: '',
    name: '',
    description: '',
    prompt_template_id: '',
    model_config_id: '',
    llm_config: {},
    tools: []
  }
  agentFormRef.value?.resetFields()
  agentWorkspaceDetail.value = null
}

const editingAgentId = ref(null)

const agentDetailVisible = ref(false)
const agentDetail = ref(null)
const agentDetailLoading = ref(false)

const handleAgentDialogClose = () => {
  agentDialogVisible.value = false
}

const afterAgentDialogClosed = () => {
  editingAgentId.value = null
  resetAgentForm()
}

const handleAgentSubmit = async () => {
  if (!agentFormRef.value) return
  try {
    await agentFormRef.value.validate()
    agentSubmitLoading.value = true
    const payload = {
      workspace_id: agentFormData.value.workspace_id,
      name: agentFormData.value.name,
      description: agentFormData.value.description || undefined,
      prompt_template_id: agentFormData.value.prompt_template_id,
      model_config_id: agentFormData.value.model_config_id,
      llm_config: agentFormData.value.llm_config || {},
      tools: agentFormData.value.tools || []
    }

    if (editingAgentId.value) {
      await agentApi.updateAgent(editingAgentId.value, payload)
      ElMessage.success('修改成功')
    } else {
      await agentApi.createAgent(payload)
      ElMessage.success('新增成功')
    }
    handleAgentDialogClose()
    agentPagination.value.page = 1
    fetchAgentList()
    fetchStatistics()
  } catch (e) {
    if (e !== false) console.error(editingAgentId.value ? '修改分析引擎失败:' : '新增分析引擎失败:', e)
  } finally {
    agentSubmitLoading.value = false
  }
}

const openAgentDialog = () => {
  editingAgentId.value = null
  agentDialogVisible.value = true
}

const openAgentDetail = async (item) => {
  const id = item?.id
  if (!id) return
  agentDetailVisible.value = true
  agentDetail.value = null
  agentDetailLoading.value = true
  try {
    const res = await agentApi.getAgentDetail(id)
    agentDetail.value = res?.data ?? null
  } catch (e) {
    ElMessage.error('获取分析引擎详情失败')
    agentDetailVisible.value = false
  } finally {
    agentDetailLoading.value = false
  }
}

const openAgentEdit = async (item) => {
  const id = item?.id
  if (!id) return
  editingAgentId.value = id
  agentDialogVisible.value = true
  resetAgentForm()
  agentSubmitLoading.value = true
  try {
    await loadAgentDialogOptions()
    const res = await agentApi.getAgentDetail(id)
    const d = res?.data
    if (!d) throw new Error('empty agent detail')

    agentFormData.value = {
      workspace_id: d.workspace_id ?? '',
      name: d.name ?? '',
      description: d.description ?? '',
      prompt_template_id: d.prompt_template_id ?? '',
      model_config_id: d.model_config_id ?? '',
      llm_config: d.llm_config && typeof d.llm_config === 'object' ? d.llm_config : {},
      tools: Array.isArray(d.tools) ? d.tools : []
    }

    if (agentFormData.value.workspace_id) {
      await loadAgentWorkspaceDetail(agentFormData.value.workspace_id)
      const allowedTools = allowedToolNameSet.value
      agentFormData.value.tools = (agentFormData.value.tools || []).filter((t) => allowedTools.has(t))
      if (agentFormData.value.prompt_template_id && !allowedPromptTemplateIdSet.value.has(agentFormData.value.prompt_template_id)) {
        agentFormData.value.prompt_template_id = ''
      }
      if (agentFormData.value.model_config_id && !allowedModelConfigIdSet.value.has(agentFormData.value.model_config_id)) {
        agentFormData.value.model_config_id = ''
      }
    }
  } catch (e) {
    ElMessage.error('获取分析引擎详情失败')
    agentDialogVisible.value = false
    editingAgentId.value = null
  } finally {
    agentSubmitLoading.value = false
  }
}

const handleDeleteAgent = (item) => {
  const id = item?.id
  const name = item?.name || id
  if (!id) return
  ElMessageBox.confirm(
    `确定要删除分析引擎“${name}”吗？运行中可能无法删除。`,
    '确认删除',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
    .then(async () => {
      await agentApi.deleteAgent(id)
      ElMessage.success('删除成功')
      if (agentList.value.length === 1 && agentPagination.value.page > 1) {
        agentPagination.value.page -= 1
      }
      fetchAgentList()
      fetchStatistics()
    })
    .catch(() => {})
}

const openWorkspaceCreate = () => {
  editingWorkspaceId.value = null
  workspaceDialogVisible.value = true
  resetWorkspaceForm()
}

const openWorkspaceDetail = async (item) => {
  const id = item?.id
  if (!id) return
  workspaceDetailVisible.value = true
  workspaceDetail.value = null
  workspaceDetailLoading.value = true
  try {
    const res = await agentApi.getWorkspaceDetail(id)
    workspaceDetail.value = res?.data ?? null
  } catch (e) {
    ElMessage.error('获取工作区详情失败')
    workspaceDetailVisible.value = false
  } finally {
    workspaceDetailLoading.value = false
  }
}

const openWorkspaceEdit = async (item) => {
  const id = item?.id
  if (!id) return
  editingWorkspaceId.value = id
  workspaceDialogVisible.value = true
  resetWorkspaceForm()
  workspaceSubmitLoading.value = true
  try {
    await loadWorkspaceDialogOptions()
    const res = await agentApi.getWorkspaceDetail(id)
    const d = res?.data
    if (d) {
      workspaceFormData.value = {
        name: d.name ?? '',
        description: d.description ?? '',
        model_config_ids: Array.isArray(d.model_config_ids) ? d.model_config_ids : [],
        prompt_template_ids: Array.isArray(d.prompt_template_ids) ? d.prompt_template_ids : [],
        enabled_tools: Array.isArray(d.enabled_tools) ? d.enabled_tools : []
      }
    }
  } catch (e) {
    ElMessage.error('获取工作区详情失败')
    workspaceDialogVisible.value = false
    editingWorkspaceId.value = null
  } finally {
    workspaceSubmitLoading.value = false
  }
}

const handleWorkspaceSubmit = async () => {
  if (!workspaceFormRef.value) return
  try {
    await workspaceFormRef.value.validate()
    workspaceSubmitLoading.value = true
    const payload = {
      name: (workspaceFormData.value.name || '').trim(),
      description: workspaceFormData.value.description || undefined,
      model_config_ids: workspaceFormData.value.model_config_ids || [],
      prompt_template_ids: workspaceFormData.value.prompt_template_ids || [],
      enabled_tools: workspaceFormData.value.enabled_tools || []
    }
    if (editingWorkspaceId.value) {
      await agentApi.updateWorkspace(editingWorkspaceId.value, payload)
      ElMessage.success('修改成功')
    } else {
      await agentApi.createWorkspace(payload)
      ElMessage.success('新增成功')
    }
    handleWorkspaceDialogClose()
    workspacePagination.value.page = 1
    fetchWorkspaceList()
  } catch (e) {
    if (e !== false) console.error(editingWorkspaceId.value ? '修改工作区失败:' : '新增工作区失败:', e)
  } finally {
    workspaceSubmitLoading.value = false
  }
}

const handleDeleteWorkspace = (item) => {
  const id = item?.id
  const name = item?.name || id
  if (!id) return

  ElMessageBox.confirm(
    `确定要删除工作区“${name}”吗？删除前请确保该工作区下已无分析引擎。`,
    '确认删除',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
    .then(async () => {
      await agentApi.deleteWorkspace(id)
      ElMessage.success('删除成功')
      if (workspaceList.value.length === 1 && workspacePagination.value.page > 1) {
        workspacePagination.value.page -= 1
      }
      fetchWorkspaceList()
    })
    .catch(() => {})
}

const handleAdd = () => {
  if (activeTab.value === 'analysisEngines') {
    openAgentDialog()
  } else if (activeTab.value === 'modelResources') {
    modelDialogVisible.value = true
  } else if (activeTab.value === 'promptTemplates') {
    editingPromptTemplateId.value = null
    promptTemplateFormData.value = { name: '', description: '', system_prompt: DEFAULT_SYSTEM_PROMPT_TEMPLATE, user_prompt: DEFAULT_USER_PROMPT_TEMPLATE }
    promptTemplateActiveTab.value = 'system_prompt'
    promptTemplateDialogVisible.value = true
  } else if (activeTab.value === 'workspaces') {
    openWorkspaceCreate()
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
    fetchStatistics()
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
const editingPromptTemplateId = ref(null)
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

const promptTemplateDetailVisible = ref(false)
const promptTemplateDetail = ref(null)
const promptTemplateDetailLoading = ref(false)
const promptTemplateDetailActiveTab = ref('system_prompt')

const openPromptTemplateDetail = async (item) => {
  if (!item?.id) return
  promptTemplateDetailVisible.value = true
  promptTemplateDetail.value = null
  promptTemplateDetailActiveTab.value = 'system_prompt'
  promptTemplateDetailLoading.value = true
  try {
    const res = await agentApi.getPromptTemplateDetail(item.id)
    promptTemplateDetail.value = res?.data ?? null
  } catch (e) {
    ElMessage.error('获取详情失败')
  } finally {
    promptTemplateDetailLoading.value = false
  }
}

const openPromptTemplateEdit = async (item) => {
  if (!item?.id) return
  editingPromptTemplateId.value = item.id
  promptTemplateDialogVisible.value = true
  promptTemplateActiveTab.value = 'system_prompt'
  promptTemplateFormData.value = { name: '', description: '', system_prompt: '', user_prompt: '' }
  promptTemplateSubmitLoading.value = true
  try {
    const res = await agentApi.getPromptTemplateDetail(item.id)
    const d = res?.data
    if (d) {
      promptTemplateFormData.value = {
        name: d.name ?? '',
        description: d.description ?? '',
        system_prompt: d.system_prompt ?? '',
        user_prompt: d.user_prompt ?? ''
      }
    }
  } catch (e) {
    ElMessage.error('获取模板详情失败')
    promptTemplateDialogVisible.value = false
    editingPromptTemplateId.value = null
  } finally {
    promptTemplateSubmitLoading.value = false
  }
}

const handlePromptTemplateDialogClose = () => {
  promptTemplateDialogVisible.value = false
  editingPromptTemplateId.value = null
  promptTemplateActiveTab.value = 'system_prompt'
  promptTemplateFormRef.value?.resetFields()
  promptTemplateFormData.value = { name: '', description: '', system_prompt: DEFAULT_SYSTEM_PROMPT_TEMPLATE, user_prompt: DEFAULT_USER_PROMPT_TEMPLATE }
}

const handlePromptTemplateSubmit = async () => {
  if (!promptTemplateFormRef.value) return
  try {
    await promptTemplateFormRef.value.validate()
    promptTemplateSubmitLoading.value = true
    const payload = {
      name: promptTemplateFormData.value.name,
      description: promptTemplateFormData.value.description || undefined,
      system_prompt: promptTemplateFormData.value.system_prompt,
      user_prompt: promptTemplateFormData.value.user_prompt
    }
    if (editingPromptTemplateId.value) {
      await agentApi.updatePromptTemplate(editingPromptTemplateId.value, payload)
      ElMessage.success('修改成功')
    } else {
      await agentApi.createPromptTemplate(payload)
      ElMessage.success('新增成功')
    }
    handlePromptTemplateDialogClose()
    promptTemplatePagination.value.page = 1
    fetchPromptTemplateList()
    fetchStatistics()
  } catch (e) {
    if (e !== false) {
      const data = promptTemplateFormData.value
      if (!data.system_prompt?.trim()) promptTemplateActiveTab.value = 'system_prompt'
      else if (!data.user_prompt?.trim()) promptTemplateActiveTab.value = 'user_prompt'
      console.error(editingPromptTemplateId.value ? '修改提示词模板失败:' : '新增提示词模板失败:', e)
    }
  } finally {
    promptTemplateSubmitLoading.value = false
  }
}

const handleAction = (action, name) => {
  ElMessage.info(`功能开发中：${action} ${name}`)
}
</script>
