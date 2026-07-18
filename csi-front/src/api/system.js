import { request } from '@/utils/request'

export const systemApi = {
  getUsers(params) {
    return request.get('/system/users', params)
  },
  getUser(userId) {
    return request.get(`/system/users/${userId}`)
  },
  createUser(data) {
    return request.post('/system/users', data)
  },
  updateUserProfile(userId, data) {
    return request.patch(`/system/users/${userId}/profile`, data)
  },
  updateUserGroups(userId, data) {
    return request.patch(`/system/users/${userId}/groups`, data)
  },
  resetUserPassword(userId, data) {
    return request.post(`/system/users/${userId}/password`, data)
  },
  patchUserStatus(userId, data) {
    return request.patch(`/system/users/${userId}/status`, data)
  },
  patchUserExpiry(userId, data) {
    return request.patch(`/system/users/${userId}/expiry`, data)
  },
  patchAssignmentScope(userId, data) {
    return request.patch(`/system/users/${userId}/assignment-scope`, data)
  },
  deleteUser(userId) {
    return request.delete(`/system/users/${userId}`)
  },
  getUserSessions(userId, params) {
    return request.get(`/system/users/${userId}/sessions`, params)
  },
  terminateUserSessions(userId) {
    return request.post(`/system/users/${userId}/sessions/terminate`, {})
  },
  terminateSession(sessionId) {
    return request.post(`/system/sessions/${sessionId}/terminate`, {})
  },

  getGroups(params) {
    return request.get('/system/groups', params)
  },
  getGroup(groupId) {
    return request.get(`/system/groups/${groupId}`)
  },
  createGroup(data) {
    return request.post('/system/groups', data)
  },
  updateGroup(groupId, data) {
    return request.patch(`/system/groups/${groupId}`, data)
  },
  deleteGroup(groupId) {
    return request.delete(`/system/groups/${groupId}`)
  },

  getPermCodes(params) {
    return request.get('/system/perm-codes', params)
  },
  createPermCode(data) {
    return request.post('/system/perm-codes', data)
  },
  createPermCodesBatch(data) {
    return request.post('/system/perm-codes/batch', data)
  },
  updatePermCode(permCodeId, data) {
    return request.patch(`/system/perm-codes/${permCodeId}`, data)
  },
  deletePermCode(permCodeId) {
    return request.delete(`/system/perm-codes/${permCodeId}`)
  },
  getPermCodeImpact(permCodeId) {
    return request.get(`/system/perm-codes/${permCodeId}/impact`)
  },
  migratePermCode(permCodeId, data) {
    return request.post(`/system/perm-codes/${permCodeId}/migrate`, data)
  },
  cleanupPermCode(permCodeId) {
    return request.post(`/system/perm-codes/${permCodeId}/cleanup`, {})
  }
}

