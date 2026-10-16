<template>
  <div class="min-h-screen bg-gray-50">
    <Header />

    <main v-if="isMobile" class="platform-mobile">
      <div class="platform-mobile-heading"><div><h1>平台</h1><p>发现来源，查看采集与关联情报</p></div><el-button :disabled="!hasPerm(PERM.operations.content.platform.create)" type="primary" @click="handleAddPlatform">新增</el-button></div>
      <form class="platform-mobile-search" @submit.prevent="handleSearch">
        <el-input v-model="searchKeyword" aria-label="搜索平台名称或描述" placeholder="平台名称或描述" clearable @clear="handleSearch" />
        <el-button native-type="submit" :disabled="loading">搜索</el-button>
        <el-button aria-label="筛选平台" @click="filterVisible = true"><Icon icon="mdi:filter-variant" /></el-button>
      </form>
      <div class="platform-mobile-summary"><span>{{ pagination.total }} 个平台</span><span>{{ [selectedStatus, selectedType === 'forum' ? '论坛' : selectedType === 'article' ? '文章' : ''].filter(Boolean).join(' · ') || '全部状态与类型' }}</span></div>
      <div v-if="!hasPerm(PERM.operations.content.platform.read)" class="platform-mobile-state">暂无平台读取权限</div>
      <div v-else-if="listError" class="platform-mobile-state" role="alert"><p>{{ listError }}</p><el-button @click="fetchPlatformList">重新加载</el-button></div>
      <div v-else v-loading="loading" class="platform-mobile-results" aria-live="polite">
        <el-empty v-if="!loading && !platformList.length" description="没有匹配的平台" :image-size="64" />
        <article v-for="platform in platformList" :key="platform.id" class="platform-mobile-card">
          <button class="platform-mobile-card-link" @click="handleViewDetail(platform.id)">
            <div class="platform-mobile-card-title"><img v-if="platform.logo" :src="getLogoUrl(platform.logo)" alt="" /><Icon v-else icon="mdi:web" class="platform-mobile-logo" /><div><h2>{{ platform.name }}</h2><p>{{ [platform.category, platform.sub_category, platform.net_type].filter(Boolean).join(' · ') }}</p></div><Icon icon="mdi:chevron-right" /></div>
            <div class="platform-mobile-tags"><el-tag :type="getStatusType(platform.status)" size="small">{{ platform.status || '状态未设置' }}</el-tag><el-tag type="info" size="small">{{ platform.type === 'forum' ? '论坛' : platform.type === 'article' ? '文章' : platform.type }}</el-tag></div>
            <p class="platform-mobile-description">{{ platform.description || '暂无描述' }}</p>
            <div v-if="platform.tags?.length" class="platform-mobile-tags"><el-tag v-for="tag in platform.tags.slice(0, 3)" :key="tag" size="small" effect="plain" :type="isSensitiveLabel(tag) ? 'danger' : 'info'">{{ tag }}</el-tag><span v-if="platform.tags.length > 3">+{{ platform.tags.length - 3 }}</span></div>
          </button>
        </article>
      </div>
      <div v-if="!listError && pagination.total > pagination.pageSize" class="platform-mobile-pagination"><el-pagination :current-page="pagination.page" :page-size="pagination.pageSize" :total="pagination.total" :pager-count="5" layout="prev, pager, next" @current-change="handlePageChange" /></div>
      <MobileSheet v-model="filterVisible" title="筛选平台">
        <el-form label-position="top"><el-form-item label="平台状态"><el-select v-model="draftStatus"><el-option label="全部状态" value="" /><el-option v-for="status in ['活跃', '非活跃', '离线']" :key="status" :label="status" :value="status" /></el-select></el-form-item><el-form-item label="内容类型"><el-radio-group v-model="draftType"><el-radio-button value="">全部</el-radio-button><el-radio-button value="forum">论坛</el-radio-button><el-radio-button value="article">文章</el-radio-button></el-radio-group></el-form-item></el-form>
        <template #footer><div class="platform-mobile-footer"><el-button @click="draftStatus = ''; draftType = ''">重置</el-button><el-button type="primary" @click="selectedStatus = draftStatus; selectedType = draftType; filterVisible = false; handleSearch()">应用筛选</el-button></div></template>
      </MobileSheet>
    </main>
    <template v-else>
    <FunctionalPageHeader
      title-prefix="平台"
      title-suffix="列表"
      subtitle="统一管理所有平台信息，查看平台详情、状态和统计数据"
    />

    <div class="max-w-480 mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- 筛选栏 -->
      <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-200 mb-6">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">搜索平台</label>
            <el-input
              v-model="searchKeyword"
              placeholder="搜索平台名称、类型..."
              clearable
              @input="handleSearch"
            >
              <template #prefix>
                <Icon icon="mdi:magnify" class="text-gray-400" />
              </template>
            </el-input>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">状态筛选</label>
            <el-select
              v-model="selectedStatus"
              placeholder="全部状态"
              clearable
              class="w-full"
            >
              <el-option label="全部状态" value="" />
              <el-option label="活跃" value="活跃" />
              <el-option label="非活跃" value="非活跃" />
              <el-option label="离线" value="离线" />
            </el-select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">类型筛选</label>
            <el-select
              v-model="selectedType"
              placeholder="全部类型"
              clearable
              class="w-full"
            >
              <el-option label="全部类型" value="" />
            </el-select>
          </div>
          <div class="flex items-end">
            <el-button type="primary" class="w-full" @click="handleSearch">
              <template #icon><Icon icon="mdi:magnify" /></template>
              搜索
            </el-button>
          </div>
        </div>
      </div>

      <!-- 平台列表区域 -->
      <div class="bg-white rounded-2xl shadow-sm border border-gray-200">
        <div class="p-6 border-b border-gray-200 flex items-center justify-between">
          <h2 class="text-lg font-bold text-gray-900">平台列表</h2>
          <el-button type="primary" @click="handleAddPlatform">
            <template #icon><Icon icon="mdi:plus" /></template>
            新增平台
          </el-button>
        </div>

        <div v-loading="loading" :element-loading-text="'加载中...'" class="min-h-100">
          <div class="p-6">
            <div v-if="platformList.length === 0" class="flex flex-col items-center justify-center py-16">
              <Icon icon="mdi:inbox" class="text-6xl text-gray-300 mb-4" />
              <p class="text-gray-500 text-lg mb-2">暂无平台数据</p>
              <p class="text-gray-400 text-sm">创建新平台后，列表将显示在这里</p>
            </div>

            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
              <div
                v-for="platform in platformList"
                :key="platform.id"
                class="bg-white rounded-2xl p-6 shadow-lg border border-blue-100 hover:shadow-xl transition-shadow"
              >
            <!-- 平台头部信息 -->
            <div class="flex items-start justify-between mb-4">
              <div class="flex items-start space-x-4 flex-1">
                <div class="w-16 h-16 bg-white rounded-xl shadow-sm border border-gray-200 flex items-center justify-center overflow-hidden shrink-0">
                  <img v-if="platform.logo" :src="getLogoUrl(platform.logo)" :alt="platform.name" class="w-full h-full object-contain" />
                  <Icon v-else icon="mdi:web" class="text-blue-600 text-3xl" />
                </div>
                <div class="flex-1 min-w-0">
                  <h3 class="text-lg font-bold text-gray-900 mb-2 truncate">{{ platform.name }}</h3>
                  <div class="flex flex-wrap items-center gap-2 mb-2">
                    <el-tag :type="getStatusType(platform.status)" size="small">{{ platform.status }}</el-tag>
                    <el-tag type="primary" size="small">{{ platform.type }}</el-tag>
                  </div>
                </div>
              </div>
            </div>

            <!-- 平台描述 -->
            <p class="text-sm text-gray-600 mb-4 line-clamp-2">{{ platform.description }}</p>

            <!-- 平台详细信息 -->
            <div class="space-y-2 mb-4">
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-500 flex items-center gap-2">
                  <Icon icon="mdi:tag" class="text-blue-500" />
                  分类
                </span>
                <span class="font-medium text-gray-900">{{ platform.category }}</span>
              </div>
              <div v-if="platform.sub_category" class="flex items-center justify-between text-sm">
                <span class="text-gray-500 flex items-center gap-2">
                  <Icon icon="mdi:tag-outline" class="text-green-500" />
                  子分类
                </span>
                <span class="font-medium text-gray-900">{{ platform.sub_category }}</span>
              </div>
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-500 flex items-center gap-2">
                  <Icon icon="mdi:calendar" class="text-purple-500" />
                  创建时间
                </span>
                <span class="font-medium text-gray-900">{{ formatDate(platform.created_at) }}</span>
              </div>
            </div>

            <!-- 平台标签 -->
            <div v-if="platform.tags && platform.tags.length > 0" class="mb-4">
              <div class="flex flex-wrap gap-2">
                <el-tag
                  v-for="tag in platform.tags.slice(0, 3)"
                  :key="tag"
                  size="small"
                  :type="isSensitiveLabel(tag) ? 'danger' : 'info'"
                  effect="plain"
                >
                  {{ tag }}
                </el-tag>
                <el-tag v-if="platform.tags.length > 3" size="small" type="info" effect="plain">
                  +{{ platform.tags.length - 3 }}
                </el-tag>
              </div>
            </div>

            <!-- 平台板块 -->
            <div v-if="platform.sections && platform.sections.length > 0" class="mb-4">
              <div class="flex flex-wrap gap-2">
                <el-tag
                  v-for="section in platform.sections.slice(0, 3)"
                  :key="section"
                  size="small"
                  :type="isSensitiveLabel(section) ? 'danger' : 'primary'"
                  effect="plain"
                >
                  {{ section }}
                </el-tag>
                <el-tag v-if="platform.sections.length > 3" size="small" type="primary" effect="plain">
                  +{{ platform.sections.length - 3 }}
                </el-tag>
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="pt-4 border-t border-gray-200">
              <div class="flex items-center gap-2">
                <el-button type="primary" link size="small" class="flex-1" @click="handleViewDetail(platform.id)">
                  <template #icon><Icon icon="mdi:eye" /></template>
                  查看详情
                </el-button>
                <el-button type="danger" link size="small" @click="handleDeletePlatform(platform.id)">
                  <template #icon><Icon icon="mdi:delete" /></template>
                  删除
                </el-button>
              </div>
            </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 分页 -->
        <div v-if="!loading && platformList.length > 0" class="p-6 border-t border-gray-200 flex justify-center">
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
    </div>

    </template>
    <!-- 手机分步填写，复用桌面的字段和提交合同。 -->
    <component
      :is="isMobile ? MobileSheet : 'el-dialog'"
      v-model="dialogVisible"
      :title="isMobile ? `新增平台 · ${mobileCreateStep + 1}/3` : '新增平台'"
      width="800px"
      :close-on-click-modal="false"
      :close-on-press-escape="!submitLoading"
      :show-close="!submitLoading"
      @close="handleDialogClose"
    >
      <p v-if="isMobile" class="platform-mobile-step">{{ ['先填写名称、网址和分类', '补充平台资料与采集信息', '核对资料后创建平台'][mobileCreateStep] }}</p>
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        :label-position="isMobile ? 'top' : 'right'"
        :label-width="isMobile ? undefined : '120px'"
        :class="isMobile ? 'platform-mobile-form' : 'max-h-[70vh] overflow-y-auto pr-2'"
      >
        <el-form-item v-show="!isMobile || mobileCreateStep === 0" label="平台名称" prop="name">
          <el-input
            v-model="formData.name"
            placeholder="请输入平台名称"
            maxlength="100"
            show-word-limit
            clearable
          />
        </el-form-item>

        <el-form-item v-show="!isMobile || mobileCreateStep === 1" label="平台描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入平台描述"
            clearable
          />
        </el-form-item>

        <el-form-item v-show="!isMobile || mobileCreateStep === 0" label="平台类型" prop="type">
          <el-select
            v-model="formData.type"
            placeholder="请选择平台类型"
            class="w-full"
          >
            <el-option label="forum" value="forum" />
            <el-option label="article" value="article" />
          </el-select>
        </el-form-item>

        <el-form-item v-show="!isMobile || mobileCreateStep === 1" label="网络类型" prop="net_type">
          <el-select
            v-model="formData.net_type"
            placeholder="请选择网络类型"
            class="w-full"
          >
            <el-option label="明网" value="明网" />
            <el-option label="Tor" value="Tor" />
          </el-select>
        </el-form-item>

        <el-form-item v-show="!isMobile || mobileCreateStep === 1" label="平台状态" prop="status">
          <el-select
            v-model="formData.status"
            placeholder="请选择平台状态"
            class="w-full"
          >
            <el-option label="活跃" value="活跃" />
            <el-option label="非活跃" value="非活跃" />
            <el-option label="离线" value="离线" />
          </el-select>
        </el-form-item>

        <el-form-item v-show="!isMobile || mobileCreateStep === 0" label="平台URL" prop="url">
          <el-input
            v-model="formData.url"
            placeholder="请输入平台URL"
            clearable
          />
        </el-form-item>

        <el-form-item v-show="!isMobile || mobileCreateStep === 1" label="平台Logo" prop="logo">
          <el-input
            v-model="formData.logo"
            placeholder="请输入平台Logo URL"
            clearable
          />
        </el-form-item>

        <el-form-item v-show="!isMobile || mobileCreateStep === 0" label="平台分类" prop="category">
          <el-select
            v-model="formData.category"
            placeholder="请选择平台分类"
            class="w-full"
            clearable
          >
            <el-option label="论坛" value="论坛" />
            <el-option label="新闻" value="新闻" />
            <el-option label="博客" value="博客" />
            <el-option label="视频" value="视频" />
            <el-option label="社交媒体" value="社交媒体" />
            <el-option label="群组" value="群组" />
          </el-select>
        </el-form-item>

        <el-form-item v-show="!isMobile || mobileCreateStep === 0" label="平台子分类" prop="sub_category">
          <el-select
            v-model="formData.sub_category"
            placeholder="请选择或输入平台子分类"
            class="w-full"
            clearable
            filterable
            allow-create
            default-first-option
            :loading="subCategoryLoading"
          >
            <el-option
              v-for="item in subCategoryOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>

        <el-form-item v-show="!isMobile || mobileCreateStep === 1" label="信任度" prop="confidence">
          <div class="flex items-center gap-4 w-full">
            <el-slider
              v-model="formData.confidence"
              :min="0"
              :max="1"
              :step="0.01"
              class="flex-1"
            />
            <el-input-number
              v-model="formData.confidence"
              :min="0"
              :max="1"
              :step="0.01"
              :precision="2"
              controls-position="right"
              style="width: 120px"
            />
          </div>
        </el-form-item>

        <el-form-item v-show="!isMobile || mobileCreateStep === 1" label="平台标签" prop="tags">
          <TagInput
            v-model="formData.tags"
            placeholder="输入标签后按回车或点击添加"
          />
        </el-form-item>

        <el-form-item v-show="!isMobile || mobileCreateStep === 1" label="平台板块" prop="sections">
          <TagInput
            v-model="formData.sections"
            placeholder="输入板块名称后按回车或点击添加"
          />
        </el-form-item>

        <el-form-item v-show="!isMobile || mobileCreateStep === 1" label="爬虫名称" prop="spider_name">
          <el-input
            v-model="formData.spider_name"
            placeholder="请输入爬虫名称（可选）"
            clearable
          />
        </el-form-item>
      </el-form>
      <dl v-if="isMobile && mobileCreateStep === 2" class="platform-mobile-review"><template v-for="[label, value] in [['名称', formData.name], ['网址', formData.url], ['分类', `${formData.category} / ${formData.sub_category}`], ['类型', formData.type], ['状态与网络', `${formData.status} · ${formData.net_type}`], ['描述', formData.description], ['Logo', formData.logo], ['信任度', formData.confidence], ['标签', formData.tags.join('、')], ['板块', formData.sections.join('、')], ['爬虫', formData.spider_name]]" :key="label"><dt>{{ label }}</dt><dd>{{ value === '' ? '未填写' : value }}</dd></template></dl>

      <template #footer>
        <div :class="isMobile ? 'platform-mobile-footer' : 'dialog-footer'">
          <el-button :disabled="submitLoading" @click="isMobile && mobileCreateStep > 0 ? mobileCreateStep-- : handleDialogClose()">{{ isMobile && mobileCreateStep > 0 ? '上一步' : '取消' }}</el-button>
          <el-button v-if="isMobile && mobileCreateStep < 2" type="primary" @click="nextCreateStep">下一步</el-button>
          <el-button v-else type="primary" :loading="submitLoading" :disabled="isMobile && !hasPerm(PERM.operations.content.platform.create)" @click="handleSubmit">
            {{ isMobile ? '确认创建' : '确定' }}
          </el-button>
        </div>
      </template>
    </component>
  </div>
