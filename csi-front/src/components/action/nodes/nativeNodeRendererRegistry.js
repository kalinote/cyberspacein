import GenericNode from './GenericNode.vue'
import {
  registerNativeNodeRenderer,
  resolveNativeNodeRenderer
} from './nativeNodeRendererRegistryCore'

export { registerNativeNodeRenderer, resolveNativeNodeRenderer }

registerNativeNodeRenderer('schema', 1, GenericNode)
registerNativeNodeRenderer('analysis', 1, GenericNode)
