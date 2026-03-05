<template>
  <div class="min-h-screen bg-gray-50">
    <Header />

    <FunctionalPageHeader
      title-prefix="基础组件"
      title-suffix="配置管理"
      subtitle="管理基础组件独立运行的任务配置，供组件 SDK 启动时拉取使用"
    >
      <template #actions>
        <div class="flex items-center gap-3">
          <div class="bg-white rounded-lg px-4 py-2 shadow-sm border border-blue-100 flex items-center gap-3">
            <Icon icon="mdi:cog-outline" class="text-blue-600 text-xl" />
            <div>
              <p class="text-xs text-gray-500">配置总数</p>
              <p class="text-lg font-bold text-gray-900">{{ total }}</p>
            </div>
          </div>
        </div>
      </template>
    </FunctionalPageHeader>

    <div class="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- 筛选栏 -->
      <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-200 mb-6">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">搜索配置</label>
            <el-input
              v-model="filterParams.keyword"
              placeholder="配置名称、描述或 node_instance_id..."
              clearable
              @input="handleSearch"
            >
              <template #prefix>
                <Icon icon="mdi:magnify" class="text-gray-400" />
              </template>
            </el-input>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">组件类型</label>
            <el-select
              v-model="filterParams.component_type"
              placeholder="全部类型"
              clearable
              class="w-full"
              @change="handleSearch"
            >
              <el-option label="全部类型" value="" />
              <el-option label="采集器" value="crawler" />
              <el-option label="分析器" value="analyzer" />
              <el-option label="报告生成器" value="reporter" />
              <el-option label="自定义" value="custom" />
            </el-select>
          </div>
          <div class="md:col-span-2 flex items-end justify-end">
            <el-button type="primary" @click="handleCreate">
              <template #icon><Icon icon="mdi:plus" /></template>
              新建配置
            </el-button>
          </div>
        </div>
      </div>

      <!-- 配置卡片网格 -->
      <div v-loading="loading" class="min-h-[200px]">
        <div v-if="configList.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-6">
          <div
            v-for="config in configList"
            :key="config.id"
            class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100 hover:shadow-xl transition-all hover:border-blue-300"
          >
            <div class="flex items-start justify-between mb-4">
              <div class="flex-1 min-w-0">
                <h3 class="text-lg font-bold text-gray-900 mb-1 truncate">{{ config.name }}</h3>
                <p class="text-sm text-gray-500 line-clamp-2">{{ config.description || '暂无描述' }}</p>
              </div>
              <el-tag class="ml-2 shrink-0" size="small" type="primary">
                {{ getComponentTypeLabel(config.type) }}
              </el-tag>
            </div>

            <div class="space-y-2 mb-4 text-sm">
              <div class="flex items-center gap-2">
                <Icon icon="mdi:identifier" class="text-blue-500 shrink-0" />
                <span class="text-gray-500 shrink-0">node_instance_id:</span>
                <span class="font-mono text-gray-800 truncate">{{ config.config_data?.meta?.node_instance_id }}</span>
              </div>
              <div class="flex items-center gap-2">
                <Icon icon="mdi:lightning-bolt" class="text-blue-500 shrink-0" />
                <span class="text-gray-500 shrink-0">action_id:</span>
                <span class="font-mono text-gray-800 truncate">{{ config.config_data?.meta?.action_id }}</span>
              </div>
            </div>

            <div class="flex items-center gap-2 mb-4 flex-wrap">
              <div class="flex items-center gap-1 bg-blue-50 text-blue-600 rounded-lg px-2 py-1 text-xs">
                <Icon icon="mdi:cog" />
                <span>{{ getConfigCount(config) }} 个配置</span>
              </div>
              <div class="flex items-center gap-1 bg-green-50 text-green-600 rounded-lg px-2 py-1 text-xs">
                <Icon icon="mdi:arrow-right-circle" />
                <span>{{ getInputCount(config) }} 个输入</span>
              </div>
              <div class="flex items-center gap-1 bg-purple-50 text-purple-600 rounded-lg px-2 py-1 text-xs">
                <Icon icon="mdi:arrow-left-circle" />
                <span>{{ getOutputCount(config) }} 个输出</span>
              </div>
            </div>

            <div class="text-xs text-gray-400 mb-4">
              更新于 {{ formatDate(config.updated_at) }}
            </div>

            <div class="flex items-center gap-2 pt-4 border-t border-gray-100">
              <el-button type="primary" link size="small" class="flex-1" @click="handleEdit(config)">
                <template #icon><Icon icon="mdi:pencil" /></template>
                编辑
              </el-button>
              <el-button type="danger" link size="small" @click="handleDelete(config)">
                <template #icon><Icon icon="mdi:delete" /></template>
                删除
              </el-button>
            </div>
          </div>
        </div>

        <div
          v-else-if="!loading"
          class="flex flex-col items-center justify-center py-16 bg-white rounded-2xl border-2 border-dashed border-gray-300"
        >
          <Icon icon="mdi:cog-outline" class="text-6xl text-gray-300 mb-4" />
          <p class="text-gray-500 text-lg mb-2">暂无配置</p>
          <p class="text-gray-400 text-sm mb-4">创建新的基础组件任务配置</p>
          <el-button type="primary" @click="handleCreate">
            <template #icon><Icon icon="mdi:plus" /></template>
            新建配置
          </el-button>
        </div>

        <div v-if="configList.length > 0 && total > pageSize" class="mt-6 flex justify-center">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="prev, pager, next"
            @current-change="fetchConfigList"
          />
        </div>
      </div>
    </div>

    <!-- 编辑/创建弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? `编辑配置 - ${formState.name || ''}` : '新建配置'"
      width="900px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <!-- 模式切换 -->
      <div class="flex items-center gap-1 mb-5 bg-gray-100 rounded-lg p-1 w-fit">
        <button
          class="px-4 py-1.5 text-sm rounded-md font-medium transition-all flex items-center gap-1.5"
          :class="editMode === 'table' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
          @click="switchToTable"
        >
          <Icon icon="mdi:table" />
          表格编辑
        </button>
        <button
          class="px-4 py-1.5 text-sm rounded-md font-medium transition-all flex items-center gap-1.5"
          :class="editMode === 'json' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
          @click="switchToJson"
        >
          <Icon icon="mdi:code-json" />
          JSON 编辑
        </button>
      </div>

      <!-- 表格编辑模式 -->
      <div v-show="editMode === 'table'" class="space-y-5 max-h-[62vh] overflow-y-auto pr-1">
        <!-- 基本信息 -->
        <div class="border border-gray-200 rounded-xl overflow-hidden">
          <div class="bg-blue-50 px-4 py-2.5 flex items-center gap-2">
            <Icon icon="mdi:information-outline" class="text-blue-600" />
            <span class="font-medium text-blue-800 text-sm">基本信息</span>
          </div>
          <div class="p-4 grid grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-1">配置名称 <span class="text-red-500">*</span></label>
              <el-input v-model="formState.name" placeholder="如：每日数据采集任务" size="small" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-1">组件类型 <span class="text-red-500">*</span></label>
              <el-select v-model="formState.type" placeholder="选择组件类型" size="small" class="w-full">
                <el-option label="采集器" value="crawler" />
                <el-option label="分析器" value="analyzer" />
                <el-option label="报告生成器" value="reporter" />
                <el-option label="自定义" value="custom" />
              </el-select>
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-1">版本</label>
              <el-input v-model="formState.version" placeholder="如：1.0.0" size="small" />
            </div>
            <div class="col-span-2">
              <label class="block text-xs font-medium text-gray-600 mb-1">描述</label>
              <el-input v-model="formState.description" placeholder="配置用途描述" size="small" />
            </div>
          </div>
        </div>

        <!-- Meta 标识 -->
        <div class="border border-gray-200 rounded-xl overflow-hidden">
          <div class="bg-blue-50 px-4 py-2.5 flex items-center gap-2">
            <Icon icon="mdi:identifier" class="text-blue-600" />
            <span class="font-medium text-blue-800 text-sm">Meta 标识</span>
          </div>
          <div class="p-4 grid grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-1">node_instance_id <span class="text-red-500">*</span></label>
              <el-input v-model="formState.meta.node_instance_id" placeholder="如：crawler_daily_task" size="small" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-600 mb-1">action_id <span class="text-red-500">*</span></label>
              <el-input v-model="formState.meta.action_id" placeholder="如：daily_task" size="small" />
            </div>
          </div>
        </div>

        <!-- Config 配置参数 -->
        <div class="border border-gray-200 rounded-xl overflow-hidden">
          <div class="bg-blue-50 px-4 py-2.5 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <Icon icon="mdi:cog-outline" class="text-blue-600" />
              <span class="font-medium text-blue-800 text-sm">配置参数 (config)</span>
            </div>
            <el-button size="small" type="primary" link @click="addConfigRow">
              <template #icon><Icon icon="mdi:plus" /></template>
              添加参数
            </el-button>
          </div>
          <div class="p-4">
            <div v-if="formState.configRows.length === 0" class="text-center text-gray-400 text-sm py-3">
              暂无配置参数
            </div>
            <div v-else class="space-y-2">
              <div
                v-for="(row, index) in formState.configRows"
                :key="index"
                class="border border-gray-100 rounded-lg p-2.5 bg-white"
              >
                <div class="flex items-center gap-2 mb-1.5">
                  <el-input v-model="row.key" placeholder="参数名" size="small" style="width:140px;flex-shrink:0" />
                  <el-select
                    v-model="row.valueType"
                    size="small"
                    style="width:100px;flex-shrink:0"
                    @change="onConfigValueTypeChange(row)"
                  >
                    <el-option label="字符串" value="string" />
                    <el-option label="数值" value="number" />
                    <el-option label="布尔" value="boolean" />
                    <el-option label="数组" value="array" />
                    <el-option label="对象" value="object" />
                  </el-select>
                  <el-switch v-if="row.valueType === 'boolean'" v-model="row.value" class="ml-1" />
                  <div class="ml-auto">
                    <el-button size="small" type="danger" link @click="removeConfigRow(index)">
                      <Icon icon="mdi:delete" />
                    </el-button>
                  </div>
                </div>
                <div v-if="row.valueType !== 'boolean'">
                  <el-input
                    v-if="row.valueType === 'string'"
                    v-model="row.value"
                    placeholder="参数值"
                    size="small"
                  />
                  <el-input-number
                    v-else-if="row.valueType === 'number'"
                    v-model="row.value"
                    size="small"
                    class="w-full"
                    controls-position="right"
                  />
                  <el-input
                    v-else-if="row.valueType === 'array' || row.valueType === 'object'"
                    v-model="row.value"
                    type="textarea"
                    :rows="3"
                    :placeholder="row.valueType === 'array' ? getArrayPlaceholder() : getObjectPlaceholder()"
                    size="small"
                    class="font-mono"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Inputs 输入端口 -->
        <div class="border border-gray-200 rounded-xl overflow-hidden">
          <div class="bg-green-50 px-4 py-2.5 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <Icon icon="mdi:arrow-right-circle-outline" class="text-green-600" />
              <span class="font-medium text-green-800 text-sm">输入端口 (inputs)</span>
            </div>
            <el-button size="small" type="primary" link @click="addInputRow">
              <template #icon><Icon icon="mdi:plus" /></template>
              添加输入端口
            </el-button>
          </div>
          <div class="p-4">
            <div v-if="formState.inputRows.length === 0" class="text-center text-gray-400 text-sm py-3">
              暂无输入端口
            </div>
            <div v-else class="space-y-3">
              <div
                v-for="(row, index) in formState.inputRows"
                :key="index"
                class="border border-gray-100 rounded-lg p-3 bg-gray-50"
              >
                <div class="flex items-center gap-2 mb-2.5">
                  <el-input v-model="row.portName" placeholder="端口名" size="small" style="width:140px;flex-shrink:0" />
                  <el-select
                    v-model="row.ioType"
                    size="small"
                    style="width:110px;flex-shrink:0"
                    @change="onInputTypeChange(row)"
                  >
                    <el-option label="直接值" value="value" />
                    <el-option label="引用队列" value="reference" />
                  </el-select>
                  <el-select
                    v-if="row.ioType === 'value'"
                    v-model="row.valueType"
                    size="small"
                    style="width:90px;flex-shrink:0"
                    @change="onInputValueTypeChange(row)"
                  >
                    <el-option label="字符串" value="string" />
                    <el-option label="数值" value="number" />
                    <el-option label="布尔" value="boolean" />
                    <el-option label="数组" value="array" />
                    <el-option label="对象" value="object" />
                  </el-select>
                  <div class="ml-auto">
                    <el-button size="small" type="danger" link @click="removeInputRow(index)">
                      <Icon icon="mdi:delete" />
                    </el-button>
                  </div>
                </div>
                <div>
                  <template v-if="row.ioType === 'value'">
                    <el-input
                      v-if="row.valueType === 'string'"
                      v-model="row.value"
                      placeholder="输入值"
                      size="small"
                    />
                    <el-input-number
                      v-else-if="row.valueType === 'number'"
                      v-model="row.value"
                      size="small"
                      class="w-full"
                      controls-position="right"
                    />
                    <el-switch v-else-if="row.valueType === 'boolean'" v-model="row.value" />
                    <el-input
                      v-else-if="row.valueType === 'array' || row.valueType === 'object'"
                      v-model="row.value"
                      type="textarea"
                      :rows="3"
                      :placeholder="row.valueType === 'array' ? getArrayPlaceholder() : getObjectPlaceholder()"
                      size="small"
                      class="font-mono"
                    />
                  </template>
                  <TagInput
                    v-else-if="row.ioType === 'reference'"
                    v-model="row.value"
                    placeholder="输入队列名，回车添加"
                    :show-count="false"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Outputs 输出端口 -->
        <div class="border border-gray-200 rounded-xl overflow-hidden">
          <div class="bg-purple-50 px-4 py-2.5 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <Icon icon="mdi:arrow-left-circle-outline" class="text-purple-600" />
              <span class="font-medium text-purple-800 text-sm">输出端口 (outputs)</span>
            </div>
            <el-button size="small" type="primary" link @click="addOutputRow">
              <template #icon><Icon icon="mdi:plus" /></template>
              添加输出端口
            </el-button>
          </div>
          <div class="p-4">
            <div v-if="formState.outputRows.length === 0" class="text-center text-gray-400 text-sm py-3">
              暂无输出端口
            </div>
            <div v-else class="space-y-3">
              <div
                v-for="(row, index) in formState.outputRows"
                :key="index"
                class="border border-gray-100 rounded-lg p-3 bg-gray-50"
              >
                <div class="flex items-center gap-2 mb-2.5">
                  <el-input v-model="row.portName" placeholder="端口名" size="small" style="width:140px;flex-shrink:0" />
                  <el-select
                    v-model="row.ioType"
                    size="small"
                    style="width:110px;flex-shrink:0"
                    @change="onOutputTypeChange(row)"
                  >
                    <el-option label="引用队列" value="reference" />
                    <el-option label="直接值" value="value" />
                  </el-select>
                  <span v-if="row.ioType === 'reference'" class="text-xs text-gray-400">目标队列：</span>
                  <div class="ml-auto">
                    <el-button size="small" type="danger" link @click="removeOutputRow(index)">
                      <Icon icon="mdi:delete" />
                    </el-button>
                  </div>
                </div>
                <TagInput
                  v-if="row.ioType === 'reference'"
                  v-model="row.queues"
                  placeholder="输入目标队列名，回车添加"
                  :show-count="false"
                />
                <p v-else class="text-xs text-gray-400 pl-1 py-1">type: "value"，无需设置 value 字段</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- JSON 编辑模式 -->
      <div v-show="editMode === 'json'">
        <div
          v-if="jsonError"
          class="mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm flex items-center gap-2"
        >
          <Icon icon="mdi:alert-circle" />
          {{ jsonError }}
        </div>
        <MonacoEditor
          v-model="jsonString"
          language="json"
          :min-height="450"
        />
      </div>

      <template #footer>
        <div class="flex items-center justify-end gap-3">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="handleSave">保存配置</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import MonacoEditor from '@/components/MonacoEditor.vue'
