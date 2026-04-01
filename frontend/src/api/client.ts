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
};
