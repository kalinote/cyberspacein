// Socket 类型配置常量
export const SOCKET_TYPE_CONFIGS = [
  { socket_type: 'basic_type_boolean', color: '#409eff', custom_style: {} },
  { socket_type: 'platform', color: '#409eff', custom_style: {} },
  { socket_type: 'keywords', color: '#f56c6c', custom_style: {} },
  { socket_type: 'crawler_results', color: '#67c23a', custom_style: {} },
  { socket_type: 'generic_data', color: '#ff69b4', custom_style: {} },
  { socket_type: 'rabbitmq_data', color: '#ff9800', custom_style: {} },
  { socket_type: 'es_data', color: '#722ed1', custom_style: {} },
  { socket_type: 'mongo_data', color: '#13c2c2', custom_style: {} },
  { socket_type: 'condition', color: '#00fa9a', custom_style: {} }
]

// 输入类型默认值
export const INPUT_TYPE_DEFAULTS = {
  'int': null,
  'string': '',
  'textarea': '',
  'select': null,
  'checkbox': false,
  'checkbox-group': [],
  'radio-group': null,
  'boolean': false,
  'datetime': null,
  'tags': [],
  'conditions': []
}

// 输入类型列表
export const INPUT_TYPES = [
  'int', 'string', 'textarea', 'select', 'checkbox', 
  'checkbox-group', 'radio-group', 'boolean', 'datetime', 
  'tags', 'conditions'
]