import TagInput from '@/components/action/nodes/components/TagInput.vue'
import { taskConfigApi } from '@/api/taskConfig'

const loading = ref(false)
const saving = ref(false)
const configList = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingConfigId = ref(null)
const editMode = ref('table')
const jsonString = ref('')
const jsonError = ref('')

const filterParams = reactive({ keyword: '', component_type: '' })

const formState = reactive({
  name: '',
  description: '',
  type: '',
  version: '1.0.0',
  meta: { node_instance_id: '', action_id: '' },
  configRows: [],
  inputRows: [],
  outputRows: []
})

let isUpdatingFromJson = false
let isUpdatingFromForm = false
let jsonDebounceTimer = null

function detectValueType(val) {
  if (Array.isArray(val)) return 'array'
  if (val !== null && typeof val === 'object') return 'object'
  if (typeof val === 'boolean') return 'boolean'
  if (typeof val === 'number') return 'number'
  return 'string'
}

function parseJsonField(str, fallback) {
  try { return JSON.parse(str) } catch { return fallback }
}

function getArrayPlaceholder() { return '如：["item1", 2, true]' }
function getObjectPlaceholder() { return '如：{"key": "value"}' }

function buildConfigData() {
  const config = {}
  formState.configRows.forEach((row) => {
    if (!row.key) return
    let val = row.value
    if (row.valueType === 'number') val = typeof val === 'number' ? val : Number(val) || 0
    else if (row.valueType === 'boolean') val = !!val
    else if (row.valueType === 'array') val = parseJsonField(val, [])
    else if (row.valueType === 'object') val = parseJsonField(val, {})
    config[row.key] = val
  })

  const inputs = {}
  formState.inputRows.forEach((row) => {
    if (!row.portName) return
    let value = row.value
    if (row.ioType === 'value') {
      if (row.valueType === 'number') value = typeof value === 'number' ? value : Number(value) || 0
      else if (row.valueType === 'boolean') value = !!value
      else if (row.valueType === 'array') value = parseJsonField(value, [])
      else if (row.valueType === 'object') value = parseJsonField(value, {})
    }
    inputs[row.portName] = { type: row.ioType, value }
  })

  const outputs = {}
  formState.outputRows.forEach((row) => {
    if (!row.portName) return
    if (row.ioType === 'value') {
      outputs[row.portName] = { type: 'value' }
    } else {
      outputs[row.portName] = { type: 'reference', value: [...(row.queues || [])] }
    }
  })

  return {
    meta: { node_instance_id: formState.meta.node_instance_id, action_id: formState.meta.action_id },
    config,
    inputs,
    outputs
  }
}

