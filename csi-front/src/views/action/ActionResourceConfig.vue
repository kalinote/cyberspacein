<template>
  <div class="h-screen flex flex-col bg-gray-50">
    <Header />
    
    <section class="bg-linear-to-br from-blue-50 to-white py-6 border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-6">
            <el-button type="primary" link @click="$router.back()" class="shrink-0">
              <template #icon>
                <Icon icon="mdi:arrow-left" />
              </template>
              返回
            </el-button>
            <div class="border-l border-gray-300 h-8"></div>
            <div>
              <h1 class="text-2xl font-bold text-gray-900 mb-1">
                <span class="text-blue-500">行动资源</span>配置中心
              </h1>
              <p class="text-sm text-gray-600">统一管理行动资源，包括代理网络、账号、容器和行动节点</p>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <div class="bg-white rounded-lg px-4 py-2 shadow-sm border border-blue-100 flex items-center gap-3">
              <Icon icon="mdi:chart-tree" class="text-blue-600 text-xl" />
              <div>
                <p class="text-xs text-gray-500">行动节点</p>
                <p class="text-lg font-bold text-gray-900">{{ nodeList.length }}</p>
              </div>
            </div>
            <div class="bg-white rounded-lg px-4 py-2 shadow-sm border border-green-100 flex items-center gap-3">
              <Icon icon="mdi:cog" class="text-green-600 text-xl" />
              <div>
                <p class="text-xs text-gray-500">基础组件</p>
                <p class="text-lg font-bold text-gray-900">{{ componentList.length }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div class="flex-1 flex overflow-hidden">
      <div class="bg-white w-72 border-r border-gray-200 shrink-0 overflow-y-auto">
        <div class="p-4">
          <h3 class="text-sm font-semibold text-gray-500 uppercase mb-3">资源类型</h3>
          <div class="space-y-1">
            <template v-for="tab in resourceTabs" :key="tab.key">
              <div
                class="flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer transition-all"
                :class="activeTab === tab.key 
                  ? 'bg-blue-50 text-blue-600 font-medium shadow-sm border border-blue-200' 
                  : 'text-gray-600 hover:bg-gray-50'"
                @click="activeTab = tab.key"
              >
                <Icon 
                  v-if="tab.children && tab.children.length > 0"
                  :icon="expandedTabs.has(tab.key) ? 'mdi:chevron-down' : 'mdi:chevron-right'"
                  class="text-sm cursor-pointer shrink-0"
                  @click.stop="toggleExpand(tab.key)"
                />
                <span v-else class="w-5"></span>
                <Icon :icon="tab.icon" class="text-xl shrink-0" />
                <span>{{ tab.label }}</span>
                <span 
                  class="ml-auto text-xs px-2 py-0.5 rounded-full"
                  :class="activeTab === tab.key ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'"
                >
                  {{ getResourceCount(tab.key) }}
                </span>
              </div>
              <div v-if="tab.children && tab.children.length > 0 && expandedTabs.has(tab.key)" class="ml-4 space-y-1">
                <div
                  v-for="child in tab.children"
                  :key="child.key"
                  class="flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer transition-all"
                  :class="activeTab === child.key 
                    ? 'bg-blue-50 text-blue-600 font-medium shadow-sm border border-blue-200' 
                    : 'text-gray-600 hover:bg-gray-50'"
                  @click="activeTab = child.key"
                >
                  <span class="w-5"></span>
                  <Icon :icon="child.icon" class="text-xl shrink-0" />
                  <span>{{ child.label }}</span>
                  <span 
                    class="ml-auto text-xs px-2 py-0.5 rounded-full"
                    :class="activeTab === child.key ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'"
                  >
                    {{ getResourceCount(child.key) }}
                  </span>
                </div>
              </div>
            </template>
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
              placeholder="搜索资源..."
              clearable
              class="w-64"
            >
              <template #prefix>
                <Icon icon="mdi:magnify" class="text-gray-400" />
              </template>
            </el-input>
            <el-button type="primary" @click="handleAdd(activeTab)">
              <template #icon>
                <Icon icon="mdi:plus" />
              </template>
              新增{{ getCurrentTabLabel() }}
            </el-button>
          </div>
        </div>

        <div class="flex-1 overflow-auto p-6">
          <!-- 节点列表 -->
          <div v-if="activeTab === 'nodes'" class="space-y-4">
            <div v-loading="loading" :element-loading-text="'加载中...'" class="min-h-[200px]">
              <div
                v-for="(node, index) in filteredNodeList"
                :key="index"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
              <div class="flex items-start justify-between">
                <div class="flex items-start gap-4 flex-1">
                  <div 
                    class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                    :class="getNodeBgClass(node)"
                  >
                    <div 
                      class="w-6 h-6 rounded-full"
                      :class="getNodeColorClass(node)"
                    ></div>
                  </div>
                  <div class="flex-1">
                    <div class="flex items-center gap-3 mb-2">
                      <h3 class="text-lg font-bold text-gray-900">{{ node.name }}</h3>
                      <el-tag 
                        size="small"
                        class="border-0"
                        :class="getNodeTagClass(node)"
                      >
                        {{ node.type }}
                      </el-tag>
                      <el-tag size="small" class="border-0">
                        v{{ node.version }}
                      </el-tag>
                    </div>
                    <p class="text-sm text-gray-600 mb-3">{{ node.description }}</p>
                    <div class="flex items-center gap-6 text-sm">
                      <div class="flex items-center gap-2">
                        <Icon icon="mdi:power-plug" class="text-blue-500" />
                        <span class="text-gray-600">接口数量:</span>
                        <span class="font-medium text-gray-900">{{ node.handles?.length || 0 }}</span>
                      </div>
                      <div class="flex items-center gap-2">
                        <Icon icon="mdi:form-textbox" class="text-green-500" />
                        <span class="text-gray-600">输入项:</span>
                        <span class="font-medium text-gray-900">{{ node.inputs?.length || 0 }}</span>
                      </div>
                      <div class="flex items-center gap-2">
                        <Icon icon="mdi:identifier" class="text-purple-500" />
                        <span class="text-gray-600">节点ID:</span>
                        <span class="font-mono text-xs text-gray-900">{{ node.id }}</span>
                      </div>
                      <div class="flex items-center gap-2">
                        <Icon icon="mdi:terminal" class="text-gray-900" />
                        <span class="text-gray-600">运行命令:</span>
                        <span class="font-mono text-xs text-gray-900">{{ node.command }} {{ node.command_args.join(' ') }}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="flex items-center gap-2 ml-4">
                  <el-button type="primary" link @click="handleView(node)">
                    <template #icon>
                      <Icon icon="mdi:eye" />
                    </template>
                    查看
                  </el-button>
                  <el-button type="primary" link @click="handleEdit(node)">
                    <template #icon>
                      <Icon icon="mdi:pencil" />
                    </template>
                    编辑
                  </el-button>
                  <el-button type="danger" link @click="handleDelete(node)">
                    <template #icon>
                      <Icon icon="mdi:delete" />
                    </template>
                    删除
                  </el-button>
                </div>
              </div>
              </div>

              <div v-if="!loading && filteredNodeList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>
          </div>

          <!-- 基础组件列表 -->
          <div v-else-if="activeTab === 'baseComponents'" class="space-y-4">
            <div v-loading="loading" :element-loading-text="'加载中...'" class="min-h-[200px]">
              <div
                v-for="(component, index) in filteredComponentList"
                :key="index"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div 
                      class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                      :class="getComponentStatusBgClass(component.status)"
                    >
                      <Icon 
                        :icon="getComponentStatusIcon(component.status)" 
                        class="text-2xl"
                        :class="getComponentStatusIconClass(component.status)"
                      />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-bold text-gray-900">{{ component.name }}</h3>
                        <el-tag 
                          :type="getComponentStatusTagType(component.status)" 
                          size="small"
                          class="border-0"
                        >
                          {{ getComponentStatusText(component.status) }}
                        </el-tag>
                      </div>
                      <p class="text-sm text-gray-600 mb-3">{{ component.description }}</p>
                      <div class="flex items-center gap-6 text-sm flex-wrap">
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:play-circle" class="text-blue-500" />
                          <span class="text-gray-600">总运行次数:</span>
                          <span class="font-medium text-gray-900">{{ component.total_runs }}</span>
                        </div>
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:clock-outline" class="text-green-500" />
                          <span class="text-gray-600">平均运行时间:</span>
                          <span class="font-medium text-gray-900">{{ component.average_runtime }}秒</span>
                        </div>
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:calendar-clock" class="text-purple-500" />
                          <span class="text-gray-600">最后运行:</span>
                          <span class="font-medium text-gray-900">{{ formatDateTime(component.last_run_at, { defaultValue: '未运行' }) }}</span>
                        </div>
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:identifier" class="text-orange-500" />
                          <span class="text-gray-600">组件ID:</span>
                          <span class="font-mono text-xs text-gray-900">{{ component.id }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 ml-4">
                    <el-button type="primary" link @click="handleView(component)">
                      <template #icon>
                        <Icon icon="mdi:eye" />
                      </template>
                      查看
                    </el-button>
                    <el-button type="primary" link @click="handleEdit(component)">
                      <template #icon>
                        <Icon icon="mdi:pencil" />
                      </template>
                      编辑
                    </el-button>
                    <el-button 
                      :type="component.status === 'running' ? 'warning' : 'success'" 
                      link 
                      @click="handleRunComponent(component)"
                    >
                      <template #icon>
                        <Icon :icon="component.status === 'running' ? 'mdi:stop' : 'mdi:play'" />
                      </template>
                      {{ component.status === 'running' ? '停止' : '运行' }}
                    </el-button>
                    <el-button type="danger" link @click="handleDelete(component)">
                      <template #icon>
                        <Icon icon="mdi:delete" />
                      </template>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>

              <div v-if="!loading && filteredComponentList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>

            <div v-if="!searchKeyword && componentList.length > 0" class="flex justify-center mt-6">
              <el-pagination
                v-model:current-page="pagination.page"
                v-model:page-size="pagination.pageSize"
                :page-sizes="[10, 20, 50, 100]"
                :total="pagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handlePageChange"
                @size-change="handlePageSizeChange"
              />
            </div>
          </div>

          <!-- 节点接口配置列表 -->
          <div v-else-if="activeTab === 'nodeHandles'" class="space-y-4">
            <div v-loading="loading" :element-loading-text="'加载中...'" class="min-h-[200px]">
              <div
                v-for="(handle, index) in filteredHandleList"
                :key="index"
                class="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-6 mb-4"
              >
                <div class="flex items-start justify-between">
                  <div class="flex items-start gap-4 flex-1">
                    <div 
                      class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-blue-100"
                    >
                      <div 
                        class="w-6 h-6 rounded-full"
                        :style="{ backgroundColor: handle.color || '#409EFF' }"
                      ></div>
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-3 mb-2">
                        <h3 class="text-lg font-bold text-gray-900">{{ handle.label }}</h3>
                        <el-tag 
                          :type="handle.type === 'value' ? 'success' : 'primary'"
                          size="small"
                          class="border-0"
                        >
                          {{ handle.type === 'value' ? '值类型' : '引用类型' }}
                        </el-tag>
                      </div>
                      <p class="text-sm text-gray-600 mb-3">{{ handle.handle_name }}</p>
                      <div class="flex items-center gap-6 text-sm flex-wrap">
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:palette" class="text-blue-500" />
                          <span class="text-gray-600">颜色:</span>
                          <div 
                            class="w-4 h-4 rounded border border-gray-300"
                            :style="{ backgroundColor: handle.color || '#409EFF' }"
                          ></div>
                          <span class="font-mono text-xs text-gray-900">{{ handle.color || '#409EFF' }}</span>
                        </div>
                        <div class="flex items-center gap-2">
                          <Icon icon="mdi:identifier" class="text-purple-500" />
                          <span class="text-gray-600">接口ID:</span>
                          <span class="font-mono text-xs text-gray-900">{{ handle.id }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="flex items-center gap-2 ml-4">
                    <el-button type="primary" link @click="handleViewHandle(handle)">
                      <template #icon>
                        <Icon icon="mdi:eye" />
                      </template>
                      查看
                    </el-button>
                    <el-button type="primary" link @click="handleEditHandle(handle)">
                      <template #icon>
                        <Icon icon="mdi:pencil" />
                      </template>
                      编辑
                    </el-button>
                    <el-button type="danger" link @click="handleDeleteHandle(handle)">
                      <template #icon>
                        <Icon icon="mdi:delete" />
                      </template>
                      删除
                    </el-button>
                  </div>
                </div>
              </div>

              <div v-if="!loading && filteredHandleList.length === 0" class="flex flex-col items-center justify-center py-16">
                <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
                <p class="text-gray-500">暂无数据</p>
              </div>
            </div>

            <div v-if="!searchKeyword && handleList.length > 0" class="flex justify-center mt-6">
              <el-pagination
                v-model:current-page="handlePagination.page"
                v-model:page-size="handlePagination.pageSize"
                :page-sizes="[10, 20, 50, 100]"
                :total="handlePagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="handleHandlePageChange"
                @size-change="handleHandlePageSizeChange"
              />
            </div>
          </div>

          <div v-else class="flex flex-col items-center justify-center py-16">
            <Icon icon="mdi:wrench" class="text-6xl text-gray-300 mb-4" />
            <p class="text-gray-500 text-lg mb-2">功能开发中</p>
            <p class="text-gray-400 text-sm">{{ getCurrentTabLabel() }}管理功能即将上线</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 新增行动节点弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      title="新增行动节点"
      width="900px"
      :close-on-click-modal="false"
      @open="handleDialogOpen"
      @close="handleDialogClose"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="120px"
        class="max-h-[70vh] overflow-y-auto pr-2"
      >
        <!-- 基础字段 -->
        <div class="mb-6">
          <h3 class="text-lg font-semibold text-gray-800 mb-4 pb-2 border-b border-gray-200">基础信息</h3>
          <el-form-item label="节点名称" prop="name">
            <el-input v-model="formData.name" placeholder="请输入节点名称" />
          </el-form-item>
          <el-form-item label="节点描述" prop="description">
            <el-input
              v-model="formData.description"
              type="textarea"
              :rows="3"
              placeholder="请输入节点类型描述"
            />
          </el-form-item>
          <el-form-item label="节点类型" prop="type">
            <el-select v-model="formData.type" placeholder="请选择节点类型" class="w-full">
              <!-- TODO: 通过接口获取 -->
              <el-option label="构造器" value="construct" />
              <el-option label="采集节点" value="crawler" />
              <el-option label="存储节点" value="storage" />
              <el-option label="中间件节点" value="middleware" />
              <el-option label="处理器节点" value="processor" />
              <el-option label="基本逻辑节点" value="logic" />
              <el-option label="简单运算节点" value="simple_operation" />
              <el-option label="输出节点" value="output" />
              <el-option label="输入节点" value="input" />
            </el-select>
          </el-form-item>
          <el-form-item label="版本号" prop="version">
            <el-input v-model="formData.version" placeholder="请输入版本号" />
          </el-form-item>
          <el-form-item label="关联组件" prop="related_components">
            <el-select
              v-model="formData.related_components"
              multiple
              placeholder="请选择关联组件"
              class="w-full"
              :loading="componentsLoading"
            >
              <el-option
                v-for="component in componentListForSelect"
                :key="component.id"
                :label="component.name"
                :value="component.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="运行命令" prop="command">
            <el-input v-model="formData.command" placeholder="请输入运行命令" />
          </el-form-item>
          <el-form-item label="运行参数" prop="command_args">
            <TagInput
              v-model="formData.command_args"
              placeholder="输入参数后按回车或点击添加"
              :show-count="true"
            />
          </el-form-item>
          <el-form-item label="默认配置" prop="default_configs">
            <KeyValueEditor v-model="formData.default_configs" />
          </el-form-item>
        </div>

        <!-- Handles -->
        <div class="mb-6">
          <div class="flex items-center justify-between mb-4 pb-2 border-b border-gray-200">
            <h3 class="text-lg font-semibold text-gray-800">接口配置</h3>
            <el-button type="primary" size="small" @click="addHandle">
              <template #icon>
                <Icon icon="mdi:plus" />
              </template>
              添加接口
            </el-button>
          </div>
          <div v-if="formData.handles.length === 0" class="text-center py-8 text-gray-400">
            <p>暂无接口配置，请点击上方按钮添加</p>
          </div>
          <div v-for="(handle, index) in formData.handles" :key="index" class="mb-4 p-4 border border-gray-200 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors">
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm font-medium text-gray-700">接口 #{{ index + 1 }}</span>
              <el-button type="danger" size="small" link @click="removeHandle(index)">
                <template #icon>
                  <Icon icon="mdi:delete" />
                </template>
                删除
              </el-button>
            </div>
            <el-form-item label="接口" :prop="`handles.${index}.id`" :rules="handleRules.id">
              <el-select 
                v-model="handle.id" 
                placeholder="请选择接口" 
                class="w-full"
                :loading="nodeHandlesLoading"
              >
                <el-option
                  v-for="nodeHandle in nodeHandlesForSelect"
                  :key="nodeHandle.id"
                  :label="nodeHandle.label"
                  :value="nodeHandle.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="类型" :prop="`handles.${index}.type`" :rules="handleRules.type">
              <el-select v-model="handle.type" placeholder="请选择接口类型" class="w-full">
                <el-option label="输出接口" value="source" />
                <el-option label="输入接口" value="target" />
              </el-select>
            </el-form-item>
            <el-form-item label="重新命名" :prop="`handles.${index}.relabel`">
              <el-input v-model="handle.relabel" placeholder="请输入重新命名（可选）" />
            </el-form-item>
            <el-form-item label="位置" :prop="`handles.${index}.position`" :rules="handleRules.position">
              <el-select v-model="handle.position" placeholder="请选择位置" class="w-full">
                <el-option label="left" value="left" />
                <el-option label="right" value="right" />
                <el-option label="top" value="top" />
                <el-option label="bottom" value="bottom" />
              </el-select>
            </el-form-item>
            <el-form-item label="自定义样式">
              <KeyValueEditor v-model="handle.custom_style" />
            </el-form-item>
          </div>
        </div>

        <!-- Inputs -->
        <div class="mb-6">
          <div class="flex items-center justify-between mb-4 pb-2 border-b border-gray-200">
            <h3 class="text-lg font-semibold text-gray-800">输入项配置</h3>
            <el-button type="primary" size="small" @click="addInput">
              <template #icon>
                <Icon icon="mdi:plus" />
              </template>
              添加输入项
            </el-button>
          </div>
          <div v-if="formData.inputs.length === 0" class="text-center py-8 text-gray-400">
            <p>暂无输入项配置，请点击上方按钮添加</p>
          </div>
          <div v-for="(input, index) in formData.inputs" :key="index" class="mb-4 p-4 border border-gray-200 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors">
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm font-medium text-gray-700">输入项 #{{ index + 1 }}</span>
              <el-button type="danger" size="small" link @click="removeInput(index)">
                <template #icon>
                  <Icon icon="mdi:delete" />
                </template>
                删除
              </el-button>
            </div>
            <el-form-item label="输入项名称" :prop="`inputs.${index}.name`" :rules="inputRules.name">
              <el-input v-model="input.name" placeholder="请输入输入项名称，必须是英文字母开头，只能包含字母、数字和下划线" />
            </el-form-item>
            <el-form-item :label="`输入类型`" :prop="`inputs.${index}.type`" :rules="inputRules.type">
              <el-select v-model="input.type" placeholder="请选择输入类型" class="w-full">
                <el-option
                  v-for="inputType in inputTypes"
                  :key="inputType"
                  :label="inputType"
                  :value="inputType"
                />
              </el-select>
            </el-form-item>
            <el-form-item :label="`对齐位置`" :prop="`inputs.${index}.position`" :rules="inputRules.position">
              <el-select v-model="input.position" placeholder="请选择对齐位置" class="w-full">
                <el-option label="left" value="left" />
                <el-option label="right" value="right" />
                <el-option label="top" value="top" />
                <el-option label="bottom" value="bottom" />
                <el-option label="center" value="center" />
              </el-select>
            </el-form-item>
            <el-form-item :label="`输入标签`" :prop="`inputs.${index}.label`" :rules="inputRules.label">
              <el-input v-model="input.label" placeholder="请输入输入项标签" />
            </el-form-item>
            <el-form-item :label="`输入描述`" :prop="`inputs.${index}.description`">
              <el-input
                v-model="input.description"
                type="textarea"
                :rows="2"
                placeholder="请输入输入项描述"
              />
            </el-form-item>
            <el-form-item :label="`是否必填`" :prop="`inputs.${index}.required`">
              <el-switch v-model="input.required" />
            </el-form-item>
            <el-form-item :label="`默认值`" :prop="`inputs.${index}.default`">
              <el-input v-model="input.default" placeholder="请输入默认值" />
            </el-form-item>
            <el-form-item v-if="input.type === 'select'" label="选项">
              <TagInput
                v-model="input.options"
                placeholder="输入选项后按回车或点击添加"
                :show-count="true"
              />
            </el-form-item>
            <el-form-item label="自定义样式">
              <KeyValueEditor v-model="input.custom_style" />
            </el-form-item>
            <el-form-item label="自定义属性">
              <KeyValueEditor v-model="input.custom_props" />
            </el-form-item>
          </div>
        </div>
      </el-form>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 新增节点接口弹窗 -->
    <el-dialog
      v-model="handleDialogVisible"
      title="新增节点接口"
      width="600px"
      :close-on-click-modal="false"
      @open="handleHandleDialogOpen"
      @close="handleHandleDialogClose"
    >
      <el-form
        ref="handleFormRef"
        :model="handleFormData"
        :rules="handleFormRules"
        label-width="120px"
      >
        <el-form-item label="接口名称" prop="handle_name">
          <el-input 
            v-model="handleFormData.handle_name" 
            placeholder="请输入接口名称，必须是英文字母开头，只能包含字母、数字和下划线" 
          />
        </el-form-item>
        <el-form-item label="接口类型" prop="type">
          <el-select v-model="handleFormData.type" placeholder="请选择接口类型" class="w-full">
            <el-option label="值类型" value="value" />
            <el-option label="引用类型" value="reference" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签" prop="label">
          <el-input v-model="handleFormData.label" placeholder="请输入标签" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker 
            v-model="handleFormData.color" 
            format="hex"
            :predefine="[
              '#409EFF',
              '#67C23A',
              '#E6A23C',
              '#F56C6C',
              '#909399'
            ]"
          />
        </el-form-item>
        <el-form-item label="其他兼容接口">
          <el-select
            v-model="handleFormData.other_compatible_interfaces"
            multiple
            placeholder="请选择其他兼容接口"
            class="w-full"
            :loading="allNodeHandlesLoading"
            clearable
          >
            <el-option
              v-for="handle in allNodeHandles"
              :key="handle.id"
              :label="handle.label"
              :value="handle.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="自定义样式">
          <KeyValueEditor v-model="handleFormData.custom_style" />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="flex justify-end gap-3">
          <el-button @click="handleDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmitHandle" :loading="handleSubmitting">确定</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import TagInput from '@/components/action/nodes/components/TagInput.vue'
import KeyValueEditor from '@/components/action/nodes/components/KeyValueEditor.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { actionApi } from '@/api/action'
import { getPaginatedData } from '@/utils/request'
import { INPUT_TYPES, formatDateTime } from '@/utils/action'

const activeTab = ref('nodes')
const searchKeyword = ref('')
const loading = ref(false)
const expandedTabs = ref(new Set(['nodes']))

const dialogVisible = ref(false)
const formRef = ref(null)
const submitting = ref(false)
const componentsLoading = ref(false)
const componentListForSelect = ref([])
const nodeHandlesForSelect = ref([])
const nodeHandlesLoading = ref(false)

const pagination = ref({
  page: 1,
  pageSize: 10,
  total: 0,
  totalPages: 0
})

const resourceTabs = [
  { key: 'nodes', label: '行动节点', icon: 'mdi:chart-tree', children: [
    { key: 'baseComponents', label: '基础组件', icon: 'mdi:cog' },
    { key: 'nodeHandles', label: '节点接口配置', icon: 'mdi:link-variant' }
  ]},
  { key: 'proxy', label: '代理网络', icon: 'mdi:server-network' },
  { key: 'accounts', label: '采集账号', icon: 'mdi:account-key' },
  { key: 'containers', label: '沙盒容器', icon: 'mdi:cube-outline' }
]

const nodeList = ref([])

const componentList = ref([])

const handleList = ref([])
const handlePagination = ref({
  page: 1,
  pageSize: 10,
  total: 0,
  totalPages: 0
})
const handleDialogVisible = ref(false)
const handleFormRef = ref(null)
const handleSubmitting = ref(false)
const allNodeHandles = ref([])
const allNodeHandlesLoading = ref(false)
const handleFormData = ref({
  handle_name: '',
  type: '',
  label: '',
  color: '#409EFF',
  custom_style: {},
  other_compatible_interfaces: []
})

const inputTypes = ref(INPUT_TYPES)

const validateName = (rule, value, callback) => {
  if (!value) {
    callback(new Error('请输入名称'))
  } else if (!/^[a-zA-Z][a-zA-Z0-9_]*$/.test(value)) {
    callback(new Error('名称必须以英文字母开头，只能包含字母、数字和下划线'))
  } else {
    callback()
  }
}

const formData = ref({
  name: '',
  description: '',
  type: '',
  version: '1.0.0',
  command: '',
  command_args: [],
  related_components: [],
  default_configs: {},
  handles: [],
  inputs: []
})

const formRules = {
  name: [
    { required: true, message: '请输入节点名称', trigger: 'blur' }
  ],
  type: [
    { required: true, message: '请选择节点类型', trigger: 'change' }
  ],
  version: [
    { required: true, message: '请输入版本号', trigger: 'blur' }
  ],
  command: [
    { required: true, message: '请输入运行命令', trigger: 'blur' }
  ],
  related_components: [
    { 
      required: true, 
      validator: (rule, value, callback) => {
        if (!value || value.length === 0) {
          callback(new Error('请至少选择一个关联组件'))
        } else {
          callback()
        }
      },
      trigger: 'change' 
    }
  ]
}

const handleRules = {
  id: [
    { required: true, message: '请选择接口', trigger: 'change' }
  ],
  type: [
    { required: true, message: '请选择接口类型', trigger: 'change' }
  ],
  position: [
    { required: true, message: '请选择接口位置', trigger: 'change' }
  ]
}

const inputRules = {
  name: [
    { required: true, validator: validateName, trigger: 'blur' }
  ],
  type: [
    { required: true, message: '请选择输入类型', trigger: 'change' }
  ],
  position: [
    { required: true, message: '请选择对齐位置', trigger: 'change' }
  ],
  label: [
    { required: true, message: '请输入输入项标签', trigger: 'blur' }
  ]
}

const handleFormRules = {
  handle_name: [
    { required: true, validator: validateName, trigger: 'blur' }
  ],
  type: [
    { required: true, message: '请选择接口类型', trigger: 'change' }
  ],
  label: [
    { required: true, message: '请输入标签', trigger: 'blur' }
  ]
}

const filteredNodeList = computed(() => {
  if (!searchKeyword.value.trim()) {
    return nodeList.value
  }
  const keyword = searchKeyword.value.toLowerCase()
  return nodeList.value.filter(node => 
    node.name.toLowerCase().includes(keyword) ||
    node.description.toLowerCase().includes(keyword) ||
    node.id.toLowerCase().includes(keyword) ||
    node.type.toLowerCase().includes(keyword)
  )
})

const filteredComponentList = computed(() => {
  if (!searchKeyword.value.trim()) {
    return componentList.value
  }
  const keyword = searchKeyword.value.toLowerCase()
  return componentList.value.filter(component => 
    component.name.toLowerCase().includes(keyword) ||
    component.description.toLowerCase().includes(keyword) ||
    component.id.toLowerCase().includes(keyword) ||
    component.status.toLowerCase().includes(keyword)
  )
})

const filteredHandleList = computed(() => {
  if (!searchKeyword.value.trim()) {
    return handleList.value
  }
  const keyword = searchKeyword.value.toLowerCase()
  return handleList.value.filter(handle => 
    handle.handle_name?.toLowerCase().includes(keyword) ||
    handle.type?.toLowerCase().includes(keyword) ||
    handle.label?.toLowerCase().includes(keyword) ||
    handle.id?.toLowerCase().includes(keyword)
  )
})

const getCurrentTabIcon = () => {
  for (const tab of resourceTabs) {
    if (tab.key === activeTab.value) {
      return tab.icon || 'mdi:help'
    }
    if (tab.children) {
      const child = tab.children.find(c => c.key === activeTab.value)
      if (child) {
        return child.icon || 'mdi:help'
      }
    }
  }
  return 'mdi:help'
}

const getCurrentTabLabel = () => {
  for (const tab of resourceTabs) {
    if (tab.key === activeTab.value) {
      return tab.label || ''
    }
    if (tab.children) {
      const child = tab.children.find(c => c.key === activeTab.value)
      if (child) {
        return child.label || ''
      }
    }
  }
  return ''
}

const toggleExpand = (tabKey) => {
  if (expandedTabs.value.has(tabKey)) {
    expandedTabs.value.delete(tabKey)
  } else {
    expandedTabs.value.add(tabKey)
  }
}

const getResourceCount = (tabKey) => {
  if (tabKey === 'nodes') {
    return nodeList.value.length
  }
  if (tabKey === 'baseComponents') {
    return componentList.value.length
  }
  if (tabKey === 'nodeHandles') {
    return handleList.value.length
  }
  return 0
}

const nodeTypeColorMap = {
  'construct': { bg: 'bg-blue-100!', color: 'bg-blue-500!', tag: 'bg-blue-100! text-blue-700!' },
  'crawler': { bg: 'bg-green-100!', color: 'bg-green-500!', tag: 'bg-green-100! text-green-700!' },
  'storage': { bg: 'bg-purple-100!', color: 'bg-purple-500!', tag: 'bg-purple-100! text-purple-700!' },
  'middleware': { bg: 'bg-orange-100!', color: 'bg-orange-500!', tag: 'bg-orange-100! text-orange-700!' },
  'processor': { bg: 'bg-red-100!', color: 'bg-red-500!', tag: 'bg-red-100 text-red-700' },
  'logic': { bg: 'bg-indigo-100!', color: 'bg-indigo-500!', tag: 'bg-indigo-100! text-indigo-700!' },
  'simple_operation': { bg: 'bg-yellow-100!', color: 'bg-yellow-500!', tag: 'bg-yellow-100! text-yellow-700!' },
  'output': { bg: 'bg-teal-100!', color: 'bg-teal-500!', tag: 'bg-teal-100! text-teal-700!' },
  'input': { bg: 'bg-pink-100!', color: 'bg-pink-500!', tag: 'bg-pink-100! text-pink-700!' }
}

const getNodeColorClass = (node) => {
  if (!node || !node.type) return 'bg-gray-400'
  return nodeTypeColorMap[node.type]?.color || 'bg-gray-400'
}

const getNodeBgClass = (node) => {
  if (!node || !node.type) return 'bg-gray-100'
  return nodeTypeColorMap[node.type]?.bg || 'bg-gray-100'
}

const getNodeTagClass = (node) => {
  if (!node || !node.type) return 'bg-gray-100! text-gray-700!'
  return nodeTypeColorMap[node.type]?.tag || 'bg-gray-100! text-gray-700!'
}

const handleAdd = (tabKey) => {
  if (tabKey === 'baseComponents') {
    // TODO: 从新tab跳转到crawlab对应页面
    ElMessage.warning('基础组件不能通过此方式新增')
    return
  }
  if (tabKey === 'nodes') {
    dialogVisible.value = true
  } else if (tabKey === 'nodeHandles') {
    handleDialogVisible.value = true
  } else {
    ElMessage.info(`新增${tabKey}功能开发中`)
  }
}

const handleDialogOpen = async () => {
  resetForm()
  await Promise.all([
    fetchComponentsForSelect(),
    fetchNodeHandlesForSelect()
  ])
}

const handleDialogClose = () => {
  resetForm()
}

const resetForm = () => {
  formData.value = {
    name: '',
    description: '',
    type: '',
    version: '1.0.0',
    command: '',
    command_args: [],
    related_components: [],
    default_configs: {},
    handles: [],
    inputs: []
  }
  if (formRef.value) {
    formRef.value.clearValidate()
  }
}

const fetchNodeHandlesForSelect = async () => {
  nodeHandlesLoading.value = true
  try {
    const response = await actionApi.getAllNodeHandles()
    if (response.code === 0) {
      nodeHandlesForSelect.value = response.data || []
    } else {
      ElMessage.error(`获取节点接口列表失败: ${response.message}`)
      nodeHandlesForSelect.value = []
    }
  } catch (error) {
    ElMessage.error('获取节点接口列表失败')
    nodeHandlesForSelect.value = []
  } finally {
    nodeHandlesLoading.value = false
  }
}

const fetchComponentsForSelect = async () => {
  componentsLoading.value = true
  try {
    const result = await getPaginatedData(
      actionApi.getBaseComponents,
      {
        page: 1,
        page_size: 20
      }
    )
    componentListForSelect.value = result.items || []
  } catch (error) {
    ElMessage.error('获取基础组件列表失败')
    componentListForSelect.value = []
  } finally {
    componentsLoading.value = false
  }
}

const addHandle = () => {
  formData.value.handles.push({
    id: '',
    type: '',
    relabel: '',
    position: '',
    custom_style: {}
  })
}

const removeHandle = (index) => {
  formData.value.handles.splice(index, 1)
}

const addInput = () => {
  formData.value.inputs.push({
    name: '',
    type: '',
    position: 'center',
    label: '',
    description: '',
    required: false,
    default: '',
    options: [],
    custom_style: {},
    custom_props: {}
  })
}

const removeInput = (index) => {
  formData.value.inputs.splice(index, 1)
}

const handleSubmit = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
    
    submitting.value = true
    
    const submitData = {
      name: formData.value.name,
      description: formData.value.description || '',
      type: formData.value.type,
      version: formData.value.version,
      command: formData.value.command || '',
      command_args: formData.value.command_args || [],
      related_components: formData.value.related_components || [],
      default_configs: formData.value.default_configs || {},
      handles: formData.value.handles.map(handle => {
        const handleData = {
          id: handle.id,
          type: handle.type,
          position: handle.position
        }
        if (handle.relabel && handle.relabel.trim()) {
          handleData.relabel = handle.relabel.trim()
        }
        if (handle.custom_style && Object.keys(handle.custom_style).length > 0) {
          handleData.custom_style = handle.custom_style
        }
        return handleData
      }),
      inputs: formData.value.inputs.map(input => {
        const inputData = {
          name: input.name,
          type: input.type,
          position: input.position,
          label: input.label,
          description: input.description || '',
          required: input.required || false,
          default: input.default || '',
          custom_style: input.custom_style || {},
          custom_props: input.custom_props || {}
        }
        if (input.type === 'select' && input.options && input.options.length > 0) {
          inputData.options = input.options
        }
        return inputData
      })
    }
    
    const response = await actionApi.createNode(submitData)
    
    if (response.code === 0) {
      ElMessage.success('新增行动节点成功')
      dialogVisible.value = false
      await fetchNodeList()
    } else {
      ElMessage.error(`新增行动节点失败: ${response.message}`)
    }
  } catch (error) {
    ElMessage.error(`新增行动节点失败: ${error.message}`)
  } finally {
    submitting.value = false
  } 
}

