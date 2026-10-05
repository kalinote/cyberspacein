import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import * as Vue from 'vue'
import { babelParse, compileScript, compileTemplate, parse } from 'vue/compiler-sfc'
import * as actionStatus from '../src/utils/action/status.js'
import * as actionFormatters from '../src/utils/action/formatters.js'
import { PERM } from '../src/utils/permissions.js'
import cronstrue from 'cronstrue/i18n.js'

/**
 * 编译真实组件，并替换网络请求和生命周期以验证状态与模板事件。
 * @param {string} path 相对于 src 的组件路径。
 * @param {object} options 模拟行动与调度接口、组件属性和权限。
 * @returns {object} 组件状态、生命周期、事件记录和模板渲染入口。
 */
function loadComponent(path, { api = {}, scheduleApi = {}, props = {}, canUpdate = true, deniedPermissions = [] } = {}) {
  const source = readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: path })
  const activated = []
  const mounted = []
  const events = []
  const messages = []
  const routes = []
  const imports = {
    vue: { ...Vue, onActivated: callback => activated.push(callback), onMounted: callback => mounted.push(callback) },
    'vue-router': { useRouter: () => ({ push: route => routes.push(route) }) },
    'element-plus': {
      ElMessage: { success: message => messages.push(message), error: message => messages.push(message) },
      ElMessageBox: { confirm: async () => {} }
    },
    '@/api/action': { actionApi: {
      getBlueprintsBaseInfo: async () => ({ code: 0, data: { items: [], total_pages: 0 } }),
      getActionHistory: async () => ({ code: 0, data: { items: [], total_pages: 0 } }),
      ...api
    } },
    '@/api/actionSchedule': { actionScheduleApi: {
      getSchedules: async () => ({ code: 0, data: { items: [], total_pages: 0 } }),
      ...scheduleApi
    } },
    '@/utils/action': {
      ...actionStatus, ...actionFormatters,
      cronToDescription: expression => cronstrue.toString(expression, { locale: 'zh_CN' })
    },
    '@/utils/permissions': { PERM },
    '@/utils/permissionKit': {
      hasPerm: permission => canUpdate && !deniedPermissions.includes(permission),
      hasAll: permissions => canUpdate && permissions.every(permission => !deniedPermissions.includes(permission))
    }
  }
  let code = script.content
  for (const node of babelParse(code, { sourceType: 'module' }).program.body.toReversed()) {
    if (node.type !== 'ImportDeclaration') continue
    const module = node.source.value
    imports[module] ||= Object.fromEntries(node.specifiers.map(specifier => [
      specifier.imported?.name || 'default', { name: specifier.local.name }
    ]))
    const declarations = node.specifiers.map(specifier => (
      `const ${specifier.local.name} = imports[${JSON.stringify(module)}][${JSON.stringify(specifier.imported?.name || 'default')}];`
    )).join('\n')
    code = code.slice(0, node.start) + declarations + code.slice(node.end)
  }
  const component = new Function('imports', code.replace('export default', 'return'))(imports)
  const state = component.setup(props, { expose() {}, emit: (...args) => events.push(args) })
  const template = compileTemplate({
    source: descriptor.template.content,
    filename: path,
    id: path,
    compilerOptions: { mode: 'function', bindingMetadata: script.bindings }
  })
  assert.deepEqual(template.errors, [])
  const render = new Function('Vue', template.code)({
    ...Vue, resolveComponent: name => ({ name }), resolveDirective: () => ({}), withDirectives: node => node
  })
  return { state, activated, mounted, events, messages, routes, render: () => render({}, [], props, Vue.proxyRefs(state)) }
}

/** 查找组件渲染树中的目标节点，供事件和展示数量断言复用。 */
function findNodes(tree, name) {
  if (Array.isArray(tree)) return tree.flatMap(node => findNodes(node, name))
  if (!tree || typeof tree !== 'object') return []
  const matches = tree.type === name || tree.type?.name === name ? [tree] : []
  return matches.concat(Array.isArray(tree.children) ? findNodes(tree.children, name) : [])
}

