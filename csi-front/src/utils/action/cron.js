import cronstrue from 'cronstrue/i18n'
import { CronExpressionParser } from 'cron-parser'

export function cronToDescription(cronExpression, locale = 'zh_CN') {
  if (!cronExpression || typeof cronExpression !== 'string') return null
  const expr = cronExpression.trim()
  if (!expr) return null
  try {
    return cronstrue.toString(expr, { locale })
  } catch {
    return null
  }
}

export function getNextCronRun(cronExpression) {
  if (!cronExpression || typeof cronExpression !== 'string') return null
  const expr = cronExpression.trim()
  if (!expr) return null
  try {
    const expression = CronExpressionParser.parse(expr, { currentDate: new Date() })
    const next = expression.next()
    return next ? next.toDate() : null
  } catch {
    return null
  }
}
