# 后端接口集成总结

## 修改概述

本次修改实现了从纯前端开发到对接后端接口的转变，建立了完整的 API 请求架构。

## 新增文件

### 1. `src/utils/request.js` - 请求工具
- 配置了 axios 实例
- 设置基础 URL 和超时时间
- 实现请求拦截器（预留认证 token 等功能）
- 实现响应拦截器，统一处理成功和失败响应
- 导出通用请求方法（get、post、put、delete、patch）
- 提供 `getPaginatedData` 工具函数处理分页数据

### 2. `src/api/action.js` - 行动相关 API
定义了以下接口：
- `getBaseComponents` - 获取基础组件列表（分页）
- `getComponentById` - 获取组件详情
- `createComponent` - 创建组件
- `updateComponent` - 更新组件
- `deleteComponent` - 删除组件
- `runComponent` - 运行组件
- `stopComponent` - 停止组件

### 3. 环境配置文件
- `.env.development` - 开发环境配置
- `.env.production` - 生产环境配置

### 4. 文档
- `docs/api_configuration.md` - API 配置详细说明
- `docs/backend_integration_summary.md` - 本文档

## 修改文件

### `src/views/action/ActionResourceConfig.vue`

#### 导入变化
```javascript
// 新增导入
import { onMounted } from 'vue'  // 添加生命周期钩子
import { actionApi } from '@/api/action'  // API 接口
import { getPaginatedData } from '@/utils/request'  // 分页工具
```

#### 数据变化
```javascript
// 添加加载状态
const loading = ref(false)

// 添加分页状态
const pagination = ref({
  page: 1,
  pageSize: 10,
  total: 0,
  totalPages: 0
})

// componentList 改为从接口获取，初始值为空数组
const componentList = ref([])
```

#### 新增方法
```javascript
// 获取组件列表
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
  } catch (error) {
    console.error('获取基础组件列表失败:', error)
    ElMessage.error('获取基础组件列表失败')
  } finally {
    loading.value = false
  }
}

// 页码变化处理
const handlePageChange = (page) => {
  pagination.value.page = page
  fetchComponentList()
}

// 每页数量变化处理
const handlePageSizeChange = (pageSize) => {
  pagination.value.pageSize = pageSize
  pagination.value.page = 1
  fetchComponentList()
}

// 组件挂载时获取数据
onMounted(() => {
  fetchComponentList()
})
```

#### 模板变化
- 添加 `v-loading` 加载状态指示器
- 添加分页组件 `el-pagination`
- 优化空数据显示逻辑

## API 配置

### 基础地址
- 开发环境: `http://192.168.31.51:8080/api/v1`
- 生产环境: `http://192.168.31.51:8080/api/v1`

可通过修改 `.env.development` 或 `.env.production` 文件来更改。

### 接口示例

**获取基础组件列表**
```
GET /action/resource_management/base_components?page=1&page_size=10
```

**返回格式**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 100,
    "page": 1,
    "page_size": 10,
    "total_pages": 10,
    "items": [
      {
        "id": "xxx",
        "name": "组件名称",
        "description": "组件描述",
        "status": "finished",
        "last_run_at": "2025-12-17T08:41:34.874000Z",
        "total_runs": 2,
        "average_runtime": 43
      }
    ]
  }
}
```

## 响应格式标准

### 普通响应
```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

### 分页响应
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 100,
    "page": 1,
    "page_size": 10,
    "total_pages": 10,
    "items": [...]
  }
}
```

### 错误响应
```json
{
  "code": 1001,
  "message": "错误信息",
  "data": null
}
```

## 使用示例

### 在其他页面中使用相同的模式

```vue
<script setup>
import { ref, onMounted } from 'vue'
import { actionApi } from '@/api/action'
import { getPaginatedData } from '@/utils/request'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const dataList = ref([])
const pagination = ref({
  page: 1,
  pageSize: 10,
  total: 0,
  totalPages: 0
})

const fetchData = async () => {
  loading.value = true
  try {
    const result = await getPaginatedData(
      actionApi.getBaseComponents,
      {
        page: pagination.value.page,
        page_size: pagination.value.pageSize
      }
    )
    
    dataList.value = result.items
    pagination.value = {
      ...pagination.value,
      ...result.pagination
    }
  } catch (error) {
    console.error('获取数据失败:', error)
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>
```

## 注意事项

1. **环境变量生效**: 修改 `.env` 文件后需要重启开发服务器
2. **跨域问题**: 如遇到跨域问题，需要后端配置 CORS 或前端配置代理
3. **认证机制**: 当前请求拦截器预留了认证位置，可在 `request.js` 中添加 token
4. **错误处理**: 所有接口错误都会自动通过 `ElMessage` 提示用户
5. **分页搜索**: 当使用搜索功能时，分页组件会隐藏，仅显示前端过滤后的结果

## 扩展建议

### 1. 添加 Token 认证
在 `src/utils/request.js` 的请求拦截器中添加：

```javascript
service.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  error => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)
```

### 2. 添加请求取消功能
对于列表页面的快速切换，可以添加请求取消逻辑避免竞态条件。

### 3. 添加请求缓存
对于不常变化的数据，可以考虑添加请求缓存机制。

### 4. 配置开发代理
如需要代理后端接口，可在 `vite.config.js` 中配置：

```javascript
export default {
  server: {
    proxy: {
      '/api': {
        target: 'http://192.168.31.51:8080',
        changeOrigin: true
      }
    }
  }
}
```

## 测试清单

- [x] 创建 axios 配置文件
- [x] 创建 API 接口定义文件
- [x] 修改页面使用 API 接口
- [x] 添加加载状态
- [x] 添加分页功能
- [x] 添加错误处理
- [x] 创建环境配置文件
- [x] 编写使用文档

## 后续工作

1. 根据后端实际返回数据调整接口响应处理
2. 为其他页面（如 ActionMonitor、NewAction）添加接口对接
3. 实现其他资源类型（代理网络、采集账号、沙盒容器）的接口对接
4. 添加认证和权限管理
5. 优化错误处理和用户体验
