# 自定义行动节点组合控件开发指南

本文档介绍如何为行动流程系统创建自定义的组合输入控件。

## 概述

系统支持两种布局方式：

- **单行布局**：Label 和控件在同一行（如：数字输入、文本输入、下拉选择）
- **多行布局**：Label 在上方，控件在下方，带有分隔线（如：多行文本、标签输入器、复选框组）

## 快速开始

### 第一步：创建组件文件

在 `src/components/action/nodes/components/` 目录下创建新的 Vue 组件。

**文件位置示例**：
```
src/components/action/nodes/components/
├── TagInput.vue          # 已有的标签输入器
├── MyCustomInput.vue     # 你的新组件
└── InputRenderer.vue     # 主渲染器
```

### 第二步：实现组件

#### 基础模板

```vue
<template>
    <div class="my-custom-input">
        <!-- 你的 UI 实现 -->
    </div>
</template>

<script setup>
const props = defineProps({
    // 必需：当前值
    modelValue: {
        type: [String, Number, Boolean, Array, Object],
        required: true
    },
    // 必需：禁用状态
    disabled: {
        type: Boolean,
        default: false
    }
    // custom_props 中的所有属性会自动传入
    // 例如：placeholder, maxLength, customOption 等
})

// 必需：发送数据变化事件
const emit = defineEmits(['update:modelValue'])

// 数据变化时调用
const handleChange = (newValue) => {
    emit('update:modelValue', newValue)
}
</script>

<style scoped>
.my-custom-input {
    width: 100%;
}
</style>
```

### 第三步：注册组件

编辑 `src/components/action/nodes/components/InputRenderer.vue`：

```javascript
// 1. 导入组件
import TagInput from './TagInput.vue'
import MyCustomInput from './MyCustomInput.vue'  // 添加导入

// 2. 在 INPUT_TYPE_MAP 中注册
const INPUT_TYPE_MAP = {
    'int': 'el-input-number',
    'string': 'el-input',
    'textarea': 'el-input',
    'select': 'el-select',
    'tags': TagInput,
    'my-custom': MyCustomInput  // 注册你的组件
}

// 3. 如果是多行布局，添加到 MULTI_LINE_TYPES
const MULTI_LINE_TYPES = [
    'textarea', 
    'checkbox-group', 
    'radio-group', 
    'tags',
    'my-custom'  // 添加到多行布局列表
]
```

### 第四步：在节点配置中使用

在 `NewAction.vue` 的 `nodeTypeConfigs` 中添加：

```javascript
{
    id: 'my_field',
    type: 'my-custom',  // 对应 INPUT_TYPE_MAP 的 key
    position: 'center',
    label: '自定义字段',
    description: '这是一个自定义控件的描述',
    required: false,
    default: null,  // 默认值，类型要匹配
    custom_style: {},
    custom_props: {
        // 这些属性会自动传递给组件
        placeholder: '请输入内容',
        maxLength: 100,
        customOption: true
    }
}
```

## 完整示例：标签输入器

### 组件实现 (TagInput.vue)

