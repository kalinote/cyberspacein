import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { parse } from 'vue/compiler-sfc'
import { PERM } from '../src/utils/permissions.js'
import * as reasoning from '../src/utils/agent/reasoningEffort.js'
import * as skillTree from '../src/utils/skillFileTree.js'

/** """读取真实组件逻辑并仅替换导入，保持提交和生命周期实现参与测试。""" */
function scriptOf(path) {
  return parse(readFileSync(new URL(path, import.meta.url), 'utf8')).descriptor.scriptSetup.content
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"]\s*$/gm, '')
    .replaceAll('import.meta.env.VITE_SANDBOX_HOST', 'undefined')
}
const configScript = scriptOf('../src/views/agent/AgentConfig.vue')

/** """从真实权限目录建立授权集合，未定义的权限键不会被管理员测试替身放行。""" */
function permissionFixture() {
  const values = [PERM], codes = new Set()
  while (values.length) {
    const value = values.pop()
    if (typeof value === 'string') codes.add(value)
    else if (value && typeof value === 'object') values.push(...Object.values(value))
  }
  return reactive(codes)
}

/** """以固定内存接口运行配置页，不连接后端或读取真实凭据。""" */
function configHarness(overrides = {}) {
  const hooks = {}, events = [], denied = reactive(new Set()), granted = permissionFixture()
  const defaultApi = async () => ({ code: 0, data: { items: [], total: 0, page: 1, page_size: 10 } })
  const api = new Proxy(overrides, { get: (target, key) => target[key] || defaultApi })
  const dependencies = {
    ref, computed, nextTick, watch,
    onMounted: () => {}, onActivated: fn => { hooks.activate = fn }, onDeactivated: fn => { hooks.deactivate = fn }, onBeforeUnmount: fn => { hooks.unmount = fn },
    defineOptions: () => {}, useMobileViewport: () => ({ isMobile: ref(true) }),
    findNavItemByKey: (items, key) => items.find(item => item.key === key),
    ElMessage: { success: value => events.push(value), error: value => events.push(value), warning: value => events.push(value), info: value => events.push(value) },
    ElMessageBox: { confirm: async () => {} },
    agentApi: api, PERM, hasPerm: permission => granted.has(permission) && !denied.has(permission),
    getPaginatedData: async (request, params) => { const response = await request(params); return { items: response.data?.items || [], pagination: { total: response.data?.total || 0 } } },
    formatDateTime: value => value, formatJson: value => JSON.stringify(value), filterByKeyword: items => items, ACTION_STATUS: {},
    console: { error: () => {} }, ...reasoning,
  }
  const state = new Function(...Object.keys(dependencies), `${configScript}\nreturn { activeTab, searchKeyword, fetchModelList, modelList, modelPagination, modelListLoading, configListErrors, mobileConfigPermissions, openModelEdit, modelFormData, modelDialogVisible, modelSubmitLoading, agentFormRef, agentFormData, editingAgentId, handleAgentSubmit, agentJsonValid, openAgentEdit, workspaceFormRef, workspaceFormData, editingWorkspaceId, handleWorkspaceSubmit, promptTemplateFormRef, promptTemplateFormData, editingPromptTemplateId, handlePromptTemplateSubmit, modelDetail, modelDetailVisible, openModelDetail, loadAgentWorkspaceDetail, hasConfigPermission, modelFormRef, modelFormRules, editingModelId, handleModelSubmit, handleMobileConfigAction, openAgentDetail, agentDetail, agentDetailVisible, openWorkspaceDetail, workspaceDetail, workspaceDetailVisible, openSystemPromptDetail, systemPromptDetail, systemPromptDetailVisible, openSkillDetail, skillDetail, skillDetailVisible, openPromptTemplateDetail, promptTemplateDetail, promptTemplateDetailVisible, handleViewSandbox, sandboxDetailData, sandboxDetailDialogVisible, getResourceCount };`)(...Object.values(dependencies))
  return { ...state, hooks, events, denied, granted }
}

