export const styleColorMap = {
  underline: '#3b82f6',
  highlight: '#fef08a',
  box: '#10b981',
  bracket: '#8b5cf6',
  circle: '#f59e0b',
  'strike-through': '#ef4444'
}

export const activeStyleColorMap = {
  underline: '#1d4ed8',
  highlight: '#d97706',
  box: '#047857',
  bracket: '#6d28d9',
  circle: '#c2410c',
  'strike-through': '#b91c1c'
}

export const styleIconMap = {
  underline: 'mdi:format-underline',
  highlight: 'mdi:format-color-highlight',
  box: 'mdi:border-all',
  bracket: 'mdi:code-brackets',
  circle: 'mdi:circle-outline',
  'strike-through': 'mdi:format-strikethrough'
}

export function getStyleColor(style, isActive = false) {
  if (isActive) {
    return activeStyleColorMap[style] || '#1d4ed8'
  }
  return styleColorMap[style] || '#3b82f6'
}

export function getStyleIcon(style) {
  return styleIconMap[style] || 'mdi:tag'
}

export function createAnnotationConfig(style, isMultiline = false) {
  const config = {
    type: style,
    color: getStyleColor(style),
    strokeWidth: 2,
    animate: true,
    padding: style === 'bracket' ? 6 : 2
  }

  if (style === 'highlight' && isMultiline) {
    config.multiline = true
  }

  if (style === 'bracket') {
    config.brackets = ['left', 'right']
  }

  return config
}
