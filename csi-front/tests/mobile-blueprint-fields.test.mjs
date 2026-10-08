import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { parse, compileScript, compileTemplate, babelParse } from 'vue/compiler-sfc'
import * as templatePolicy from '../src/utils/action/template.js'
import * as boundaryPolicy from '../src/utils/action/boundaryBinding.js'
import * as constants from '../src/utils/action/constants.js'

/**
 * 编译真实蓝图配置组件，隔离 UI 确认但保留 Vue 状态和领域工具。
 * @param {object} t 测试上下文。
 * @param {string} file 源组件路径。
 * @param {object} options 属性、注入数据和确认替身。
 * @returns {object} 状态、事件与生命周期。
 */
function mount(t, file, options = {}) {
  const { descriptor } = parse(readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'))
  const script = compileScript(descriptor, { id: file })
  const props = Vue.reactive({ disabled: false, params: [], bindings: {}, resizable: false, availableHandles: [], ...options.props })
  const events = [], hooks = [], notices = []
  const imports = {
    vue: { ...Vue, inject: key => options.inject?.[key] || null, onActivated() {}, onDeactivated: callback => hooks.push(callback), onBeforeUnmount: callback => hooks.push(callback) },
    'element-plus': { ElMessage: { success: value => notices.push(value) }, ElMessageBox: { confirm: options.confirm || (async () => {}), close() {} } },
    '@/composables/useMobileViewport': { useMobileViewport: () => ({ isMobile: Vue.ref(options.mobile !== false) }) },
    '@/utils/action/useVerticalResize': { useVerticalResize: () => ({ height: Vue.ref(300), isResizing: Vue.ref(false), startResize() {} }) },
    '@/utils/action/template': templatePolicy, '@/utils/action/boundaryBinding': boundaryPolicy, '@/utils/action/constants': constants,
  }
  let code = script.content
  for (const node of babelParse(code, { sourceType: 'module' }).program.body.toReversed()) {
    if (node.type !== 'ImportDeclaration') continue
    const module = node.source.value
    imports[module] ||= Object.fromEntries(node.specifiers.map(specifier => [specifier.imported?.name || 'default', { name: specifier.local.name }]))
    code = code.slice(0, node.start) + node.specifiers.map(specifier => `const ${specifier.local.name} = imports[${JSON.stringify(module)}][${JSON.stringify(specifier.imported?.name || 'default')}];`).join('\n') + code.slice(node.end)
  }
  const component = new Function('imports', code.replace('export default', 'return'))(imports)
  const scope = Vue.effectScope()
  const state = scope.run(() => component.setup(props, { expose() {}, emit: (...args) => events.push(args) }))
  const template = compileTemplate({ source: descriptor.template.content, filename: file, id: file, compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(template.errors, [])
  t.after(() => { hooks.forEach(callback => callback()); scope.stop() })
  return { state, props, events, hooks, notices }
}

const managerFile = 'components/action/template/TemplateParamsManager.vue'
const fieldsFile = 'components/action/mobile/MobileBlueprintNodeFields.vue'
const structuredFile = 'components/action/mobile/MobileBlueprintStructuredField.vue'
const rendererFile = 'components/action/nodes/components/InputRenderer.vue'
const bindingFile = 'components/action/BoundaryBindingDialog.vue'

test('参数重命名保留未知定义字段，并复制绑定更新而不提前修改父蓝图', async t => {
  const original = { id: 'parameter', name: 'old', label: '名称', type: 'string', required: true, options: [{ value: 'x' }], extension: { keep: true } }
  const page = mount(t, managerFile, { props: { params: [original], bindings: { node: { field: 'old', other: 'unknown' } } } })
  page.state.editParam(original)
  page.state.paramFormRef.value = { validate: async () => true, resetFields() {} }
  page.state.paramForm.value.name = 'new'
  await page.state.saveParam()
  assert.equal(page.props.bindings.node.field, 'old')
  const params = page.events.find(event => event[0] === 'update:params')[1]
  assert.deepEqual(params[0], { ...original, name: 'new', description: '' })
  assert.deepEqual(page.events.find(event => event[0] === 'update:bindings')[1], { node: { field: 'new', other: 'unknown' } })
})

test('参数删除保留原引用确认语义，取消或离页后的迟到确认不改蓝图', async t => {
  let accept, message = ''
  const param = { id: 'p', name: 'name' }
  const page = mount(t, managerFile, { props: { params: [param], bindings: { n: { f: 'name' } } }, confirm: text => { message = text; return new Promise(resolve => { accept = resolve }) } })
  page.state.confirmDeleteParam(param)
  assert.match(message, /1 个字段引用/)
  page.hooks.forEach(callback => callback())
  accept()
  await new Promise(setImmediate)
  assert.equal(page.events.length, 0)
  assert.equal(page.props.bindings.n.f, 'name')
})

test('参数校验失败回基础分组并保稿，关闭后的迟到校验不写回', async t => {
  let validate
  const page = mount(t, managerFile)
  page.state.showAddDialog.value = true
  page.state.mobileStep.value = 1
  page.state.paramForm.value.label = '草稿'
  page.state.paramFormRef.value = { validate: async () => false, resetFields() {} }
  await page.state.saveParam()
  assert.equal(page.state.mobileStep.value, 0)
  assert.equal(page.state.paramForm.value.label, '草稿')
  page.state.paramFormRef.value = { validate: () => new Promise(resolve => { validate = resolve }), resetFields() {} }
  const pending = page.state.saveParam()
  page.state.cancelParamDialog()
  validate(true)
  await pending
  assert.equal(page.events.length, 0)
})

test('字段分组遵循原边界隐藏规则，仅发出单字段修改且只读禁止修改', t => {
  const node = { id: 'node', data: { untouched: { keep: true }, boundaryBinding: { bound_node_id: 'target' }, config: { inputs: [{ id: 'plain', type: 'string' }, { id: 'hidden', type: 'string', custom_props: { hide_when_boundary_bound: true } }, { id: 'comment', type: 'comment', label: '高级' }, { id: 'advanced', type: 'int' }] } } }
  const page = mount(t, fieldsFile, { props: { node } })
  assert.deepEqual(page.state.groups.value.map(group => group.inputs.map(input => input.id)), [['plain'], ['comment', 'advanced']])
  page.state.changeField('hidden', '非法修改')
  page.state.changeField('comment', '非法修改')
  page.state.changeField('advanced', 0)
  assert.deepEqual(page.events, [['field-change', { inputId: 'advanced', value: 0 }]])
  assert.deepEqual(node.data.untouched, { keep: true })
  page.props.disabled = true
  page.state.changeField('plain', '禁止修改')
  assert.equal(page.events.length, 1)
})

test('JSON 单项无效时保稿，应用后保留其它未知值与原父对象', t => {
  const original = { nested: { a: true }, unknown: null, enabled: false }
  const page = mount(t, structuredFile, { props: { kind: 'key-value', modelValue: original } })
  page.state.edit('nested')
  page.state.draftValue.value = '{'
  page.state.apply()
  assert.equal(page.state.visible.value, true)
  assert.match(page.state.error.value, /JSON/)
  assert.equal(page.events.length, 0)
  page.state.draftValue.value = '{"a":false,"extra":0}'
  page.state.apply()
  assert.deepEqual(page.events[0], ['update:modelValue', { nested: { a: false, extra: 0 }, unknown: null, enabled: false }])
  assert.deepEqual(original.nested, { a: true })
  page.state.edit('enabled')
  assert.equal(page.state.draftMode.value, 'json')
  page.state.draftValue.value = 'true'
  page.state.apply()
  assert.equal(page.events[1][1].enabled, true)
})

test('条件逐项编辑保留未识别表达式，重复键和只读均不能改写集合', t => {
  const page = mount(t, structuredFile, { props: { kind: 'conditions', modelValue: ['field_with_underscore__gte=3', '既有未知表达式'] } })
  page.state.edit('0')
  page.state.draftValue.value = 'field_with_underscore__gte=4'
  page.state.apply()
  assert.deepEqual(page.events[0][1], ['field_with_underscore__gte=4', '既有未知表达式'])
  const object = mount(t, structuredFile, { props: { kind: 'key-value', modelValue: { a: 0, b: false } } })
  object.state.edit('a')
  object.state.draftKey.value = 'b'
  object.state.apply()
  assert.equal(object.events.length, 0)
  assert.match(object.state.error.value, /已存在/)
  object.props.disabled = true
  object.state.remove()
  assert.equal(object.events.length, 0)
})

test('手机字段保持模板注入契约和类型匹配，切回固定值只清除绑定而不清空原值', t => {
  const updates = []
  const context = { isTemplateMode: Vue.ref(true), availableParams: Vue.ref([{ name: 'template', type: 'int' }]), bindings: Vue.ref({ node: { count: 'template' } }), updateBinding: (...args) => updates.push(args) }
  const page = mount(t, rendererFile, { props: { nodeId: 'node', inputConfig: { name: 'count', type: 'int' }, modelValue: '0' }, inject: { templateContext: context } })
  assert.equal(page.state.currentMode.value, constants.PARAM_MODE.PARAM)
  assert.equal(page.state.normalizedModelValue.value, 0)
  page.state.toggleMode()
  assert.deepEqual(updates, [['node', 'count', null]])
  assert.equal(page.props.modelValue, '0')
  page.props.disabled = true
  page.state.toggleMode()
  page.state.handleParamChange('new')
  page.state.handleUpdate(3)
  assert.equal(updates.length, 1)
  assert.equal(page.events.length, 0)
})

test('边界绑定逐项选择保留稳定端口和原事件载荷，阻止重复确认及失效端口', t => {
  const boundary = { id: 'boundary', data: { interfacePortId: 'public', name: '原名称', config: { builtin_key: 'blueprint.input', inputs: [{ id: 'name', name: 'interface_name' }], handles: [{ id: 'handle', port_id: 'stable-boundary', type: 'source' }] } } }
  const page = mount(t, bindingFile, { props: { modelValue: true, boundaryNode: boundary, targetNode: { id: 'target' }, availableHandles: [{ id: 'old', port_id: 'stable-target' }] } })
  assert.equal(page.state.form.interfaceName, '原名称')
  page.state.form.interfaceName = ' 新名称 '
  page.state.togglePort('missing', true)
  assert.equal(page.state.canSubmit.value, false)
  page.state.submit()
  assert.equal(page.events.length, 0)
  page.state.togglePort('missing', false)
  page.state.togglePort('stable-target', true)
  page.state.submit()
  page.state.submit()
  assert.deepEqual(page.events, [['confirm', { interfaceName: '新名称', targetPortIds: ['stable-target'], interfacePortId: 'public', boundaryHandleId: 'stable-boundary' }], ['update:modelValue', false]])
  page.state.handleClosed()
  assert.equal(page.events.filter(event => event[0] === 'cancel').length, 0)
})

test('未应用的结构化字段和模板参数登记离页草稿，取消、还原和卸载清理登记', t => {
  const drafts = Vue.reactive(new Map())
  const field = mount(t, structuredFile, { props: { kind: 'key-value', modelValue: { key: '原值' } }, inject: { blueprintLocalDrafts: drafts } })
  field.state.edit('key')
  assert.equal(drafts.size, 0)
  field.state.draftValue.value = '未应用'
  assert.equal(drafts.size, 1)
  const signature = [...drafts.values()][0]
  field.state.draftValue.value = '继续输入'
  assert.notEqual([...drafts.values()][0], signature)
  field.state.draftValue.value = '原值'
  assert.equal(drafts.size, 0)
  field.state.draftValue.value = '{'
  field.state.visible.value = false
  assert.equal(drafts.size, 0)
  const manager = mount(t, managerFile, { inject: { blueprintLocalDrafts: drafts } })
  manager.state.showAddDialog.value = true
  manager.state.paramForm.value.name = 'draft'
  assert.equal(drafts.size, 1)
  manager.state.cancelParamDialog()
  assert.equal(drafts.size, 0)
  manager.state.showAddDialog.value = true
  manager.state.paramForm.value.label = '尚未保存'
  manager.hooks.forEach(callback => callback())
  assert.equal(drafts.size, 0)
})
