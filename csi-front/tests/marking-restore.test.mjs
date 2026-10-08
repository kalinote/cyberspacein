import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { ref, computed, nextTick } from 'vue'

// 保留组合函数的真实逻辑，替换浏览器绘制和接口依赖，验证异步恢复竞态。
const source = readFileSync(new URL('../src/composables/useMarking.js', import.meta.url), 'utf8')
    .replace(/^import .*\r?\n/gm, '')
    .replace('export function useMarking', 'function useMarking')
const createComposable = new Function('ref', 'computed', 'nextTick', 'annotationApi', 'HTMLElement', `${source}\nreturn useMarking`)
const response = {
    code: 0,
    data: [{ id: 'marking-1', content: '批注', style: 'highlight', target: { region: 'clean', text_offset: { start: 0, end: 2, text: '正文' } } }],
}

test('清理后重新恢复只保留当前批注，清空选区工具栏', async () => {
    const useMarking = createComposable(ref, computed, nextTick, { list: async () => response }, class {})
    const marking = useMarking({ entityUuid: ref('article-1'), entityType: 'article' })
    await marking.loadAndRestoreMarkings(null, null, null)
    marking.toolbarVisible.value = true
    marking.clearAllMarkings()
    await marking.loadAndRestoreMarkings(null, null, null)
    assert.equal(marking.markings.value.length, 1)
    assert.equal(marking.toolbarVisible.value, false)
})

test('断点恢复的新请求先返回时，旧请求不能追加重复批注', async () => {
    const pending = []
    const useMarking = createComposable(ref, computed, nextTick, { list: () => new Promise(resolve => pending.push(resolve)) }, class {})
    const marking = useMarking({ entityUuid: ref('article-1'), entityType: 'article' })
    const older = marking.loadAndRestoreMarkings(null, null, null)
    marking.clearAllMarkings()
    const newer = marking.loadAndRestoreMarkings(null, null, null)
    pending[1](response)
    await newer
    pending[0](response)
    await older
    assert.equal(marking.markings.value.length, 1)
})

test('切换实体与离开页面后，未完成请求不能恢复旧批注', async () => {
    const pending = []
    const uuid = ref('article-1')
    const useMarking = createComposable(ref, computed, nextTick, { list: () => new Promise(resolve => pending.push(resolve)) }, class {})
    const marking = useMarking({ entityUuid: uuid, entityType: 'article' })
    const older = marking.loadAndRestoreMarkings(null, null, null)
    uuid.value = 'article-2'
    pending[0](response)
    await older
    assert.equal(marking.markings.value.length, 0)
    const beforeUnmount = marking.loadAndRestoreMarkings(null, null, null)
    marking.clearAllMarkings()
    pending[1](response)
    await beforeUnmount
    assert.equal(marking.markings.value.length, 0)
})
