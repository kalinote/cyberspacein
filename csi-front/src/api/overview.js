import { request } from '@/utils/request'

export const overviewApi = {
  getSummaryStatus() {
    return request.get('/overview/summary-status')
  },
  getPlatformStatus() {
    return request.get('/overview/platform-status')
  },
  getNewDataStatus(params) {
    return request.get('/overview/new-data-status', params)
  }
}
