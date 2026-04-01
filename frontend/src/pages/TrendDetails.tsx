import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import Card, { StatCard } from '../components/Card';
import Badge, { priorityColor, severityColor, statusColor } from '../components/Badge';

export default function TrendDetails() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [generating, setGenerating] = useState(false);

  const load = () => {
    setLoading(true);
    api.dashboardTrendDetail(Number(id))
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, [id]);

  const generateSummary = async () => {
    setGenerating(true);
    try {
      await api.generateTrendSummary(Number(id));
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div></div>;
  if (error) return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Error: {error}</div>;
  if (!data || data.error) return <div className="text-gray-500">Trend not found</div>;

  return (
    <div>
      <div className="mb-6">
        <Link to="/trends" className="text-sm text-gray-500 hover:text-brand-600">&larr; Back to Trends</Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">{data.topic}</h1>
        <div className="flex items-center gap-3 mt-2">
          <Badge text={data.category} variant="blue" />
          <Badge text={data.direction} variant={statusColor(data.direction)} />
          <span className="text-sm text-gray-500">{data.source}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Score" value={data.score?.toFixed(1)} color="blue" />
        <StatCard label="Growth Rate" value={`${data.growth_rate > 0 ? '+' : ''}${data.growth_rate?.toFixed(1)}%`} color="green" />
        <StatCard label="Confidence" value={`${(data.confidence * 100).toFixed(0)}%`} color="purple" />
        <StatCard label="Events" value={data.event_count} color="amber" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card title="AI Summary" action={
          !data.ai_summary ? (
            <button onClick={generateSummary} disabled={generating} className="px-3 py-1 bg-purple-100 text-purple-700 rounded-lg text-sm hover:bg-purple-200 disabled:opacity-50">
              {generating ? 'Generating...' : 'Generate AI Summary'}
            </button>
          ) : null
        }>
          {data.ai_summary ? (
            <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">{data.ai_summary}</div>
          ) : (
            <p className="text-gray-400 text-sm">No AI summary generated yet. Click "Generate AI Summary" to create one.</p>
          )}
        </Card>

        <Card title="Timeline">
          <div className="space-y-3 text-sm">
            <div className="flex justify-between"><span className="text-gray-500">First seen</span><span className="font-medium">{data.first_seen?.split('T')[0]}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Last seen</span><span className="font-medium">{data.last_seen?.split('T')[0]}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Direction</span><Badge text={data.direction} variant={statusColor(data.direction)} /></div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title={`Recommendations (${data.recommendations?.length || 0})`}>
          {data.recommendations?.length ? (
            <div className="space-y-3">
              {data.recommendations.map((r: any) => (
                <div key={r.id} className="p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Badge text={r.priority} variant={priorityColor(r.priority)} />
                    <span className="font-medium text-sm">{r.title}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="text-gray-400 text-sm">No linked recommendations</p>}
        </Card>

        <Card title={`Alerts (${data.alerts?.length || 0})`}>
          {data.alerts?.length ? (
            <div className="space-y-3">
              {data.alerts.map((a: any) => (
                <div key={a.id} className="p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Badge text={a.severity} variant={severityColor(a.severity)} />
                    <span className="font-medium text-sm">{a.title}</span>
                    <Badge text={a.status} variant={statusColor(a.status)} />
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="text-gray-400 text-sm">No linked alerts</p>}
        </Card>
      </div>
    </div>
  );
}
