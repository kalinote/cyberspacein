import { request } from '@/utils/request'

export const systemApi = {
  getUsers(params) {
    return request.get('/system/users', params)
  },
  createUser(data) {
    return request.post('/system/users', data)
  },
  updateUser(userId, data) {
    return request.put(`/system/users/${userId}`, data)
  },
  patchUserStatus(userId, data) {
    return request.patch(`/system/users/${userId}/status`, data)
  },

  getGroups(params) {
    return request.get('/system/groups', params)
  },
  createGroup(data) {
    return request.post('/system/groups', data)
  },
  updateGroup(groupId, data) {
    return request.put(`/system/groups/${groupId}`, data)
  }
}