function applyConfigDataToForm(data) {
  if (data.meta) {
    formState.meta.node_instance_id = data.meta.node_instance_id || ''
    formState.meta.action_id = data.meta.action_id || ''
  }

  formState.configRows = Object.entries(data.config || {}).map(([key, val]) => {
    const vt = detectValueType(val)
    return {
      key,
      valueType: vt,
      value: (vt === 'array' || vt === 'object') ? JSON.stringify(val, null, 2) : val
    }
  })

  formState.inputRows = Object.entries(data.inputs || {}).map(([portName, port]) => {
    if (port.type === 'reference') {
      const refs = Array.isArray(port.value) ? [...port.value] : port.value ? [port.value] : []
      return { portName, ioType: 'reference', valueType: 'array', value: refs }
    }
    const vt = detectValueType(port.value)
    return {
      portName,
      ioType: 'value',
      valueType: vt,
      value: (vt === 'array' || vt === 'object') ? JSON.stringify(port.value, null, 2) : port.value
    }
  })

  formState.outputRows = Object.entries(data.outputs || {}).map(([portName, port]) => ({
    portName,
    ioType: port.type === 'value' ? 'value' : 'reference',
    queues: port.type === 'reference' ? (Array.isArray(port.value) ? [...port.value] : port.value ? [port.value] : []) : []
  }))
}