const handleView = (node) => {
  ElMessage.info(`查看节点: ${node.name}`)
}

const handleEdit = (node) => {
  ElMessage.info(`编辑节点: ${node.name}`)
}

const handleDelete = (item) => {
  const itemType = item.handles ? '节点' : '组件'
  ElMessageBox.confirm(
    `确定要删除${itemType}"${item.name}"吗？此操作不可恢复。`,
    '确认删除',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
    .then(() => {
      ElMessage.success(`已删除${itemType}: ${item.name}`)
    })
    .catch(() => {
      ElMessage.info('已取消删除')
    })
}

const getComponentStatusText = (status) => {
  const statusMap = {
    'finished': '成功',
    'running': '运行中',
    'error': '失败',
    'unknown': '未知'
  }
  return statusMap[status] || status
}

const getComponentStatusTagType = (status) => {
  const typeMap = {
    'finished': 'success',
    'running': 'primary',
    'error': 'danger',
    'unknown': 'info'
  }
  return typeMap[status] || ''
}

const getComponentStatusIcon = (status) => {
  const iconMap = {
    'finished': 'mdi:check-circle',
    'running': 'mdi:loading',
    'error': 'mdi:alert-circle',
    'unknown': 'mdi:clock-outline'
  }
  return iconMap[status] || 'mdi:help-circle'
}

const getComponentStatusIconClass = (status) => {
  const classMap = {
    'finished': 'text-green-600',
    'running': 'text-blue-600',
    'error': 'text-red-600',
    'unknown': 'text-gray-600'
  }
  return classMap[status] || 'text-gray-600'
}

const getComponentStatusBgClass = (status) => {
  const classMap = {
    'finished': 'bg-green-100',
    'running': 'bg-blue-100',
    'error': 'bg-red-100',
    'unknown': 'bg-gray-100'
  }
  return classMap[status] || 'bg-gray-100'
}


const handleRunComponent = (component) => {
  if (component.status === 'running') {
    ElMessage.info(`停止组件: ${component.name}`)
  } else {
    ElMessage.info(`运行组件: ${component.name}`)
  }
}

const fetchNodeList = async () => {
  loading.value = true
  try {
    const response = await actionApi.getNodes()
    if (response.code === 0) {
      nodeList.value = response.data || []
    } else {
      ElMessage.error(`获取行动节点列表失败: ${response.message}`)
      nodeList.value = []
    }
  } catch (error) {
    ElMessage.error('获取行动节点列表失败')
    nodeList.value = []
  } finally {
    loading.value = false
  }
}

const fetchComponentList = async () => {
  loading.value = true
  try {
    const result = await getPaginatedData(
      actionApi.getBaseComponents,
      {
        page: pagination.value.page,
        page_size: pagination.value.pageSize
      }
    )
    
    componentList.value = result.items
    pagination.value = {
      ...pagination.value,
      ...result.pagination
    }
    
    // console.log('获取基础组件列表成功:', result)
  } catch (error) {
    // console.error('获取基础组件列表失败:', error)
    ElMessage.error('获取基础组件列表失败')
  } finally {
    loading.value = false
  }
}

const handlePageChange = (page) => {
  pagination.value.page = page
  fetchComponentList()
}

const handlePageSizeChange = (pageSize) => {
  pagination.value.pageSize = pageSize
  pagination.value.page = 1
  fetchComponentList()
}

const fetchHandleList = async () => {
  loading.value = true
  try {
    const result = await getPaginatedData(
      actionApi.getNodeHandles,
      {
        page: handlePagination.value.page,
        page_size: handlePagination.value.pageSize
      }
    )
    
    handleList.value = result.items
    handlePagination.value = {
      ...handlePagination.value,
      ...result.pagination
    }
  } catch (error) {
    ElMessage.error('获取节点接口列表失败')
    handleList.value = []
  } finally {
    loading.value = false
  }
}

const handleHandlePageChange = (page) => {
  handlePagination.value.page = page
  fetchHandleList()
}

const handleHandlePageSizeChange = (pageSize) => {
  handlePagination.value.pageSize = pageSize
  handlePagination.value.page = 1
  fetchHandleList()
}

const fetchAllNodeHandles = async () => {
  allNodeHandlesLoading.value = true
  try {
    const response = await actionApi.getAllNodeHandles()
    if (response.code === 0) {
      allNodeHandles.value = response.data || []
    } else {
      ElMessage.error(`获取节点接口选项失败: ${response.message}`)
      allNodeHandles.value = []
    }
  } catch (error) {
    ElMessage.error('获取节点接口选项失败')
    allNodeHandles.value = []
  } finally {
    allNodeHandlesLoading.value = false
  }
}

const resetHandleForm = () => {
  handleFormData.value = {
    handle_name: '',
    type: '',
    label: '',
    color: '#409EFF',
    custom_style: {},
    other_compatible_interfaces: []
  }
  if (handleFormRef.value) {
    handleFormRef.value.clearValidate()
  }
}

const handleHandleDialogOpen = async () => {
  resetHandleForm()
  await fetchAllNodeHandles()
}

const handleHandleDialogClose = () => {
  resetHandleForm()
}

const handleSubmitHandle = async () => {
  if (!handleFormRef.value) return
  
  try {
    await handleFormRef.value.validate()
    
    handleSubmitting.value = true
    
    const submitData = {
      handle_name: handleFormData.value.handle_name,
      type: handleFormData.value.type,
      label: handleFormData.value.label
    }
    
    if (handleFormData.value.color) {
      submitData.color = handleFormData.value.color
    }
    
    if (handleFormData.value.custom_style && Object.keys(handleFormData.value.custom_style).length > 0) {
      submitData.custom_style = handleFormData.value.custom_style
    }
    
    if (Array.isArray(handleFormData.value.other_compatible_interfaces)) {
      submitData.other_compatible_interfaces = handleFormData.value.other_compatible_interfaces
    } else {
      submitData.other_compatible_interfaces = []
    }
    
    const response = await actionApi.createNodeHandle(submitData)
    
    if (response.code === 0) {
      ElMessage.success('新增节点接口成功')
      handleDialogVisible.value = false
      await fetchHandleList()
    } else {
      ElMessage.error(`新增节点接口失败: ${response.message}`)
    }
  } catch (error) {
    ElMessage.error(`新增节点接口失败: ${error.message}`)
  } finally {
    handleSubmitting.value = false
  }
}

const handleViewHandle = (handle) => {
  ElMessage.info(`查看接口: ${handle.handle_name}`)
}

const handleEditHandle = (handle) => {
  ElMessage.info(`编辑接口: ${handle.handle_name}`)
}

const handleDeleteHandle = (handle) => {
  ElMessage.info(`删除接口: ${handle.handle_name}`)
}

watch(activeTab, (newTab) => {
  if (newTab === 'nodeHandles') {
    fetchHandleList()
  } else if (newTab === 'baseComponents') {
    fetchComponentList()
  }
})

onMounted(() => {
  fetchNodeList()
  if (activeTab.value === 'baseComponents') {
    fetchComponentList()
  } else if (activeTab.value === 'nodeHandles') {
    fetchHandleList()
  }
})
</script>