</template>

<script setup>
import { ref, onMounted, onActivated, onDeactivated, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { platformApi } from '@/api/platform'
import { getPaginatedData } from '@/utils/request'
import { getCosUrl } from '@/utils/cos'
import { formatDate } from '@/utils/action'
import TagInput from '@/components/action/nodes/components/TagInput.vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
import { PERM } from '@/utils/permissions'
import { hasPerm } from '@/utils/permissionKit'

defineOptions({ name: 'PlatformList' })

const router = useRouter()
const { isMobile } = useMobileViewport()
const filterVisible = ref(false)
const draftStatus = ref('')
const draftType = ref('')
const mobileCreateStep = ref(0)
const listError = ref('')
let listGeneration = 0
let pageActive = true
let reloadOnActivate = false
const loading = ref(false)
const searchKeyword = ref('')
const selectedStatus = ref('')
const selectedType = ref('')
const platformList = ref([])
const pagination = ref({
  page: 1,
  pageSize: 10,
  total: 0
})

const fetchPlatformList = async () => {
  if (!pageActive || (isMobile.value && !hasPerm(PERM.operations.content.platform.read))) return
  const generation = ++listGeneration
  listError.value = ''
  loading.value = true
  try {
    const result = await getPaginatedData(
      platformApi.getPlatformList,
      {
        page: pagination.value.page,
        page_size: pagination.value.pageSize,
        ...(isMobile.value ? { search: searchKeyword.value.trim() || undefined, status: selectedStatus.value || undefined, type: selectedType.value || undefined } : {})
      }
    )

    if (generation !== listGeneration || !pageActive) return
    platformList.value = result.items
    pagination.value = {
      ...pagination.value,
      ...result.pagination
    }
  } catch (error) {
    if (generation !== listGeneration || !pageActive) return
    console.error('获取平台列表失败:', error)
    ElMessage.error('获取平台列表失败')
    platformList.value = []
    listError.value = '平台列表加载失败，请重试'
  } finally {
    if (generation === listGeneration) loading.value = false
  }
}

const handlePageChange = (page) => {
  pagination.value.page = page
  fetchPlatformList()
}

const handlePageSizeChange = (pageSize) => {
  pagination.value.pageSize = pageSize
  pagination.value.page = 1
  fetchPlatformList()
}

const handleSearch = () => {
  if (isMobile.value) {
    pagination.value.page = 1
    fetchPlatformList()
    return
  }
  ElMessage.info('搜索功能暂未实现')
}

watch(filterVisible, visible => {
  if (visible) { draftStatus.value = selectedStatus.value; draftType.value = selectedType.value }
})

/** """校验当前步骤后进入平台创建的下一步。""" */
const nextCreateStep = async () => {
  if (mobileCreateStep.value === 0) {
    try { await formRef.value?.validateField(['name', 'url', 'type', 'category', 'sub_category']) } catch { return }
  }
  mobileCreateStep.value += 1
}

const dialogVisible = ref(false)
const formRef = ref(null)
const submitLoading = ref(false)
const formData = ref({
  name: '',
  description: '',
  type: 'forum',
  net_type: '明网',
  status: '活跃',
  url: '',
  logo: '',
  tags: [],
  sections: [],
  category: '',
  sub_category: '',
  confidence: 1,
  spider_name: ''
})

const formRules = {
  name: [
    { required: true, message: '请输入平台名称', trigger: 'blur' },
    { min: 1, max: 100, message: '平台名称长度应在1-100字符之间', trigger: 'blur' }
  ],
  type: [
    { required: true, message: '请选择平台类型', trigger: 'change' }
  ],
  url: [
    { required: true, message: '请输入平台URL', trigger: 'blur' }
  ],
  category: [
    { required: true, message: '请选择平台分类', trigger: 'change' }
  ],
  sub_category: [
    { required: true, message: '请选择或输入平台子分类', trigger: 'change' }
  ]
}

const subCategoryOptions = ref([])
const subCategoryLoading = ref(false)

const fetchSubCategoryOptions = async () => {
  subCategoryLoading.value = true
  try {
    const res = await platformApi.getPlatformFilterSubCategory()
    if (res?.code === 0 && Array.isArray(res.data)) {
      subCategoryOptions.value = res.data
    } else {
      subCategoryOptions.value = []
    }
  } catch (error) {
    console.error('获取子分类列表失败:', error)
    subCategoryOptions.value = []
  } finally {
    subCategoryLoading.value = false
  }
}

const handleAddPlatform = async () => {
  if (submitLoading.value) return
  if (isMobile.value && !hasPerm(PERM.operations.content.platform.create)) return
  mobileCreateStep.value = 0
  dialogVisible.value = true
  await fetchSubCategoryOptions()
}

const handleDialogClose = () => {
  dialogVisible.value = false
  if (formRef.value) {
    formRef.value.resetFields()
  }
  formData.value = {
    name: '',
    description: '',
    type: 'forum',
    net_type: '明网',
    status: '活跃',
    url: '',
    logo: '',
    tags: [],
    sections: [],
    category: '',
    sub_category: '',
    confidence: 1,
    spider_name: ''
  }
}

const handleSubmit = async () => {
  if (!formRef.value || submitLoading.value || (isMobile.value && !hasPerm(PERM.operations.content.platform.create))) return

  try {
    await formRef.value.validate()
    if (!pageActive || submitLoading.value || (isMobile.value && !hasPerm(PERM.operations.content.platform.create))) return
    submitLoading.value = true

    const submitData = {
      name: formData.value.name,
      description: formData.value.description || '',
      type: formData.value.type,
      net_type: formData.value.net_type,
      status: formData.value.status,
      url: formData.value.url,
      logo: formData.value.logo || '',
      tags: formData.value.tags || [],
      sections: formData.value.sections || [],
      category: formData.value.category,
      sub_category: formData.value.sub_category,
      confidence: formData.value.confidence,
      spider_name: formData.value.spider_name || null
    }

    const response = await platformApi.createPlatform(submitData)
    if (response?.code !== 0) throw new Error(response?.message || '创建平台失败')
    ElMessage.success('平台创建成功')
    handleDialogClose()
    fetchPlatformList()
  } catch (error) {
    if (error !== false) {
      console.error('创建平台失败:', error)
    }
  } finally {
    submitLoading.value = false
  }
}

const handleViewDetail = (id) => {
  if (isMobile.value && !hasPerm(PERM.operations.content.platform.read)) return
  router.push(`/details/platform/${id}`)
}

const handleDeletePlatform = (id) => {
  ElMessageBox.confirm(
    '确定要删除该平台吗？此操作不可恢复。',
    '确认删除',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    ElMessage.info('删除平台功能暂未实现')
  }).catch(() => {})
}

