<template>
  <div class="min-h-screen bg-gray-50">
    <Header />
    
    <FunctionalPageHeader
      title-prefix="平台"
      title-suffix="列表"
      subtitle="统一管理所有平台信息，查看平台详情、状态和统计数据"
    />

    <div class="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
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

        <div v-loading="loading" :element-loading-text="'加载中...'" class="min-h-[400px]">
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
                <el-tag v-for="tag in platform.tags.slice(0, 3)" :key="tag" size="small" type="info" effect="plain">
                  {{ tag }}
                </el-tag>
                <el-tag v-if="platform.tags.length > 3" size="small" type="info" effect="plain">
                  +{{ platform.tags.length - 3 }}
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

    <!-- 新增平台对话框 -->
    <el-dialog
      v-model="dialogVisible"
      title="新增平台"
      width="800px"
      :close-on-click-modal="false"
      @close="handleDialogClose"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="120px"
        class="max-h-[70vh] overflow-y-auto pr-2"
      >
        <el-form-item label="平台名称" prop="name">
          <el-input
            v-model="formData.name"
            placeholder="请输入平台名称"
            maxlength="100"
            show-word-limit
            clearable
          />
        </el-form-item>

        <el-form-item label="平台描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入平台描述"
            clearable
          />
        </el-form-item>

        <el-form-item label="平台类型" prop="type">
          <el-select
            v-model="formData.type"
            placeholder="请选择平台类型"
            class="w-full"
          >
            <el-option label="forum" value="forum" />
            <el-option label="article" value="article" />
          </el-select>
        </el-form-item>

        <el-form-item label="网络类型" prop="net_type">
          <el-select
            v-model="formData.net_type"
            placeholder="请选择网络类型"
            class="w-full"
          >
            <el-option label="明网" value="明网" />
            <el-option label="Tor" value="Tor" />
          </el-select>
        </el-form-item>

        <el-form-item label="平台状态" prop="status">
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

        <el-form-item label="平台URL" prop="url">
          <el-input
            v-model="formData.url"
            placeholder="请输入平台URL"
            clearable
          />
        </el-form-item>

        <el-form-item label="平台Logo" prop="logo">
          <el-input
            v-model="formData.logo"
            placeholder="请输入平台Logo URL"
            clearable
          />
        </el-form-item>

        <el-form-item label="平台分类" prop="category">
          <el-input
            v-model="formData.category"
            placeholder="请输入平台分类"
            clearable
          />
        </el-form-item>

        <el-form-item label="平台子分类" prop="sub_category">
          <el-input
            v-model="formData.sub_category"
            placeholder="请输入平台子分类"
            clearable
          />
        </el-form-item>

        <el-form-item label="信任度" prop="confidence">
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

        <el-form-item label="平台标签" prop="tags">
          <TagInput
            v-model="formData.tags"
            placeholder="输入标签后按回车或点击添加"
          />
        </el-form-item>

        <el-form-item label="爬虫名称" prop="spider_name">
          <el-input
            v-model="formData.spider_name"
            placeholder="请输入爬虫名称（可选）"
            clearable
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="handleDialogClose">取消</el-button>
          <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
            确定
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import FunctionalPageHeader from '@/components/page-header/FunctionalPageHeader.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { platformApi } from '@/api/platform'
import { getPaginatedData } from '@/utils/request'
import { getCosUrl } from '@/utils/cos'
import TagInput from '@/components/action/nodes/components/TagInput.vue'

export default {
  name: 'PlatformList',
  components: {
    Header,
    Icon,
    TagInput,
    FunctionalPageHeader
  },
  setup() {
    const router = useRouter()
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
      loading.value = true
      try {
        const result = await getPaginatedData(
          platformApi.getPlatformList,
          {
            page: pagination.value.page,
            page_size: pagination.value.pageSize
          }
        )
        
        platformList.value = result.items
        pagination.value = {
          ...pagination.value,
          ...result.pagination
        }
      } catch (error) {
        console.error('获取平台列表失败:', error)
        ElMessage.error('获取平台列表失败')
        platformList.value = []
      } finally {
        loading.value = false
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
      ElMessage.info('搜索功能暂未实现')
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
      logo: [
        { required: true, message: '请输入平台Logo', trigger: 'blur' }
      ],
      category: [
        { required: true, message: '请输入平台分类', trigger: 'blur' }
      ],
      sub_category: [
        { required: true, message: '请输入平台子分类', trigger: 'blur' }
      ]
    }

    const handleAddPlatform = () => {
      dialogVisible.value = true
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
        category: '',
        sub_category: '',
        confidence: 1,
        spider_name: ''
      }
    }

    const handleSubmit = async () => {
      if (!formRef.value) return
      
      try {
        await formRef.value.validate()
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
          category: formData.value.category,
          sub_category: formData.value.sub_category,
          confidence: formData.value.confidence,
          spider_name: formData.value.spider_name || null
        }
        
        await platformApi.createPlatform(submitData)
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
      }).catch(() => {
        // 用户取消
      })
    }

    const getStatusType = (status) => {
      const statusMap = {
        活跃: 'success',
        非活跃: 'danger',
        离线: 'info'
      }
      return statusMap[status] || 'info'
    }

    const formatDate = (dateString) => {
      if (!dateString) return '-'
      try {
        const date = new Date(dateString)
        return date.toLocaleDateString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit'
        })
      } catch (error) {
        return dateString
      }
    }

    const getLogoUrl = (logo) => {
      return getCosUrl(logo)
    }

    onMounted(() => {
      fetchPlatformList()
    })

    return {
      loading,
      searchKeyword,
      selectedStatus,
      selectedType,
      platformList,
      pagination,
      dialogVisible,
      formRef,
      formData,
      formRules,
      submitLoading,
      handlePageChange,
      handlePageSizeChange,
      handleSearch,
      handleAddPlatform,
      handleViewDetail,
      handleDeletePlatform,
      handleDialogClose,
      handleSubmit,
      getStatusType,
      formatDate,
      getLogoUrl
    }
  }
}
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