test('配置列表失败保留资料并提供明确错误，有效空结果才清空', async () => {
  let fail = false
  const state = configHarness({ getModelList: async () => { if (fail) throw new Error('网络中断'); return { code: 0, data: { items: [{ id: '模型甲' }], total: 1 } } } })
  await state.fetchModelList()
  fail = true
  await state.fetchModelList()
  assert.deepEqual(state.modelList.value, [{ id: '模型甲' }])
  assert.match(state.configListErrors.value.modelResources, /网络中断/)
  assert.equal(state.modelListLoading.value, false)
  const empty = configHarness({ getModelList: async () => ({ items: [], total: 0, page: 1 }) })
  await empty.fetchModelList()
  assert.deepEqual(empty.modelList.value, [])
  assert.equal(empty.configListErrors.value.modelResources, '')
})

test('手机目录区分未知与零，已加载总数不被筛选结果或错误统计字段覆盖', async () => {
  let total = 2, fail = false
  const state = configHarness({ getModelList: async () => {
    if (fail) throw new Error('网络中断')
    return { items: [], total, page: 1 }
  } })
  assert.equal(state.getResourceCount('modelResources'), -1)
  assert.equal(state.getResourceCount('promptTemplates'), -1)
  await state.fetchModelList()
  assert.equal(state.getResourceCount('modelResources'), 2)
  state.searchKeyword.value = '没有匹配项'
  total = 0
  await state.fetchModelList()
  assert.equal(state.getResourceCount('modelResources'), 2)
  state.searchKeyword.value = ''
  await state.fetchModelList()
  assert.equal(state.getResourceCount('modelResources'), 0)
  fail = true
  await state.fetchModelList()
  assert.equal(state.getResourceCount('modelResources'), -1)
  fail = false
  total = undefined
  await state.fetchModelList()
  assert.equal(state.getResourceCount('modelResources'), -1)
})

test('新筛选请求胜出，缓存离开关闭面板并拒绝旧响应', async () => {
  const pending = []
  const state = configHarness({ getModelList: () => new Promise(resolve => pending.push(resolve)) })
  const oldLoad = state.fetchModelList()
  state.searchKeyword.value = '新关键词'
  const newLoad = state.fetchModelList()
  pending[1]({ data: { items: [{ id: '最新模型' }], total: 1 } })
  await newLoad
  pending[0]({ data: { items: [{ id: '过期模型' }], total: 1 } })
  await oldLoad
  assert.equal(state.modelList.value[0].id, '最新模型')
  state.modelDialogVisible.value = true
  const leaving = state.fetchModelList()
  state.hooks.deactivate()
  assert.equal(state.modelDialogVisible.value, false)
  pending[2]({ data: { items: [{ id: '离页响应' }], total: 1 } })
  await leaving
  assert.equal(state.modelList.value[0].id, '最新模型')
})

test('手机模型列表权限与凭据详情权限分别检查', async () => {
  const state = configHarness()
  state.activeTab.value = 'modelResources'
  assert.equal(state.mobileConfigPermissions.value.read, true)
  assert.equal(state.mobileConfigPermissions.value.update, true)
  state.denied.add(PERM.operations.agent.modelConfig.detailRead)
  assert.equal(state.mobileConfigPermissions.value.read, false)
  assert.equal(state.mobileConfigPermissions.value.update, false)
  await state.fetchModelList()
  assert.equal(state.configListErrors.value.modelResources, '')
})

