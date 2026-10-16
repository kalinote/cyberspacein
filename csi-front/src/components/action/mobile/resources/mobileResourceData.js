import { PERM } from '../../../../utils/permissions.js'

export const RESOURCE_PERMISSIONS = {
  nodes: { page: PERM.pages.action.resource.nodes, read: PERM.operations.action.node.read, create: PERM.operations.action.node.create, update: PERM.operations.action.node.update, delete: PERM.operations.action.node.delete },
  encapsulatedNodes: { page: PERM.pages.action.resource.encapsulatedNodes, read: PERM.operations.action.node.read, delete: PERM.operations.action.node.delete },
  baseComponents: { page: PERM.pages.action.resource.components, read: PERM.operations.action.node.read },
  nodeHandles: { page: PERM.pages.action.resource.handles, read: PERM.operations.action.config.read, create: PERM.operations.action.config.create },
  accounts: { page: PERM.pages.action.resource.accounts, read: PERM.operations.action.account.listRead, detail: PERM.operations.action.account.detailRead, create: PERM.operations.action.account.create, update: PERM.operations.action.account.update, delete: PERM.operations.action.account.delete },
}

/**
 * 将接口资料复制为移动表单，保持桌面使用的字段及默认值。
 * @param {string} kind 资源模块。
 * @param {object} data 已加载的详情，新增时为空。
 * @returns {object} 不会修改原详情的表单草稿。
 */
export function makeResourceDraft(kind, data = {}) {
  const copy = JSON.parse(JSON.stringify(data))
  if (kind === 'accounts') return {
    platform_id: copy.platform_id || '', account_name: copy.account_name || '',
    credentials: { username: '', password: '', phone: '', email: '', ...copy.credentials },
    rate_limit: { strategy: copy.rate_limit?.strategy || 'none', max_requests: copy.rate_limit?.max_requests ?? 0 },
  }
  if (kind === 'nodeHandles') return {
    handle_name: '', type: '', label: '', color: '#409EFF', custom_style: {}, other_compatible_interfaces: [], ...copy,
  }
  return {
    name: copy.name || '', description: copy.description || '', type: copy.type || '', version: copy.version || '1.0.0',
    command: copy.command || 'csi-component', command_args: Array.isArray(copy.command_args) ? copy.command_args : ['main:run'],
    related_components: Array.isArray(copy.related_components) ? copy.related_components : [], component_timeouts: copy.component_timeouts && typeof copy.component_timeouts === 'object' ? copy.component_timeouts : {}, default_configs: copy.default_configs && typeof copy.default_configs === 'object' ? copy.default_configs : {},
    handles: (copy.handles || []).map(handle => ({ id: handle.id || '', type: handle.type || '', relabel: handle.relabel || '', position: handle.position || '', custom_style: handle.custom_style && typeof handle.custom_style === 'object' ? handle.custom_style : {} })),
    inputs: (copy.inputs || []).map(input => ({ name: input.name || '', type: input.type || '', position: input.position || 'center', label: input.label || '', description: input.description || '', required: Boolean(input.required), options: Array.isArray(input.options) ? input.options : [], custom_style: input.custom_style && typeof input.custom_style === 'object' ? input.custom_style : {}, custom_props: input.custom_props && typeof input.custom_props === 'object' ? input.custom_props : {}, default: input.default == null ? '' : String(input.default) })),
  }
}

/**
 * 验证所有分组，错误定位到对应步骤，避免隐藏字段跳过校验。
 * @param {string} kind 资源模块。
 * @param {object} draft 完整表单。
 * @returns {object|null} 错误步骤及说明，通过时为空。
 */
export function validateResourceDraft(kind, draft) {
  if (kind === 'accounts') {
    if (!draft.platform_id || !draft.account_name.trim()) return { step: 0, message: '请选择平台并填写账号别名' }
    return null
  }
  if (kind === 'nodeHandles') {
    if (!/^[a-zA-Z][a-zA-Z0-9_]*$/.test(draft.handle_name)) return { step: 0, message: '接口名称须以英文字母开头，仅包含字母、数字和下划线' }
    if (!draft.type || !draft.label.trim()) return { step: 0, message: '请选择接口类型并填写标签' }
    return null
  }
  if (!draft.name.trim() || !draft.type || !draft.version.trim()) return { step: 0, message: '请填写节点名称、类型和版本号' }
  if (!draft.command.trim() || !draft.related_components.length) return { step: 1, message: '请填写运行命令并至少选择一个关联组件' }
  for (const [index, handle] of draft.handles.entries()) {
    if (!handle.id || !handle.type || !handle.position) return { step: 2, index, message: `请补全接口 ${index + 1} 的接口、方向和位置` }
  }
  for (const [index, input] of draft.inputs.entries()) {
    if (!/^[a-zA-Z][a-zA-Z0-9_]*$/.test(input.name) || !input.type || !input.position || !input.label.trim()) return { step: 3, index, message: `请补全输入项 ${index + 1}；字段名须以字母开头，仅含字母、数字和下划线` }
  }
  return null
}

/**
 * 构造与现有桌面一致的保存载荷，不引入新的后台能力。
 * @param {string} kind 资源模块。
 * @param {object} draft 表单草稿。
 * @returns {object} 创建或更新接口的字段。
 */
export function resourcePayload(kind, draft) {
  if (kind === 'accounts') return {
    platform_id: draft.platform_id, account_name: draft.account_name,
    credentials: Object.fromEntries(['username', 'password', 'phone', 'email'].filter(key => draft.credentials[key]).map(key => [key, draft.credentials[key]])),
    rate_limit: draft.rate_limit.strategy && draft.rate_limit.strategy !== 'none' ? { strategy: draft.rate_limit.strategy, max_requests: draft.rate_limit.max_requests ?? 0 } : {},
  }
  if (kind === 'nodeHandles') return {
    handle_name: draft.handle_name, type: draft.type, label: draft.label,
    ...(draft.color ? { color: draft.color } : {}),
    ...(Object.keys(draft.custom_style || {}).length ? { custom_style: draft.custom_style } : {}),
    other_compatible_interfaces: Array.isArray(draft.other_compatible_interfaces) ? draft.other_compatible_interfaces : [],
  }
  return {
    name: draft.name, description: draft.description || '', type: draft.type, version: draft.version,
    command: draft.command || '', command_args: draft.command_args || [], related_components: draft.related_components || [],
    component_timeouts: Object.fromEntries(draft.related_components.map(id => [id, Number(draft.component_timeouts[id]) || 0])),
    default_configs: draft.default_configs || {},
    handles: draft.handles.map(handle => ({ id: handle.id, type: handle.type, position: handle.position,
      ...(handle.relabel?.trim() ? { relabel: handle.relabel.trim() } : {}),
      ...(Object.keys(handle.custom_style || {}).length ? { custom_style: handle.custom_style } : {}),
    })),
    inputs: draft.inputs.map(input => ({ name: input.name, type: input.type, position: input.position, label: input.label,
      description: input.description || '', required: input.type === 'comment' ? false : (input.required || false),
      default: input.type === 'comment' ? '' : (input.default || ''), custom_style: input.custom_style || {}, custom_props: input.custom_props || {},
      ...(input.type === 'select' && input.options?.length ? { options: input.options } : {}),
    })),
  }
}
