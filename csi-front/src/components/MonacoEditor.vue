<template>
    <div ref="editorContainer" class="monaco-editor-container"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import loader from '@monaco-editor/loader'

const props = defineProps({
    modelValue: {
        type: String,
        default: ''
    },
    readOnly: {
        type: Boolean,
        default: false
    },
    language: {
        type: String,
        default: 'html'
    }
})

const emit = defineEmits(['update:modelValue'])

const editorContainer = ref(null)
let editor = null
let monaco = null

const formatDocument = async () => {
    if (editor) {
        const wasReadOnly = editor.getOptions().get(monaco.editor.EditorOption.readOnly)
        
        if (wasReadOnly) {
            editor.updateOptions({ readOnly: false })
        }
        
        await editor.getAction('editor.action.formatDocument').run()
        
        if (wasReadOnly) {
            editor.updateOptions({ readOnly: true })
        }
    }
}

onMounted(async () => {
    monaco = await loader.init()
    
    editor = monaco.editor.create(editorContainer.value, {
        value: props.modelValue || '',
        language: props.language,
        readOnly: props.readOnly,
        theme: 'vs',
        minimap: { enabled: false },
        fontSize: 14,
        wordWrap: 'on',
        automaticLayout: true,
        scrollBeyondLastLine: false
    })

    editor.onDidChangeModelContent(() => {
        const value = editor.getValue()
        emit('update:modelValue', value)
    })
})

onBeforeUnmount(() => {
    if (editor) {
        editor.dispose()
    }
})

watch(() => props.modelValue, (newValue) => {
    if (editor && editor.getValue() !== newValue) {
        editor.setValue(newValue || '')
    }
})

watch(() => props.readOnly, (newValue) => {
    if (editor) {
        editor.updateOptions({ readOnly: newValue })
    }
})

watch(() => props.language, (newValue) => {
    if (editor && monaco) {
        monaco.editor.setModelLanguage(editor.getModel(), newValue)
    }
})

defineExpose({
    formatDocument
})
</script>

<style scoped>
.monaco-editor-container {
    width: 100%;
    min-height: 600px;
}
</style>