test('八类配置使用真实权限目录，工具和沙盒不产生不存在的编辑权限', () => {
  const state = configHarness()
  const cases = [
    ['analysisEngines', PERM.operations.agent.agent, true, true],
    ['modelResources', { ...PERM.operations.agent.modelConfig, read: PERM.operations.agent.modelConfig.detailRead }, true, true],
    ['promptTemplates', PERM.operations.agent.promptTemplate, true, true],
    ['systemPrompts', PERM.operations.agent.systemPrompt, true, true],
    ['workspaces', PERM.operations.agent.workspace, true, true],
    ['skills', PERM.operations.agent.skill, true, true],
    ['tools', PERM.operations.agent.tool, false, false],
    ['sandboxes', PERM.operations.agent.sandbox, false, true],
  ]
  assert.equal(state.granted.has(undefined), false)
  assert.equal(state.granted.has('operation:agent:model-config:read'), false)
  for (const [key, permissions, update, remove] of cases) {
    state.activeTab.value = key
    assert.deepEqual(state.mobileConfigPermissions.value, { read: true, update, delete: remove }, key)
    state.denied.add(permissions.read)
    assert.deepEqual(state.mobileConfigPermissions.value, { read: false, update: false, delete: remove }, `${key} 失去读取权限`)
    state.denied.delete(permissions.read)
    if (update) {
      state.denied.add(permissions.update)
      assert.equal(state.mobileConfigPermissions.value.read, true)
      assert.equal(state.mobileConfigPermissions.value.update, false)
      state.denied.delete(permissions.update)
    }
  }
})

test('模型列表和详情返回时复核真实权限，撤权后的响应不回填', async () => {
  let finishList, finishDetail
  const state = configHarness({
    getModelList: () => new Promise(resolve => { finishList = resolve }),
    getModelDetail: () => new Promise(resolve => { finishDetail = resolve }),
  })
  const listing = state.fetchModelList()
  state.denied.add(PERM.operations.agent.modelConfig.listRead)
  finishList({ data: { items: [{ id: '无权回填' }], total: 1 } })
  await listing
  assert.deepEqual(state.modelList.value, [])
  assert.match(state.configListErrors.value.modelResources, /权限/)
  const opening = state.openModelDetail({ id: '模型甲' })
  state.denied.add(PERM.operations.agent.modelConfig.detailRead)
  finishDetail({ data: { id: '模型甲', name: '迟到详情' } })
  await opening
  assert.equal(state.modelDetail.value, null)
  assert.equal(state.modelDetailVisible.value, false)
})

test('各类详情读取在响应到达后重新检查权限', async () => {
  const cases = [
    ['openAgentDetail', 'getAgentDetail', 'agentDetail', 'agentDetailVisible', PERM.operations.agent.agent.read],
    ['openWorkspaceDetail', 'getWorkspaceDetail', 'workspaceDetail', 'workspaceDetailVisible', PERM.operations.agent.workspace.read],
    ['openSystemPromptDetail', 'getSystemPromptDetail', 'systemPromptDetail', 'systemPromptDetailVisible', PERM.operations.agent.systemPrompt.read],
    ['openSkillDetail', 'getSkillDetail', 'skillDetail', 'skillDetailVisible', PERM.operations.agent.skill.read],
    ['openPromptTemplateDetail', 'getPromptTemplateDetail', 'promptTemplateDetail', 'promptTemplateDetailVisible', PERM.operations.agent.promptTemplate.read],
    ['handleViewSandbox', 'getSandboxDetail', 'sandboxDetailData', 'sandboxDetailDialogVisible', PERM.operations.agent.sandbox.read],
  ]
  for (const [open, request, detail, visible, permission] of cases) {
    let finish, markRequested
    const requested = new Promise(resolve => { markRequested = resolve })
    const state = configHarness({ [request]: () => new Promise(resolve => { finish = resolve; markRequested() }) })
    const opening = state[open]({ id: '虚构配置', sandbox_id: '虚构沙盒' })
    await requested
    state.denied.add(permission)
    finish({ code: 0, data: { id: '无权回填' } })
    await opening
    assert.equal(state[detail].value, null, open)
    assert.equal(state[visible].value, false, open)
  }
})

