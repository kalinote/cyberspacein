import { request } from '@/utils/request'

export const actionScheduleApi = {
  getSchedules(params = {}) {
    return request.get('/action/schedules', params)
  },
  getSchedule(scheduleId) {
    return request.get(`/action/schedules/${scheduleId}`)
  },
  createSchedule(data) {
    return request.post('/action/schedules', data)
  },
  updateSchedule(scheduleId, data) {
    return request.patch(`/action/schedules/${scheduleId}`, data)
  },
  deleteSchedule(scheduleId) {
    return request.delete(`/action/schedules/${scheduleId}`)
  },
  previewSchedule(data) {
    return request.post('/action/schedules/preview', data)
  },
  getRuns(params = {}) {
    return request.get('/action/schedules/runs', params)
  },
  getSummary() {
    return request.get('/action/schedules/summary')
  },
  getStatus() {
    return request.get('/action/schedules/status')
  }
}
