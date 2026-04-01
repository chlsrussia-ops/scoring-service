import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import Card, { StatCard } from '../components/Card';
import MiniChart from '../components/MiniChart';
import type { DashboardOverview, DigestItem, TrendItem, ActivityEvent } from '../api/types';

export default function Dashboard() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [activity, setActivity] = useState<{ recent_events: ActivityEvent[] } | null>(null);
  const [topTrends, setTopTrends] = useState<TrendItem[]>([]);
  const [latestDigest, setLatestDigest] = useState<DigestItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [generatingDigest, setGeneratingDigest] = useState(false);

  useEffect(() => {
    Promise.all([
      api.dashboardOverview(),
      api.dashboardActivity(),
      api.dashboardTrends('demo', '&limit=5'),
      api.listDigests().catch(() => ({ items: [] })),
    ])
      .then(([o, a, t, d]) => {
        setOverview(o);
        setActivity(a);
        setTopTrends(t.items || []);
        if (d.items?.length) setLatestDigest(d.items[0]);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleGenerateDigest = async () => {
    setGeneratingDigest(true);
    try {
      const digest = await api.generateDigest();
      setLatestDigest(digest);
    } catch {} finally {
      setGeneratingDigest(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;
  if (error) return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Error: {error}</div>;
  if (!overview) return <div className="text-gray-500">No data yet. Go to <Link to="/demo" className="text-brand-600 underline">Demo</Link> to seed data.</div>;

  const trendScores = topTrends.map(t => t.score);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Content Intelligence Dashboard</h1>
          <p className="text-gray-500 mt-1">Real-time trend monitoring for your content & marketing team</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleGenerateDigest}
            disabled={generatingDigest}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium transition-colors disabled:opacity-50"
          >
            {generatingDigest ? 'Generating...' : 'Generate Digest'}
          </button>
          <Link to="/demo" className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm font-medium transition-colors">
            Run Demo
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
        <StatCard label="Total Events" value={overview.events.total} color="blue" />
        <StatCard label="Trends Detected" value={overview.trends.total} sub={overview.trends.rising + ' rising'} color="green" />
        <StatCard label="Recommendations" value={overview.recommendations.total} sub={overview.recommendations.high_priority + ' high priority'} color="purple" />
        <StatCard label="Alerts" value={overview.alerts.total} sub={overview.alerts.open + ' open'} color="amber" />
        <StatCard label="Sources" value={overview.sources.total} sub={overview.sources.active + ' active'} color="blue" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <Card title="Top Trends" className="lg:col-span-2" action={<Link to="/trends" className="text-sm text-brand-600 hover:underline">View all</Link>}>
          {topTrends.length > 0 && (
            <div className="mb-4">
              <MiniChart values={trendScores} color="#22c55e" height={40} />
            </div>
          )}
          <div className="space-y-3">
            {topTrends.map((t, i) => (
              <Link key={t.id} to={'/trends/' + t.id} className="flex items-center justify-between hover:bg-gray-50 rounded-lg p-2 -mx-2 transition-colors">
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-bold">{i + 1}</span>
                  <div>
                    <p className="font-medium text-sm text-gray-900">{t.topic}</p>
                    <p className="text-xs text-gray-500">{t.category} &middot; {t.source}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-mono font-semibold text-sm">{t.score.toFixed(1)}</p>
                  <p className={'text-xs ' + (t.growth_rate > 50 ? 'text-green-600 font-semibold' : 'text-gray-400')}>
                    {t.growth_rate > 0 ? '+' : ''}{t.growth_rate.toFixed(0)}%
                  </p>
                </div>
              </Link>
            ))}
            {!topTrends.length && <p className="text-gray-400 text-sm">No trends yet</p>}
          </div>
        </Card>

        <div className="space-y-6">
          <Card title="Latest Digest" action={<Link to="/digests" className="text-sm text-purple-600 hover:underline">All digests</Link>}>
            {latestDigest ? (
              <div>
                <p className="text-xs text-gray-500 mb-2">{latestDigest.created_at?.split('T')[0]}</p>
                <div className="text-sm text-gray-700 whitespace-pre-wrap line-clamp-6">
                  {latestDigest.summary?.replace(/##?\s*/g, '').replace(/\*\*/g, '').slice(0, 300)}...
                </div>
                <Link to="/digests" className="text-xs text-purple-600 hover:underline mt-2 inline-block">Read full digest</Link>
              </div>
            ) : (
              <div className="text-center py-4">
                <p className="text-gray-400 text-sm mb-2">No digests yet</p>
                <button onClick={handleGenerateDigest} disabled={generatingDigest} className="text-sm text-purple-600 hover:underline">
                  Generate first digest
                </button>
              </div>
            )}
          </Card>

          <Card title="Quick Actions">
            <div className="space-y-2">
              <Link to="/trends" className="block p-3 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors">
                <p className="font-medium text-sm text-blue-900">View Trends</p>
                <p className="text-xs text-blue-600 mt-0.5">See what's trending</p>
              </Link>
              <Link to="/recommendations" className="block p-3 bg-purple-50 rounded-lg hover:bg-purple-100 transition-colors">
                <p className="font-medium text-sm text-purple-900">Recommendations</p>
                <p className="text-xs text-purple-600 mt-0.5">AI-powered actions</p>
              </Link>
              <Link to="/sources" className="block p-3 bg-green-50 rounded-lg hover:bg-green-100 transition-colors">
                <p className="font-medium text-sm text-green-900">Data Sources</p>
                <p className="text-xs text-green-600 mt-0.5">Manage feeds & APIs</p>
              </Link>
            </div>
          </Card>
        </div>
      </div>

      <Card title="Recent Activity">
        {activity?.recent_events?.length ? (
          <div className="space-y-2">
            {activity.recent_events.slice(0, 10).map((e) => (
              <div key={e.id} className="flex items-center justify-between text-sm py-1">
                <div className="flex-1 truncate">
                  <span className="text-gray-900 font-medium">{e.title || 'Event'}</span>
                  <span className="text-gray-400 ml-2 text-xs">{e.source}</span>
                </div>
                <span className="text-xs text-gray-400 ml-4 whitespace-nowrap px-2 py-0.5 bg-gray-100 rounded">{e.event_type}</span>
              </div>
            ))}
          </div>
        ) : <p className="text-gray-400 text-sm">No recent activity</p>}
      </Card>
    </div>
  );
}