/**
 * 提取真实模板渲染的文本，用于校验板块顺序和数据可见性。
 * @param {object|Array|string} tree 组件渲染节点。
 * @returns {string} 按页面顺序排列的文本。
 */
function renderedText(tree) {
  if (Array.isArray(tree)) return tree.map(renderedText).join('')
  if (typeof tree === 'string') return tree
  if (!tree || typeof tree !== 'object' || tree.type === Vue.Comment) return ''
  return renderedText(tree.children?.default ? tree.children.default({ row: {} }) : tree.children)
}

for (const [format, wrapped] of [['统一响应封装', true], ['直接分页响应', false]]) {
  for (const count of [0, 1, 7, 205]) {
    test(`${format}：主页完整展示 ${count} 项置顶蓝图，跨页请求始终限定置顶`, async () => {
      const calls = []
      const items = Array.from({ length: count }, (_, id) => ({ id, name: `蓝图${id}`, is_pinned: true }))
      const page = loadComponent('views/action/ActionMonitor.vue', {
        api: { getBlueprintsBaseInfo: async params => {
          calls.push(params)
          const data = {
            items: items.slice((params.page - 1) * 100, params.page * 100),
            total: count,
            page: params.page,
            page_size: params.page_size,
            total_pages: Math.ceil(count / 100)
          }
          return wrapped ? { code: 0, message: 'success', data } : data
        } }
      })

      await page.state.fetchCommonBlueprints()

      assert.equal(page.state.loadingBlueprints.value, false)
      assert.deepEqual(page.messages, [])
      assert.deepEqual(page.state.commonBlueprints.value.map(item => item.id), items.map(item => item.id))
      assert.ok(page.state.commonBlueprints.value.every(item => item.isPinned))
      assert.equal(findNodes(page.render(), 'ActionBlueprintCard').length, count)
      assert.deepEqual(calls, Array.from({ length: Math.max(1, Math.ceil(count / 100)) }, (_, index) => ({
        page: index + 1, page_size: 100, is_pinned: true
      })))
    })
  }
}

test('后续分页失败时不展示部分结果，并结束加载状态', async () => {
  const calls = []
  const page = loadComponent('views/action/ActionMonitor.vue', {
    api: { getBlueprintsBaseInfo: async ({ page }) => {
      calls.push(page)
      if (page === 2) throw new Error('模拟后续分页失败')
      return { code: 0, message: 'success', data: { items: [{ id: '部分结果', is_pinned: true }], total_pages: 2 } }
    } }
  })
  page.state.commonBlueprints.value = [{ id: '旧蓝图', isPinned: true }]

  await page.state.fetchCommonBlueprints()

  assert.deepEqual(calls, [1, 2])
  assert.deepEqual(page.state.commonBlueprints.value, [])
  assert.equal(page.state.loadingBlueprints.value, false)
  assert.deepEqual(page.messages, ['获取行动蓝图失败'])
})

test('缓存主页每次激活都会刷新置顶蓝图、运行行动和已启用计划', async () => {
  let requests = 0
  let actionRequests = 0
  let scheduleRequests = 0
  const page = loadComponent('views/action/ActionMonitor.vue', {
    api: { getBlueprintsBaseInfo: async () => ({
      code: 0, message: 'success',
      data: { items: [{ id: ++requests, is_pinned: true }], total_pages: 1 }
    }), getActionHistory: async () => ({
      code: 0, data: { items: [{ id: ++actionRequests, status: actionStatus.ACTION_STATUS.RUNNING }], total_pages: 1 }
    }) },
    scheduleApi: { getSchedules: async () => ({
      code: 0, data: { items: [{ id: ++scheduleRequests, enabled: true }], total_pages: 1 }
    }) }
  })

  assert.ok(page.activated.length > 0)
  for (const expected of [1, 2]) {
    await Promise.all(page.activated.map(callback => callback()))
    assert.equal(page.state.commonBlueprints.value[0].id, expected)
    assert.equal(page.state.runningActions.value[0].id, expected)
    assert.equal(page.state.enabledSchedules.value[0].id, expected)
  }
})