function initFormFromConfig(config) {
  formState.name = config.name || ''
  formState.description = config.description || ''
  formState.type = config.type || ''
  formState.version = config.version || '1.0.0'
  applyConfigDataToForm(config.config_data || {})
}

function resetForm() {
  formState.name = ''
  formState.description = ''
  formState.type = ''
  formState.version = '1.0.0'
  formState.meta.node_instance_id = ''
  formState.meta.action_id = ''
  formState.configRows = []
  formState.inputRows = []
  formState.outputRows = []
}

watch(
  formState,
  () => {
    if (isUpdatingFromJson) return
    isUpdatingFromForm = true
    jsonString.value = JSON.stringify(buildConfigData(), null, 2)
    nextTick(() => { isUpdatingFromForm = false })
  },
  { deep: true }
)

watch(jsonString, (val) => {
  if (isUpdatingFromForm) return
  clearTimeout(jsonDebounceTimer)
  jsonDebounceTimer = setTimeout(() => {
    try {
      const parsed = JSON.parse(val)
      isUpdatingFromJson = true
      applyConfigDataToForm(parsed)
      jsonError.value = ''
      nextTick(() => { isUpdatingFromJson = false })
    } catch (e) {
      jsonError.value = 'JSON 格式错误：' + e.message
    }
  }, 300)
})

