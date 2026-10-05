import { request } from '@/utils/request';
export const evidenceApi = {
  overview: () => request.get('/evidence/overview'),
  list: params => request.get('/evidence/chains', params),
  get: id => request.get(`/evidence/chains/${encodeURIComponent(id)}`),
  create: data => request.post('/evidence/chains', data),
  save: (id, data) => request.put(`/evidence/chains/${encodeURIComponent(id)}`, data),
  remove: (id, revision) => request.delete(`/evidence/chains/${encodeURIComponent(id)}`, {
    params: {
      expected_revision: revision
    }
  }),
  resolve: (node, page = 1, pageSize = 30) => request.post('/evidence/resolve', {
    node,
    page,
    page_size: pageSize
  })
};