for (const [format, wrapped] of [['统一响应封装', true], ['直接分页响应', false]]) {
  for (const count of [0, 4, 205]) {
    test(`${format}：完整展示 ${count} 项运行行动及已启用计划，每页均携带筛选条件`, async () => {
      const actionCalls = []
      const scheduleCalls = []
      const actions = Array.from({ length: count }, (_, id) => ({
        id: `行动${id}`, name: `运行行动${id}`, status: actionStatus.ACTION_STATUS.RUNNING,
        start_at: '2026-10-05T08:00:00+08:00', duration: 90, completed_steps: 2, total_steps: 4,
        progress: 50, scheduling_mode: 'streaming'
      }))
      const schedules = Array.from({ length: count }, (_, id) => ({
        id: `计划${id}`, name: `已启用计划${id}`, enabled: true, blueprint_name: `关联蓝图${id}`,
        schedule_type: id % 2 ? 'interval' : 'cron', cron_expression: '0 8 * * *',
        interval_seconds: 3600, timezone: 'Asia/Shanghai', priority: 5
      }))
      const page = loadComponent('views/action/ActionMonitor.vue', {
        api: { getActionHistory: async params => {
          actionCalls.push(params)
          const data = {
            items: actions.slice((params.page - 1) * 100, params.page * 100),
            total: count, page: params.page, page_size: 100, total_pages: Math.ceil(count / 100)
          }
          return wrapped ? { code: 0, data } : data
        } },
        scheduleApi: { getSchedules: async params => {
          scheduleCalls.push(params)
          const data = {
            items: schedules.slice((params.page - 1) * 100, params.page * 100),
            total: count, page: params.page, page_size: 100, total_pages: Math.ceil(count / 100)
          }
          return wrapped ? { code: 0, data } : data
        } }
      })

      await Promise.all([page.state.fetchRunningActions(), page.state.fetchEnabledSchedules()])

      assert.equal(page.state.loadingRunningActions.value, false)
      assert.equal(page.state.loadingSchedules.value, false)
      assert.deepEqual(page.messages, [])
      assert.deepEqual(page.state.runningActions.value.map(item => item.id), actions.map(item => item.id))
      assert.deepEqual(page.state.enabledSchedules.value.map(item => item.id), schedules.map(item => item.id))
      if (count) {
        assert.equal(page.state.runningActions.value[0].startTime, actions[0].start_at)
        assert.equal(page.state.runningActions.value[0].duration, 90000)
        assert.equal(page.state.runningActions.value[0].completedSteps, 2)
        assert.equal(page.state.runningActions.value[0].totalSteps, 4)
        assert.equal(page.state.runningActions.value[0].progress, 50)
        assert.equal(page.state.runningActions.value[0].schedulingMode, 'streaming')
      }
      const renderedNames = findNodes(page.render(), 'h3').map(renderedText)
      assert.deepEqual(renderedNames.filter(name => name.startsWith('运行行动')), actions.map(item => item.name))
      assert.deepEqual(renderedNames.filter(name => name.startsWith('已启用计划')), schedules.map(item => item.name))
      const pages = Array.from({ length: Math.max(1, Math.ceil(count / 100)) }, (_, index) => index + 1)
      assert.deepEqual(actionCalls, pages.map(page => ({ page, page_size: 100, status: actionStatus.ACTION_STATUS.RUNNING })))
      assert.deepEqual(scheduleCalls, pages.map(page => ({ page, page_size: 100, enabled: true })))
    })
  }
}