function switchToTable() {
  if (editMode.value === 'json' && jsonError.value) {
    ElMessage.warning('请先修正 JSON 格式错误，再切换到表格编辑')
    return
  }
  if (editMode.value === 'json') {
    clearTimeout(jsonDebounceTimer)
    try {
      const parsed = JSON.parse(jsonString.value)
      isUpdatingFromJson = true
      applyConfigDataToForm(parsed)
      jsonError.value = ''
      nextTick(() => { isUpdatingFromJson = false })
    } catch (e) {
      ElMessage.warning('JSON 格式有误，请修正后切换：' + e.message)
      return
    }
  }
  editMode.value = 'table'
}

function switchToJson() {
  jsonString.value = JSON.stringify(buildConfigData(), null, 2)
  jsonError.value = ''
  editMode.value = 'json'
}

async function fetchConfigList() {
  loading.value = true
  try {
    const res = await taskConfigApi.getConfigList({
      keyword: filterParams.keyword || undefined,
      page: page.value,
      page_size: pageSize.value
    })
    const data = res.data || res
    let items = Array.isArray(data.items) ? data.items : []
    if (filterParams.component_type) {
      items = items.filter((c) => c.type === filterParams.component_type)
    }
    configList.value = items
    total.value = data.total ?? 0
  } finally {
    loading.value = false
  }
}