const getStatusType = (status) => {
  const statusMap = {
    活跃: 'success',
    非活跃: 'danger',
    离线: 'info'
  }
  return statusMap[status] || 'info'
}

const isSensitiveLabel = (text) => {
  if (text == null || text === '') return false
  const s = String(text).toUpperCase()
  return s.includes('NSFW') || s.includes('AIGC')
}

const getLogoUrl = (logo) => {
  return getCosUrl(logo)
}

onMounted(() => {
  fetchPlatformList()
})
onActivated(() => { pageActive = true; if (reloadOnActivate) { reloadOnActivate = false; fetchPlatformList() } })
onDeactivated(() => {
  pageActive = false
  reloadOnActivate = loading.value || submitLoading.value
  listGeneration++
  loading.value = false
  filterVisible.value = false
  dialogVisible.value = false
})
onBeforeUnmount(() => { pageActive = false; listGeneration++ })
</script>

<style scoped>
.platform-mobile { padding: 16px 12px 24px; color: #0f172a; }
.platform-mobile-heading, .platform-mobile-summary, .platform-mobile-card-title { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.platform-mobile-heading h1 { margin: 0; font-size: 23px; font-weight: 750; }
.platform-mobile-heading p, .platform-mobile-card-title p { color: #64748b; font-size: 12px; margin: 5px 0 0; }
.platform-mobile-search { display: flex; gap: 6px; margin: 18px 0 12px; }
.platform-mobile-search :deep(.el-input) { min-width: 0; flex: 1; }
.platform-mobile :deep(.el-button), .platform-mobile-form :deep(.el-input__wrapper), .platform-mobile-form :deep(.el-select__wrapper) { min-height: 44px; }
.platform-mobile :deep(.el-button + .el-button) { margin-left: 0; }
.platform-mobile-summary { font-size: 12px; color: #64748b; margin-bottom: 12px; }
.platform-mobile-results { min-height: 150px; }
.platform-mobile-card { border: 1px solid #e2e8f0; background: white; border-radius: 16px; margin-bottom: 12px; overflow: hidden; }
.platform-mobile-card-link { display: block; padding: 16px; width: 100%; background: transparent; border: 0; text-align: left; color: inherit; }
.platform-mobile-card-title > div { flex: 1; min-width: 0; }
.platform-mobile-card-title h2 { margin: 0; font-size: 17px; font-weight: 700; overflow-wrap: anywhere; }
.platform-mobile-card-title img, .platform-mobile-logo { width: 38px; height: 38px; object-fit: contain; flex-shrink: 0; color: #2563eb; }
.platform-mobile-description { margin: 12px 0; color: #475569; font-size: 14px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
.platform-mobile-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 10px; min-width: 0; }
.platform-mobile-tags :deep(.el-tag) { max-width: 100%; }
.platform-mobile-tags :deep(.el-tag__content) { overflow: hidden; text-overflow: ellipsis; }
.platform-mobile-state { padding: 24px; text-align: center; background: #fff; border-radius: 16px; color: #64748b; }
.platform-mobile-state p { margin-bottom: 12px; }
.platform-mobile-pagination { display: flex; justify-content: center; margin-top: 20px; }
.platform-mobile-footer { display: flex; gap: 10px; }
.platform-mobile-footer .el-button { flex: 1; min-width: 0; margin: 0; }
.platform-mobile-step { margin-bottom: 18px; color: #64748b; font-size: 14px; }
.platform-mobile-review { display: grid; grid-template-columns: 65px minmax(0, 1fr); gap: 14px 10px; font-size: 14px; }
.platform-mobile-review dt { color: #64748b; }
.platform-mobile-review dd { margin: 0; overflow-wrap: anywhere; white-space: pre-wrap; }
.platform-mobile-form :deep(.el-select) { width: 100%; }
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
