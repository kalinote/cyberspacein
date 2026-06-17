/**
 * 绑定 Monaco 编辑器与 Markdown 预览容器的比例滚动同步
 * @param {import('monaco-editor').editor.IStandaloneCodeEditor} editor
 * @param {HTMLElement} previewEl
 * @returns {() => void} 解除绑定
 */
export function bindMarkdownLiveScrollSync(editor, previewEl) {
  if (!editor || !previewEl) {
    return () => {}
  }

  let scrollSource = null

  const getEditorMaxScroll = () => {
    const layoutInfo = editor.getLayoutInfo()
    return Math.max(0, editor.getScrollHeight() - layoutInfo.height)
  }

  const getPreviewMaxScroll = () =>
    Math.max(0, previewEl.scrollHeight - previewEl.clientHeight)

  const syncToPreview = () => {
    if (scrollSource === 'preview') return

    const editorMax = getEditorMaxScroll()
    const previewMax = getPreviewMaxScroll()
    if (editorMax <= 0 || previewMax <= 0) return

    scrollSource = 'editor'
    const ratio = editor.getScrollTop() / editorMax
    previewEl.scrollTop = ratio * previewMax
    requestAnimationFrame(() => {
      scrollSource = null
    })
  }

  const syncToEditor = () => {
    if (scrollSource === 'editor') return

    const editorMax = getEditorMaxScroll()
    const previewMax = getPreviewMaxScroll()
    if (editorMax <= 0 || previewMax <= 0) return

    scrollSource = 'preview'
    const ratio = previewEl.scrollTop / previewMax
    editor.setScrollTop(ratio * editorMax)
    requestAnimationFrame(() => {
      scrollSource = null
    })
  }

  const editorDisposable = editor.onDidScrollChange(syncToPreview)
  previewEl.addEventListener('scroll', syncToEditor, { passive: true })

  return () => {
    editorDisposable.dispose()
    previewEl.removeEventListener('scroll', syncToEditor)
  }
}