let searchTimer = null
function handleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchConfigList()
  }, 300)
}

function handleCreate() {
  isEditing.value = false
  editingConfigId.value = null
  editMode.value = 'table'
  isUpdatingFromJson = true
  resetForm()
  jsonString.value = JSON.stringify(buildConfigData(), null, 2)
  jsonError.value = ''
  nextTick(() => { isUpdatingFromJson = false })
  dialogVisible.value = true
}

function handleEdit(config) {
  isEditing.value = true
  editingConfigId.value = config.id
  editMode.value = 'table'
  isUpdatingFromJson = true
  initFormFromConfig(config)
  jsonString.value = JSON.stringify(buildConfigData(), null, 2)
  jsonError.value = ''
  nextTick(() => { isUpdatingFromJson = false })
  dialogVisible.value = true
}

async function handleSave() {
  if (!formState.name.trim()) {
    ElMessage.warning('请填写配置名称')
    return
  }
  if (!formState.type) {
    ElMessage.warning('请选择组件类型')
    return
  }
  if (!formState.meta.node_instance_id.trim() || !formState.meta.action_id.trim()) {
    ElMessage.warning('请填写 node_instance_id 和 action_id')
    return
  }

  saving.value = true
  try {
    const payload = {
      name: formState.name,
      description: formState.description ?? '',
      type: formState.type,
      version: formState.version || '1.0.0',
      config_data: buildConfigData()
    }

    if (isEditing.value) {
      await taskConfigApi.updateConfig(editingConfigId.value, payload)
      ElMessage.success('配置已更新')
    } else {
      await taskConfigApi.createConfig(payload)
      ElMessage.success('配置已创建')
    }

    dialogVisible.value = false
    fetchConfigList()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(config) {
  try {
    await ElMessageBox.confirm(
      `确认删除配置「${config.name}」？此操作不可撤销。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await taskConfigApi.deleteConfig(config.id)
    ElMessage.success('配置已删除')
    fetchConfigList()
  } catch (e) {
    if (e !== 'cancel' && e?.type !== 'cancel') {
      ElMessage.error(e?.response?.data?.message || e.message || '删除失败')
    }
  }
}

function addConfigRow() {
  formState.configRows.push({ key: '', valueType: 'string', value: '' })
}

function removeConfigRow(index) {
  formState.configRows.splice(index, 1)
}

function onConfigValueTypeChange(row) {
  if (row.valueType === 'number') row.value = 0
  else if (row.valueType === 'boolean') row.value = false
  else if (row.valueType === 'array') row.value = '[]'
  else if (row.valueType === 'object') row.value = '{}'
  else row.value = ''
}

function addInputRow() {
  formState.inputRows.push({ portName: '', ioType: 'value', valueType: 'string', value: '' })
}

function removeInputRow(index) {
  formState.inputRows.splice(index, 1)
}

function onInputTypeChange(row) {
  if (row.ioType === 'reference') {
    row.value = []
  } else {
    row.valueType = 'string'
    row.value = ''
  }
}

function onInputValueTypeChange(row) {
  if (row.valueType === 'number') row.value = 0
  else if (row.valueType === 'boolean') row.value = false
  else if (row.valueType === 'array') row.value = '[]'
  else if (row.valueType === 'object') row.value = '{}'
  else row.value = ''
}

function addOutputRow() {
  formState.outputRows.push({ portName: '', ioType: 'reference', queues: [] })
}

function onOutputTypeChange(row) {
  if (row.ioType !== 'reference') {
    row.queues = []
  }
}

function removeOutputRow(index) {
  formState.outputRows.splice(index, 1)
}

function getComponentTypeLabel(type) {
  const labels = { crawler: '采集器', analyzer: '分析器', reporter: '报告生成器', custom: '自定义' }
  return labels[type] || type || '未知'
}

function getConfigCount(config) {
  return Object.keys(config.config_data?.config || {}).length
}

function getInputCount(config) {
  return Object.keys(config.config_data?.inputs || {}).length
}

function getOutputCount(config) {
  return Object.keys(config.config_data?.outputs || {}).length
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

fetchConfigList()
</script>