```vue
<template>
    <div class="tag-input-container">
        <!-- 标签显示区 -->
        <div v-if="tags.length > 0" class="tags-display mb-2">
            <el-tag
                v-for="(tag, index) in tags"
                :key="index"
                closable
                @close="handleRemoveTag(index)"
                size="small"
                class="mr-1 mb-1"
            >
                {{ tag }}
            </el-tag>
        </div>
        
        <!-- 输入框 + 添加按钮 -->
        <div class="input-with-button flex gap-2">
            <el-input
                v-model="inputValue"
                :placeholder="placeholder"
                size="small"
                @keyup.enter="handleAddTag"
                :disabled="disabled"
                class="flex-1"
            />
            <el-button
                size="small"
                type="primary"
                @click="handleAddTag"
                :disabled="disabled || !inputValue.trim()"
            >
                添加
            </el-button>
        </div>
        
        <!-- 计数显示 -->
        <div v-if="showCount" class="text-xs text-gray-400 mt-1">
            已添加 {{ tags.length }} 项
            <span v-if="maxTags"> / 最多 {{ maxTags }} 项</span>
        </div>
    </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
    modelValue: {
        type: Array,
        default: () => []
    },
    placeholder: {
        type: String,
        default: '输入内容后按回车或点击添加'
    },
    maxTags: {
        type: Number,
        default: null
    },
    showCount: {
        type: Boolean,
        default: true
    },
    disabled: {
        type: Boolean,
        default: false
    }
})

const emit = defineEmits(['update:modelValue'])

const inputValue = ref('')
const tags = ref([...props.modelValue])

// 监听外部值变化
watch(() => props.modelValue, (newVal) => {
    tags.value = [...(newVal || [])]
}, { deep: true })

// 添加标签
const handleAddTag = () => {
    const value = inputValue.value.trim()
    if (!value) return
    
    if (tags.value.includes(value)) {
        ElMessage.warning('该标签已存在')
        return
    }
    
    if (props.maxTags && tags.value.length >= props.maxTags) {
        ElMessage.warning(`最多只能添加 ${props.maxTags} 个标签`)
        return
    }
    
    tags.value.push(value)
    emit('update:modelValue', tags.value)
    inputValue.value = ''
}

// 删除标签
const handleRemoveTag = (index) => {
    tags.value.splice(index, 1)
    emit('update:modelValue', tags.value)
}
</script>

<style scoped>
.tag-input-container {
    width: 100%;
}

.tags-display {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    min-height: 28px;
    padding: 4px;
    background-color: #f5f7fa;
    border-radius: 4px;
}
</style>
```

### 配置使用

```javascript
{
    id: 'platforms',
    type: 'tags',
    position: 'center',
    label: '平台列表',
    description: '输入平台名称后按回车或点击添加按钮',
    required: true,
    default: [],
    custom_props: {
        placeholder: '输入平台名称（如：bilibili、youtube）',
        maxTags: 10,
        showCount: true
    }
}
```

## 开发规范

### 必需实现

1. **Props**
   - `modelValue`: 当前值（必需）
   - `disabled`: 禁用状态（必需）

2. **Events**
   - `update:modelValue`: 值变化时触发（必需）

3. **响应性**
   - 正确处理外部 `modelValue` 的变化
   - 及时 emit 内部值的变化

### 建议实现

1. **默认值处理**
   ```javascript
   const value = computed(() => props.modelValue || defaultValue)
   ```

2. **验证逻辑**
   - 数据格式验证
   - 长度/数量限制
   - 用户提示

3. **样式规范**
   - 使用 Tailwind CSS 类名
   - 保持与系统一致的视觉风格
   - 响应式布局

## 布局选择

### 单行布局适用场景
- 简单输入（文本、数字）
- 单个选择（下拉框、开关）
- 占用空间小的控件

### 多行布局适用场景
- 复杂组合控件（多个交互元素）
- 需要更多展示空间（标签列表、多选项）
- 需要视觉分隔的独立区域

## 调试技巧

1. **查看传入的 props**
   ```vue
   <script setup>
   watch(() => props, (val) => {
       console.log('组件收到的 props:', val)
   }, { deep: true, immediate: true })
   </script>
   ```

2. **测试数据变化**
   ```javascript
   const handleChange = (newValue) => {
       console.log('发送新值:', newValue)
       emit('update:modelValue', newValue)
   }
   ```

3. **检查节点数据**
   - 在浏览器控制台使用 Vue DevTools
   - 查看 VueFlow 的节点 data 属性

## 常见问题

### Q: 组件没有显示？
A: 检查：
1. 是否正确导入和注册到 `INPUT_TYPE_MAP`
2. 节点配置中的 `type` 是否匹配
3. 是否有语法错误导致组件加载失败

### Q: 数据没有更新？
A: 检查：
1. 是否正确 emit `update:modelValue`
2. 是否直接修改了 props（不要这样做）
3. 是否正确使用 `v-model` 或 `:model-value/@update:model-value`

### Q: 样式不生效？
A: 检查：
1. 是否使用了 `scoped` 样式
2. 使用 `:deep()` 来修改子组件样式
3. 检查 Tailwind CSS 类名是否正确

## 参考

- 现有组件：`src/components/action/nodes/components/TagInput.vue`
- 渲染器：`src/components/action/nodes/components/InputRenderer.vue`
- 数据格式：`数据格式.jsonl`
