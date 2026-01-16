<template>
  <div class="min-h-screen bg-gray-50">
    <Header />
    
    <section class="bg-linear-to-br from-blue-50 to-white py-6 border-b border-gray-200">
      <div class="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8">
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
                <span class="text-blue-500">平台</span>列表
              </h1>
              <p class="text-sm text-gray-600">统一管理所有平台信息，查看平台详情、状态和统计数据</p>
            </div>
          </div>
        </div>
      </div>
    </section>

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
              placeholder="全部状态"
              clearable
              class="w-full"
            >
              <el-option label="全部状态" value="" />
              <el-option label="正常" value="正常" />
              <el-option label="异常" value="异常" />
              <el-option label="维护中" value="维护中" />
              <el-option label="已停用" value="已停用" />
            </el-select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">类型筛选</label>
            <el-select
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
                :key="platform.uuid"
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
                <el-button type="primary" link size="small" class="flex-1" @click="handleViewDetail(platform.uuid)">
                  <template #icon><Icon icon="mdi:eye" /></template>
                  查看详情
                </el-button>
                <el-button type="danger" link size="small" @click="handleDeletePlatform(platform.uuid)">
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
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import Header from '@/components/Header.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { platformApi } from '@/api/platform'
import { getPaginatedData } from '@/utils/request'
import { getCosUrl } from '@/utils/cos'

export default {
  name: 'PlatformList',
  components: {
    Header,
    Icon
  },
  setup() {
    const router = useRouter()
    const loading = ref(false)
    const searchKeyword = ref('')
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

    const handleAddPlatform = () => {
      ElMessage.info('新增平台功能暂未实现')
    }

    const handleViewDetail = (uuid) => {
      router.push(`/details/platform/${uuid}`)
    }

    const handleDeletePlatform = (uuid) => {
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
        正常: 'success',
        异常: 'danger',
        维护中: 'warning',
        已停用: 'info'
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
      platformList,
      pagination,
      handlePageChange,
      handlePageSizeChange,
      handleSearch,
      handleAddPlatform,
      handleViewDetail,
      handleDeletePlatform,
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
