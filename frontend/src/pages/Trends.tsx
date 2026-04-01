import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import Card from '../components/Card';
import Badge, { statusColor } from '../components/Badge';

export default function Trends() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sort, setSort] = useState('score');
  const [category, setCategory] = useState('');

  const load = () => {
    setLoading(true);
    let params = `&sort=${sort}&direction=desc`;
    if (category) params += `&category=${category}`;
    api.dashboardTrends('demo', params)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, [sort, category]);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div></div>;
  if (error) return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Error: {error}</div>;

  const categories = [...new Set((data?.items || []).map((t: any) => t.category))];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Trends</h1>
          <p className="text-gray-500 mt-1">{data?.total || 0} trends detected</p>
        </div>
        <div className="flex gap-3">
          <select value={category} onChange={e => setCategory(e.target.value)} className="px-3 py-2 border rounded-lg text-sm">
            <option value="">All categories</option>
            {categories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={sort} onChange={e => setSort(e.target.value)} className="px-3 py-2 border rounded-lg text-sm">
            <option value="score">Score</option>
            <option value="growth_rate">Growth</option>
            <option value="event_count">Events</option>
            <option value="confidence">Confidence</option>
          </select>
        </div>
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="pb-3 font-medium">Topic</th>
                <th className="pb-3 font-medium">Category</th>
                <th className="pb-3 font-medium text-right">Score</th>
                <th className="pb-3 font-medium text-right">Growth</th>
                <th className="pb-3 font-medium text-right">Events</th>
                <th className="pb-3 font-medium">Direction</th>
                <th className="pb-3 font-medium">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {(data?.items || []).map((t: any) => (
                <tr key={t.id} className="hover:bg-gray-50 transition-colors">
                  <td className="py-3">
                    <Link to={`/trends/${t.id}`} className="font-medium text-brand-600 hover:underline">{t.topic}</Link>
                    {t.ai_summary && <span className="ml-2 text-xs text-purple-500" title="AI summary available">AI</span>}
                  </td>
                  <td className="py-3"><Badge text={t.category} variant="blue" /></td>
                  <td className="py-3 text-right font-mono font-semibold">{t.score.toFixed(1)}</td>
                  <td className="py-3 text-right font-mono">
                    <span className={t.growth_rate > 50 ? 'text-green-600 font-semibold' : t.growth_rate > 0 ? 'text-green-500' : 'text-gray-400'}>
                      {t.growth_rate > 0 ? '+' : ''}{t.growth_rate.toFixed(1)}%
                    </span>
                  </td>
                  <td className="py-3 text-right font-mono">{t.event_count}</td>
                  <td className="py-3"><Badge text={t.direction} variant={statusColor(t.direction)} /></td>
                  <td className="py-3 text-gray-500">{t.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(!data?.items?.length) && <p className="text-center text-gray-400 py-8">No trends yet. <Link to="/demo" className="text-brand-600 underline">Seed demo data</Link></p>}
        </div>
      </Card>
    </div>
  );
}