for (const [label, fetchName, stateName, loadingName, apiName, methodName, permission] of [
  ['运行行动', 'fetchRunningActions', 'runningActions', 'loadingRunningActions', 'api', 'getActionHistory', PERM.operations.action.instance.read],
  ['已启用计划', 'fetchEnabledSchedules', 'enabledSchedules', 'loadingSchedules', 'scheduleApi', 'getSchedules', PERM.operations.action.schedule.read]
]) {
  for (const failurePage of [1, 2]) {
    test(`${label}第 ${failurePage} 页失败时清空旧结果且不展示部分分页，结束加载状态`, async () => {
      const calls = []
      const page = loadComponent('views/action/ActionMonitor.vue', {
        [apiName]: { [methodName]: async ({ page }) => {
          calls.push(page)
          if (page === failurePage) throw new Error('模拟接口失败')
          return { code: 0, data: { items: [{ id: '不完整数据', status: 'running', enabled: true }], total_pages: 2 } }
        } }
      })
      page.state[stateName].value = [{ id: '旧数据', status: 'running', enabled: true }]

      await page.state[fetchName]()

      assert.deepEqual(calls, Array.from({ length: failurePage }, (_, index) => index + 1))
      assert.deepEqual(page.state[stateName].value, [])
      assert.equal(page.state[loadingName].value, false)
    })
  }

  test(`没有${label}读取权限时不调用接口`, async () => {
    const page = loadComponent('views/action/ActionMonitor.vue', {
      deniedPermissions: [permission],
      [apiName]: { [methodName]() { assert.fail('无读取权限时不应调用接口') } }
    })

    await page.state[fetchName]()

    assert.deepEqual(page.state[stateName].value, [])
    assert.equal(page.state[loadingName].value, false)
  })

  test(`${label}加载期间重复刷新只发起一次请求`, async () => {
    let requests = 0
    let complete
    const page = loadComponent('views/action/ActionMonitor.vue', {
      [apiName]: { [methodName]: () => {
        requests += 1
        return new Promise(resolve => { complete = resolve })
      } }
    })

    const pending = page.state[fetchName]()
    await page.state[fetchName]()
    assert.equal(requests, 1)
    assert.equal(page.state[loadingName].value, true)
    complete({ code: 0, data: { items: [], total_pages: 0 } })
    await pending
    assert.equal(page.state[loadingName].value, false)
  })
}

test('主页依次展示置顶蓝图、运行行动和启用计划，移除资源及监控占位信息', () => {
  const page = loadComponent('views/action/ActionMonitor.vue')
  const tree = page.render()

  assert.deepEqual(findNodes(tree, 'h2').map(renderedText), ['置顶行动蓝图', '正在运行的行动', '已启用的调度计划'])
  const text = renderedText(tree)
  for (const obsolete of ['代理网络', '全球接入节点', '采集账号', '沙盒容器', '当前行动状态', '资源使用热图', '3个代理节点响应异常']) {
    assert.equal(text.includes(obsolete), false)
  }
})

test('调度卡片展示 Cron 或固定间隔、关联蓝图与时区，并提供计划管理入口', () => {
  const page = loadComponent('views/action/ActionMonitor.vue')
  page.state.enabledSchedules.value = [
    {
      id: '每天执行', name: '每日采集', blueprint_name: '每日全量平台采集', blueprint_version: '1.0.0',
      enabled: true, schedule_type: 'cron', cron_expression: '0 8 * * *', timezone: 'Asia/Shanghai',
      priority: 5, next_run_at: '2026-10-06T00:00:00Z'
    },
    {
      id: '间隔执行', name: '定期采集', blueprint_name: '关键词采集', blueprint_version: '2.0.0',
      enabled: true, schedule_type: 'interval', interval_seconds: 3600, timezone: 'UTC', priority: 2
    }
  ]

  const tree = page.render()
  const cards = findNodes(tree, 'article').map(renderedText)
  assert.equal(cards.length, 2)
  for (const expected of ['每日采集', '每日全量平台采集（1.0.0）', 'Cron：0 8 * * *（在上午 08:00）', 'Asia/Shanghai', '优先级 5', '下次执行（本地时间）']) {
    assert.ok(cards[0].includes(expected), `每日计划应展示：${expected}`)
  }
  for (const expected of ['定期采集', '关键词采集（2.0.0）', '每 1小时0分钟执行', 'UTC', '优先级 2']) {
    assert.ok(cards[1].includes(expected), `间隔计划应展示：${expected}`)
  }
  assert.equal(findNodes(tree, 'el-switch').length, 0)
  const manageButton = findNodes(tree, 'el-button').find(button => renderedText(button).trim() === '管理调度计划')
  assert.ok(manageButton)
  manageButton.props.onClick()
  assert.deepEqual(page.routes, ['/action/component-tasks?tab=schedule'])
})

