const BASE = import.meta.env.VITE_API_BASE_URL || '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  // Dashboard
  dashboardOverview: (tid = 'demo') => request<any>(`/v1/dashboard/overview?tenant_id=${tid}`),
  dashboardActivity: (tid = 'demo') => request<any>(`/v1/dashboard/activity?tenant_id=${tid}`),
  dashboardTrends: (tid = 'demo', params = '') => request<any>(`/v1/dashboard/trends?tenant_id=${tid}${params}`),
  dashboardTrendDetail: (id: number, tid = 'demo') => request<any>(`/v1/dashboard/trends/${id}?tenant_id=${tid}`),
  dashboardRecommendations: (tid = 'demo', params = '') => request<any>(`/v1/dashboard/recommendations?tenant_id=${tid}${params}`),
  dashboardAlerts: (tid = 'demo') => request<any>(`/v1/dashboard/alerts?tenant_id=${tid}`),
  dashboardSources: (tid = 'demo') => request<any>(`/v1/dashboard/sources?tenant_id=${tid}`),

  // Sources
  listSources: (tid = 'demo') => request<any>(`/v1/sources?tenant_id=${tid}`),
  createSource: (data: any, tid = 'demo') => request<any>(`/v1/sources?tenant_id=${tid}`, { method: 'POST', body: JSON.stringify(data) }),
  testSource: (id: number, tid = 'demo') => request<any>(`/v1/sources/${id}/test?tenant_id=${tid}`, { method: 'POST' }),
  syncSource: (id: number, tid = 'demo') => request<any>(`/v1/sources/${id}/sync?tenant_id=${tid}`, { method: 'POST' }),
  sourceHealth: (id: number, tid = 'demo') => request<any>(`/v1/sources/${id}/health?tenant_id=${tid}`),

  // LLM
  generateTrendSummary: (id: number, tid = 'demo') => request<any>(`/v1/llm/trends/${id}/generate-summary?tenant_id=${tid}`, { method: 'POST' }),
  enhanceRecommendation: (id: number, tid = 'demo') => request<any>(`/v1/llm/recommendations/${id}/enhance?tenant_id=${tid}`, { method: 'POST' }),
  generateDigest: (tid = 'demo') => request<any>(`/v1/llm/digests/generate?tenant_id=${tid}`, { method: 'POST' }),
  listDigests: (tid = 'demo') => request<any>(`/v1/llm/digests?tenant_id=${tid}`),
  listGenerations: (tid = 'demo') => request<any>(`/v1/llm/generations?tenant_id=${tid}`),

  // Demo
  demoSeed: () => request<any>('/v1/demo/seed', { method: 'POST' }),
  demoSyncSources: () => request<any>('/v1/demo/sync-sources', { method: 'POST' }),
  demoRunAnalysis: () => request<any>('/v1/demo/run-analysis', { method: 'POST' }),
  demoGenerateAI: () => request<any>('/v1/demo/generate-ai', { method: 'POST' }),
  demoDispatchAlerts: () => request<any>('/v1/demo/dispatch-alerts', { method: 'POST' }),
  demoRunAll: () => request<any>('/v1/demo/run-all', { method: 'POST' }),
  demoStatus: () => request<any>('/v1/demo/status'),

// Adaptation
  adaptationStatus: (tid = 'demo') => request<any>(`/v1/adaptation/status?tenant_id=${tid}`),
  evaluationScorecards: (tid = 'demo') => request<any>(`/v1/evaluation/scorecards?tenant_id=${tid}`),
  sourceLearning: (tid = 'demo') => request<any>(`/v1/source-learning/summary?tenant_id=${tid}`),
  listGoals: (tid = 'demo') => request<any>(`/v1/goals?tenant_id=${tid}`),
  listExperiments: (tid = 'demo') => request<any>(`/v1/experiments?tenant_id=${tid}`),
  adaptationProposals: () => request<any>('/v1/admin/adaptation/proposals', {
    headers: { 'x-admin-key': 'admin-secret-key' },
  }),
  goalPerformance: () => request<any>('/v1/admin/adaptation/goal-performance', {
    headers: { 'x-admin-key': 'admin-secret-key' },
  }),
  approveProposal: (id: number) => request<any>(`/v1/admin/adaptation/proposals/${id}/approve`, {
    method: 'POST', headers: { 'x-admin-key': 'admin-secret-key' },
    body: JSON.stringify({ actor: 'ui_admin' }),
  }),
  rejectProposal: (id: number) => request<any>(`/v1/admin/adaptation/proposals/${id}/reject`, {
    method: 'POST', headers: { 'x-admin-key': 'admin-secret-key' },
    body: JSON.stringify({ actor: 'ui_admin' }),
  }),
  applyProposal: (id: number) => request<any>(`/v1/admin/adaptation/proposals/${id}/apply`, {
    method: 'POST', headers: { 'x-admin-key': 'admin-secret-key' },
  }),
  simulateProposal: (id: number) => request<any>(`/v1/admin/adaptation/proposals/${id}/simulate`, {
    method: 'POST', headers: { 'x-admin-key': 'admin-secret-key' },
  }),
  rollbackProposal: (id: number) => request<any>(`/v1/admin/adaptation/rollbacks/${id}/execute`, {
    method: 'POST', headers: { 'x-admin-key': 'admin-secret-key' },
  }),
  seedAdaptation: () => request<any>('/v1/demo/seed-adaptation', { method: 'POST' }),
};
