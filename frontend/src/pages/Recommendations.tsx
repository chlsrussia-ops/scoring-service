import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import Card from '../components/Card';
import Badge, { priorityColor } from '../components/Badge';
import type { RecommendationItem } from '../api/types';

export default function Recommendations() {
  const [data, setData] = useState<{ total: number; items: RecommendationItem[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [enhancing, setEnhancing] = useState<number | null>(null);
  const [filterPriority, setFilterPriority] = useState('');
  const [search, setSearch] = useState('');

  const load = () => {
    setLoading(true);
    let params = '';
    if (filterPriority) params += '&priority=' + filterPriority;
    api.dashboardRecommendations('demo', params)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, [filterPriority]);

  const enhance = async (id: number) => {
    setEnhancing(id);
    try { await api.enhanceRecommendation(id); load(); } catch {} finally { setEnhancing(null); }
  };

  const enhanceAll = async () => {
    const items = (data?.items || []).filter(r => !r.ai_enhancement);
    for (const item of items) {
      setEnhancing(item.id);
      try { await api.enhanceRecommendation(item.id); } catch {}
    }
    setEnhancing(null);
    load();
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;
  if (error) return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Error: {error}</div>;

  let filtered = data?.items || [];
  if (search) filtered = filtered.filter(r => r.title.toLowerCase().includes(search.toLowerCase()) || r.body?.toLowerCase().includes(search.toLowerCase()));

  const unenhanced = (data?.items || []).filter(r => !r.ai_enhancement).length;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Recommendations</h1>
          <p className="text-gray-500 mt-1">{data?.total || 0} actionable recommendations for your content team</p>
        </div>
        {unenhanced > 0 && (
          <button onClick={enhanceAll} disabled={enhancing !== null} className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium disabled:opacity-50">
            {enhancing !== null ? 'Enhancing...' : 'AI Enhance All (' + unenhanced + ')'}
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-3 mb-4">
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search recommendations..." className="px-3 py-2 border rounded-lg text-sm w-64" />
        <select value={filterPriority} onChange={e => setFilterPriority(e.target.value)} className="px-3 py-2 border rounded-lg text-sm">
          <option value="">All priorities</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      <div className="space-y-4">
        {filtered.map(r => (
          <Card key={r.id}>
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <Badge text={r.priority} variant={priorityColor(r.priority)} />
                  <Badge text={r.category} variant="blue" />
                  <span className="text-xs text-gray-400">Confidence: {(r.confidence * 100).toFixed(0)}%</span>
                  {r.ai_enhancement && <span className="text-xs text-purple-500 font-medium">AI Enhanced</span>}
                </div>
                <h3 className="font-semibold text-gray-900">{r.title}</h3>
                <p className="text-sm text-gray-600 mt-1">{r.body}</p>
                {r.ai_enhancement && (
                  <div className="mt-3 p-3 bg-purple-50 rounded-lg border border-purple-100">
                    <p className="text-xs font-medium text-purple-700 mb-1">AI Enhancement</p>
                    <div className="text-sm text-purple-900 whitespace-pre-wrap">{r.ai_enhancement}</div>
                  </div>
                )}
              </div>
              <div className="ml-4 flex flex-col gap-2 flex-shrink-0">
                {!r.ai_enhancement && (
                  <button onClick={() => enhance(r.id)} disabled={enhancing === r.id} className="px-3 py-1 bg-purple-100 text-purple-700 rounded-lg text-xs hover:bg-purple-200 disabled:opacity-50 whitespace-nowrap">
                    {enhancing === r.id ? 'Enhancing...' : 'AI Enhance'}
                  </button>
                )}
                {r.trend_id && <Link to={'/trends/' + r.trend_id} className="text-xs text-brand-600 hover:underline">View trend</Link>}
              </div>
            </div>
          </Card>
        ))}
        {!filtered.length && <p className="text-center text-gray-400 py-8">{(data?.items?.length || 0) > 0 ? 'No recommendations match filters' : <>No recommendations yet. <Link to="/demo" className="text-brand-600 underline">Seed demo data</Link></>}</p>}
      </div>
    </div>
  );
}