for (const [label, methodName] of [['暂停', 'pauseAction'], ['停止', 'stopAction']]) {
  test(`${label}成功后重新筛选运行行动并移除对应卡片`, async () => {
    let active = true
    const calls = []
    const page = loadComponent('views/action/ActionMonitor.vue', {
      api: {
        [methodName]: async id => {
          calls.push(id)
          active = false
          return { code: 0 }
        },
        getActionHistory: async params => {
          assert.equal(params.status, actionStatus.ACTION_STATUS.RUNNING)
          return { code: 0, data: { items: active ? [{ id: '运行中的行动', status: 'running' }] : [], total_pages: 1 } }
        }
      }
    })
    await page.state.fetchRunningActions()
    assert.equal(page.state.runningActions.value.length, 1)

    await page.state[methodName]('运行中的行动')

    assert.deepEqual(calls, ['运行中的行动'])
    assert.deepEqual(page.state.runningActions.value, [])
  })
}

test('置顶请求进行中阻止重复提交，成功后才通知父组件', async () => {
  const calls = []
  let complete
  const blueprint = { id: '置顶测试', isPinned: false }
  const button = loadComponent('components/action/BlueprintPinButton.vue', {
    props: { blueprint },
    api: { updateBlueprintPin: (...args) => {
      calls.push(args)
      return new Promise(resolve => { complete = resolve })
    } }
  })

  const pending = button.state.togglePin()
  await button.state.togglePin()
  assert.equal(button.state.saving.value, true)
  assert.deepEqual(calls, [['置顶测试', true]])
  assert.deepEqual(button.events, [])
  assert.equal(blueprint.isPinned, false)
  complete({ data: { is_pinned: true } })
  await pending

  assert.equal(button.state.saving.value, false)
  assert.deepEqual(button.events, [['change', true]])
  assert.deepEqual(button.messages, ['已置顶到主页（全局生效）'])
})

test('置顶保存失败保持原状态，并允许再次点击重试', async () => {
  let requests = 0
  const blueprint = { id: '失败测试', isPinned: true }
  const button = loadComponent('components/action/BlueprintPinButton.vue', {
    props: { blueprint },
    api: { updateBlueprintPin: async (_id, pinned) => {
      assert.equal(pinned, false)
      if (++requests === 1) throw new Error('模拟保存失败')
      return { data: { is_pinned: false } }
    } }
  })

  await button.state.togglePin()
  assert.equal(button.state.saving.value, false)
  assert.equal(blueprint.isPinned, true)
  assert.deepEqual(button.events, [])
  assert.deepEqual(button.messages, [])
  await button.state.togglePin()
  assert.deepEqual(button.events, [['change', false]])
})

test('没有更新权限时不提交置顶请求', async () => {
  const button = loadComponent('components/action/BlueprintPinButton.vue', {
    props: { blueprint: { id: '无权限', isPinned: false } }, canUpdate: false,
    api: { updateBlueprintPin() { assert.fail('无权限时不应调用接口') } }
  })

  await button.state.togglePin()

  assert.equal(button.state.saving.value, false)
  assert.deepEqual(button.events, [])
  assert.equal(button.render().type, Vue.Comment)
})

test('卡片传递取消置顶事件后，主页立即移除对应蓝图并保留其他蓝图', () => {
  const page = loadComponent('views/action/ActionMonitor.vue')
  page.state.commonBlueprints.value = [{ id: '取消', isPinned: true }, { id: '保留', isPinned: true }]
  const cards = findNodes(page.render(), 'ActionBlueprintCard')
  const card = loadComponent('components/action/ActionBlueprintCard.vue', { props: { blueprint: cards[0].props.blueprint } })
  const pin = findNodes(card.render(), 'BlueprintPinButton')[0]

  pin.props.onChange(false)
  assert.deepEqual(card.events, [['pin-change', false]])
  cards[0].props.onPinChange(card.events[0][1])

  assert.deepEqual(page.state.commonBlueprints.value.map(item => item.id), ['保留'])
  assert.equal(findNodes(page.render(), 'ActionBlueprintCard').length, 1)
})
