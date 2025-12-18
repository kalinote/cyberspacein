# API 配置说明

## 概述

本项目已配置完整的 API 请求层，支持从后端接口获取数据。

## 文件结构

```
src/
├── utils/
│   └── request.js        # axios 配置和请求拦截器
├── api/
│   └── action.js         # 行动相关的 API 接口定义
└── views/
    └── action/
        └── ActionResourceConfig.vue  # 使用 API 的页面示例
```

## 环境配置

### 配置文件

- `.env.development` - 开发环境配置
- `.env.production` - 生产环境配置

### 配置项

```env
VITE_API_BASE_URL=http://192.168.31.51:8080/api/v1
```

## 接口响应格式

### 标准格式

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

- `code`: 0 表示成功，非 0 表示失败
- `message`: 成功时为 "success"，失败时为错误信息
- `data`: 具体返回数据

### 分页格式

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

## 使用示例

### 1. 基础请求

```javascript
import { request } from '@/utils/request'

// GET 请求
const response = await request.get('/path', { param1: 'value1' })

// POST 请求
const response = await request.post('/path', { data: 'value' })

// PUT 请求
const response = await request.put('/path', { data: 'value' })

// DELETE 请求
const response = await request.delete('/path')
```

### 2. 使用 API 服务

```javascript
import { actionApi } from '@/api/action'

// 获取基础组件列表
const response = await actionApi.getBaseComponents({
  page: 1,
  page_size: 10
})

// 获取单个组件详情
const response = await actionApi.getComponentById('component_id')

// 创建组件
const response = await actionApi.createComponent(data)

// 更新组件
const response = await actionApi.updateComponent('component_id', data)

// 删除组件
const response = await actionApi.deleteComponent('component_id')
```

### 3. 分页数据处理

```javascript
import { getPaginatedData } from '@/utils/request'
import { actionApi } from '@/api/action'

const result = await getPaginatedData(
  actionApi.getBaseComponents,
  { page: 1, page_size: 10 }
)

console.log(result.items)        // 数据列表
console.log(result.pagination)   // 分页信息
```

### 4. 在组件中使用

```vue
<script setup>
import { ref, onMounted } from 'vue'
import { actionApi } from '@/api/action'
import { getPaginatedData } from '@/utils/request'

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
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>
```

## 错误处理

请求拦截器会自动处理以下错误：

- 400: 请求参数错误
- 401: 未授权，请登录
- 403: 拒绝访问
- 404: 请求的资源不存在
- 500: 服务器错误
- 502: 网关错误
- 503: 服务不可用
- 504: 网关超时

所有错误都会通过 `ElMessage` 自动提示用户。

## 添加新接口

### 1. 在 API 文件中定义接口

在 `src/api/` 目录下创建或编辑对应的 API 文件：

```javascript
// src/api/your-module.js
import { request } from '@/utils/request'

export const yourApi = {
  // GET 请求
  getList(params) {
    return request.get('/your-path', params)
  },
  
  // POST 请求
  create(data) {
    return request.post('/your-path', data)
  },
  
  // PUT 请求
  update(id, data) {
    return request.put(`/your-path/${id}`, data)
  },
  
  // DELETE 请求
  delete(id) {
    return request.delete(`/your-path/${id}`)
  }
}
```

### 2. 在组件中使用

```vue
<script setup>
import { yourApi } from '@/api/your-module'

const handleAction = async () => {
  try {
    const response = await yourApi.getList({ page: 1 })
    console.log(response.data)
  } catch (error) {
    console.error(error)
  }
}
</script>
```

## 注意事项

1. 所有请求都会自动添加 `Content-Type: application/json` 头
2. 请求超时时间为 30 秒
3. 响应拦截器会自动处理 `code !== 0` 的情况，并显示错误信息
4. 如需修改 API 基础地址，请编辑 `.env.development` 或 `.env.production` 文件
5. 环境变量修改后需要重启开发服务器才能生效