test('模型详情权限与密钥权限分离，无密钥读取权限仍可保留原密钥编辑', async () => {
  const saved = []
  const state = configHarness({
    getModelDetail: async () => ({ data: { id: '模型甲', name: '测试模型', base_url: 'https://example.test', model: '测试型号', api_key: '仅内存虚构密钥' } }),
    updateModel: async (...args) => { saved.push(args); return { code: 0 } },
  })
  state.denied.add(PERM.operations.agent.modelConfig.secretRead)
  await state.openModelDetail({ id: '模型甲' })
  assert.equal(state.modelDetail.value.api_key, null)
  state.modelDetailVisible.value = false
  await state.openModelEdit({ id: '模型甲' })
  assert.equal(state.modelFormData.value.api_key, '')
  assert.equal(state.modelFormRules.value.api_key[0].required, false)
  state.modelFormRef.value = { validate: async () => true }
  await state.handleModelSubmit()
  assert.equal(saved.length, 1)
  assert.equal(saved[0][1].api_key, '')
  assert.equal(state.modelFormRules.value.api_key[0].required, true)
})

test('模型编辑提交前和返回后检查权限，验证期间撤权不写入也不清空草稿', async () => {
  let saved = 0, validateDone, saveDone
  const state = configHarness({ updateModel: () => { saved++; return new Promise(resolve => { saveDone = resolve }) } })
  state.editingModelId.value = '模型甲'
  state.modelDialogVisible.value = true
  state.modelFormData.value.name = '未保存草稿'
  state.modelFormRef.value = { validate: () => new Promise(resolve => { validateDone = resolve }) }
  const validating = state.handleModelSubmit()
  state.denied.add(PERM.operations.agent.modelConfig.detailRead)
  validateDone(true)
  await validating
  assert.equal(saved, 0)
  state.denied.delete(PERM.operations.agent.modelConfig.detailRead)
  state.modelFormRef.value = { validate: async () => true }
  const saving = state.handleModelSubmit()
  await nextTick()
  assert.equal(saved, 1)
  state.denied.add(PERM.operations.agent.modelConfig.update)
  saveDone({ code: 0 })
  await saving
  assert.equal(state.modelFormData.value.name, '未保存草稿')
  assert.equal(state.modelDialogVisible.value, true)
  assert.equal(state.events.includes('修改成功'), false)
})

test('关闭模型编辑后迟到详情不会回填旧对象，新一轮读取不被旧请求覆盖', async () => {
  const pending = []
  const state = configHarness({ getModelDetail: id => new Promise(resolve => pending.push({ id, resolve })) })
  const oldOpen = state.openModelEdit({ id: '旧模型' })
  state.modelDialogVisible.value = false
  const newOpen = state.openModelEdit({ id: '新模型' })
  pending[1].resolve({ data: { id: '新模型', name: '新名称', base_url: 'https://example.test', api_key: '虚构凭据', model: '测试模型' } })
  await newOpen
  pending[0].resolve({ data: { id: '旧模型', name: '旧名称', api_key: '过期虚构凭据' } })
  await oldOpen
  assert.equal(state.modelFormData.value.name, '新名称')
  assert.equal(state.modelFormData.value.api_key, '虚构凭据')
  assert.equal(state.modelSubmitLoading.value, false)
})

