<template>
    <div ref="container" class="monaco-diff-editor-container" :style="{ height: `${minHeight}px` }"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import loader from '@monaco-editor/loader'

const props = defineProps({
    original: { type: String, default: '' },
    modified: { type: String, default: '' },
    language: { type: String, default: 'html' },
    minHeight: { type: Number, default: 600 }
})

const container = ref(null)
let diffEditor = null

const formatContent = async (monaco, content, language) => {
    const uri = monaco.Uri.parse(`inmemory://format/${Math.random().toString(36).slice(2)}`)
    const model = monaco.editor.createModel(content, language, uri)
    const tempContainer = document.createElement('div')
    document.body.appendChild(tempContainer)
    const tempEditor = monaco.editor.create(tempContainer, { model, language, automaticLayout: false })
    try {
        const action = tempEditor.getAction('editor.action.formatDocument')
        if (action) {
            await action.run()
        }
        return tempEditor.getValue()
    } finally {
        tempEditor.dispose()
        model.dispose()
        document.body.removeChild(tempContainer)
    }
}

onMounted(async () => {
    const monaco = await loader.init()

    const formattedOriginal = await formatContent(monaco, props.original || '', props.language)
    const formattedModified = await formatContent(monaco, props.modified || '', props.language)

    diffEditor = monaco.editor.createDiffEditor(container.value, {
        readOnly: true,
        renderSideBySide: true,
        theme: 'vs',
        minimap: { enabled: false },
        fontSize: 14,
        wordWrap: 'on',
        automaticLayout: true,
        scrollBeyondLastLine: false
    })

    const originalModel = monaco.editor.createModel(formattedOriginal, props.language)
    const modifiedModel = monaco.editor.createModel(formattedModified, props.language)

    diffEditor.setModel({ original: originalModel, modified: modifiedModel })
})

onBeforeUnmount(() => {
    if (diffEditor) {
        diffEditor.dispose()
    }
})
</script>

<style scoped>
.monaco-diff-editor-container {
    width: 100%;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
}
</style>
