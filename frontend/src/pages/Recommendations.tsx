import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import Card from '../components/Card';
import Badge, { priorityColor } from '../components/Badge';

export default function Recommendations() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [enhancing, setEnhancing] = useState<number | null>(null);

  const load = () => {
    setLoading(true);
    api.dashboardRecommendations()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const enhance = async (id: number) => {
    setEnhancing(id);
    try {
      await api.enhanceRecommendation(id);
      load();
    } catch {} finally {
      setEnhancing(null);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div></div>;
  if (error) return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Error: {error}</div>;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Recommendations</h1>
        <p className="text-gray-500 mt-1">{data?.total || 0} actionable recommendations for your content team</p>
      </div>

      <div className="space-y-4">
        {(data?.items || []).map((r: any) => (
          <Card key={r.id}>
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <Badge text={r.priority} variant={priorityColor(r.priority)} />
                  <Badge text={r.category} variant="blue" />
                  <span className="text-xs text-gray-400">Confidence: {(r.confidence * 100).toFixed(0)}%</span>
                </div>
                <h3 className="font-semibold text-gray-900">{r.title}</h3>
                <p className="text-sm text-gray-600 mt-1">{r.body}</p>
                {r.ai_enhancement && (
                  <div className="mt-3 p-3 bg-purple-50 rounded-lg">
                    <p className="text-xs font-medium text-purple-700 mb-1">AI Enhancement</p>
                    <div className="text-sm text-purple-900 whitespace-pre-wrap">{r.ai_enhancement}</div>
                  </div>
                )}
              </div>
              <div className="ml-4 flex flex-col gap-2">
                {!r.ai_enhancement && (
                  <button
                    onClick={() => enhance(r.id)}
                    disabled={enhancing === r.id}
                    className="px-3 py-1 bg-purple-100 text-purple-700 rounded-lg text-xs hover:bg-purple-200 disabled:opacity-50 whitespace-nowrap"
                  >
                    {enhancing === r.id ? 'Enhancing...' : 'AI Enhance'}
                  </button>
                )}
                {r.trend_id && <Link to={`/trends/${r.trend_id}`} className="text-xs text-brand-600 hover:underline">View trend</Link>}
              </div>
            </div>
          </Card>
        ))}
        {(!data?.items?.length) && <p className="text-center text-gray-400 py-8">No recommendations yet. <Link to="/demo" className="text-brand-600 underline">Seed demo data</Link></p>}
      </div>
    </div>
  );
}