test('分析引擎提交保持提示词顺序、模型、技能与嵌套类型，不发送工作区变更', async () => {
  const saved = []
  const state = configHarness({ updateAgent: async (...args) => { saved.push(args); return { code: 0 } } })
  state.editingAgentId.value = '引擎甲'
  state.agentFormRef.value = { validate: async () => true }
  state.agentFormData.value = { workspace_id: '工作区甲', name: '分析引擎', description: '描述', agent_builtin_prompt_ids: ['指令乙', '指令甲'], prompt_template_id: '模板甲', model_config_id: '模型甲', llm_provider: 'anthropic', reasoning_effort: null, llm_config: { n: 0.2, enabled: false, list: [1, 'x'], nested: { value: null } }, tools: ['工具乙', '工具甲'], skills: ['技能甲'] }
  await state.handleAgentSubmit()
  assert.equal(saved[0][0], '引擎甲')
  assert.deepEqual(saved[0][1].agent_builtin_prompt_ids, ['指令乙', '指令甲'])
  assert.deepEqual(saved[0][1].llm_config, { n: 0.2, enabled: false, list: [1, 'x'], nested: { value: null } })
  assert.deepEqual(saved[0][1].skills, ['技能甲'])
  assert.equal(saved[0][1].reasoning_effort, null)
  assert.equal('workspace_id' in saved[0][1], false)
})

test('无效 JSON 或提交权限失效不会调用分析引擎写接口', async () => {
  let count = 0
  const state = configHarness({ createAgent: async () => { count++ } })
  state.agentFormRef.value = { validate: async () => true }
  state.agentJsonValid.value = false
  await state.handleAgentSubmit()
  state.agentJsonValid.value = true
  state.denied.add(PERM.operations.agent.agent.create)
  await state.handleAgentSubmit()
  assert.equal(count, 0)
})

test('工作区提交保留全部白名单，提示词模板保留系统和用户原文', async () => {
  const saved = []
  const state = configHarness({ updateWorkspace: async (_id, body) => { saved.push(body) }, updatePromptTemplate: async (_id, body) => { saved.push(body) } })
  state.editingWorkspaceId.value = '工作区甲'
  state.workspaceFormRef.value = { validate: async () => true }
  state.workspaceFormData.value = { name: '工作区', description: '说明', model_config_ids: ['模型甲'], prompt_template_ids: ['模板甲'], enabled_tools: ['工具甲'], enabled_skills: ['技能甲'] }
  await state.handleWorkspaceSubmit()
  assert.deepEqual(saved[0], { name: '工作区', description: '说明', model_config_ids: ['模型甲'], prompt_template_ids: ['模板甲'], enabled_tools: ['工具甲'], enabled_skills: ['技能甲'] })
  state.editingPromptTemplateId.value = '模板甲'
  state.promptTemplateFormRef.value = { validate: async () => true }
  state.promptTemplateFormData.value = { name: '模板', description: '说明', system_prompt: '# 原文\n  缩进', user_prompt: '{{ uuid }}\n第二行' }
  await state.handlePromptTemplateSubmit()
  assert.equal(saved[1].system_prompt, '# 原文\n  缩进')
  assert.equal(saved[1].user_prompt, '{{ uuid }}\n第二行')
})

test('JSON 编辑器保留数值布尔数组和嵌套对象，错误文本不回写', () => {
  const events = []
  const props = reactive({ modelValue: { temperature: 0.2 } })
  const state = new Function('ref', 'watch', 'defineProps', 'defineEmits', `${scriptOf('../src/components/agent/AgentConfigJsonField.vue')}\nreturn {text, error, updateValue};`)(ref, watch, () => props, () => (...args) => events.push(args))
  state.text.value = '{"enabled":false,"n":2,"a":[1,null],"o":{"x":"y"}}'
  state.updateValue()
  assert.deepEqual(events[0], ['update:modelValue', { enabled: false, n: 2, a: [1, null], o: { x: 'y' } }])
  events.length = 0
  state.text.value = '{ invalid'
  state.updateValue()
  assert.deepEqual(events, [['validity-change', false]])
  assert.match(state.error.value, /格式有误/)
})

