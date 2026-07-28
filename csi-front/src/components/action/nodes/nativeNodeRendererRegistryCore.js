import { markRaw } from 'vue'

const renderers = new Map()

export const registerNativeNodeRenderer = (key, contractVersion, component) => {
  const registryKey = `${key}@${contractVersion}`
  const current = renderers.get(registryKey)
  if (current && current !== component) {
    throw new Error(`原生节点渲染器重复注册：${registryKey}`)
  }
  renderers.set(registryKey, markRaw(component))
}

export const resolveNativeNodeRenderer = (nodeDefinition) => {
  const extension = nodeDefinition?.extension
  if (!extension) return null
  return renderers.get(`${extension.renderer_key}@${extension.contract_version}`) || null
}
