import { request } from '@/utils/request'

export const searchApi = {
  searchEntity(params) {
    return request.post('/search/entity', params)
  }
}