test('手机面板首次异步加载形成基线，保存失败后仍保护未保存输入', async () => {
  const props = reactive({ draft: { name: '' }, busy: true, title: '编辑配置' })
  const visible = ref(true), hooks = {}
  const dependencies = { computed, nextTick, ref, watch, defineOptions: () => {}, defineProps: () => props, defineModel: () => visible, useMobileViewport: () => ({ isMobile: ref(true), keyboardOpen: ref(false), viewportHeight: ref(844) }), onBeforeRouteLeave: fn => { hooks.leave = fn }, onDeactivated: () => {}, ElMessageBox: { confirm: async () => { throw new Error('继续编辑') } } }
  const state = new Function(...Object.keys(dependencies), `${scriptOf('../src/components/agent/AgentConfigPanel.vue')}\nreturn {beginSession, dirty, requestClose};`)(...Object.values(dependencies))
  state.beginSession()
  props.draft = { name: '服务器配置' }
  props.busy = false
  await nextTick()
  assert.equal(state.dirty.value, false)
  props.draft.name = '本地修改'
  props.busy = true
  await nextTick()
  props.busy = false
  await nextTick()
  assert.equal(state.dirty.value, true)
  assert.equal(await hooks.leave(), false)
  await state.requestClose()
  assert.equal(visible.value, true)
  assert.equal(props.draft.name, '本地修改')
})

test('技能文件并发和权限变化不覆盖新文件或误清空未保存输入', async () => {
  const pending = [], saved = [], hooks = {}, granted = permissionFixture()
  let finishSave
  const dependencies = { computed, nextTick, ref, watch, defineProps: () => ({ modelValue: true, skillId: '技能甲', skillName: '技能' }), defineEmits: () => () => {}, onBeforeRouteLeave: fn => { hooks.leave = fn }, onBeforeUnmount: fn => { hooks.unmount = fn }, onDeactivated: () => {}, useMobileViewport: () => ({ isMobile: ref(true) }), ElMessage: { success: () => {}, error: () => {} }, ElMessageBox: { confirm: async () => {} }, PERM, hasPerm: permission => granted.has(permission), agentApi: { getSkillFileContent: (_id, path) => new Promise(resolve => pending.push({ path, resolve })), updateSkillFileContent: (...args) => { saved.push(args); return new Promise(resolve => { finishSave = resolve }) } }, ...skillTree }
  const state = new Function(...Object.keys(dependencies), `${scriptOf('../src/components/agent/SkillEditorDialog.vue')}\nreturn {selectFile, currentPath, editorContent, originalContent, handleSave, isDirty, loadError};`)(...Object.values(dependencies))
  const oldFile = state.selectFile('旧文件.md')
  const newFile = state.selectFile('SKILL.md')
  pending[1].resolve({ data: { content: '最新内容' } })
  await newFile
  pending[0].resolve({ data: { content: '迟到旧内容' } })
  await oldFile
  assert.equal(state.currentPath.value, 'SKILL.md')
  assert.equal(state.editorContent.value, '最新内容')
  state.editorContent.value = '准备保存'
  const saving = state.handleSave()
  state.editorContent.value = '保存时继续输入'
  finishSave({ code: 0 })
  await saving
  assert.deepEqual(saved[0], ['技能甲', 'SKILL.md', '准备保存'])
  assert.equal(state.originalContent.value, '准备保存')
  assert.equal(state.isDirty.value, true)
  const revokedRead = state.selectFile('README.md')
  granted.delete(PERM.operations.agent.skill.read)
  pending[2].resolve({ data: { content: '撤权后到达的文件' } })
  await revokedRead
  assert.equal(state.editorContent.value, '保存时继续输入')
  assert.match(state.loadError.value, /权限/)
  granted.add(PERM.operations.agent.skill.read)
  state.loadError.value = ''
  granted.delete(PERM.operations.agent.skill.update)
  await state.handleSave()
  assert.equal(saved.length, 1)
  granted.add(PERM.operations.agent.skill.update)
  const revokedWrite = state.handleSave()
  granted.delete(PERM.operations.agent.skill.update)
  finishSave({ code: 0 })
  await revokedWrite
  assert.equal(state.originalContent.value, '准备保存')
  assert.equal(state.isDirty.value, true)
})
