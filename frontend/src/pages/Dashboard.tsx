import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import Card, { StatCard } from '../components/Card';

export default function Dashboard() {
  const [overview, setOverview] = useState<any>(null);
  const [activity, setActivity] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([api.dashboardOverview(), api.dashboardActivity()])
      .then(([o, a]) => { setOverview(o); setActivity(a); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div></div>;
  if (error) return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Error: {error}</div>;
  if (!overview) return <div className="text-gray-500">No data yet. Go to <Link to="/demo" className="text-brand-600 underline">Demo</Link> to seed data.</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Content Intelligence Dashboard</h1>
          <p className="text-gray-500 mt-1">Real-time trend monitoring for your content & marketing team</p>
        </div>
        <Link to="/demo" className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm font-medium transition-colors">
          Run Demo
        </Link>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
        <StatCard label="Total Events" value={overview.events?.total || 0} color="blue" />
        <StatCard label="Trends Detected" value={overview.trends?.total || 0} sub={`${overview.trends?.rising || 0} rising`} color="green" />
        <StatCard label="Recommendations" value={overview.recommendations?.total || 0} sub={`${overview.recommendations?.high_priority || 0} high priority`} color="purple" />
        <StatCard label="Alerts" value={overview.alerts?.total || 0} sub={`${overview.alerts?.open || 0} open`} color="amber" />
        <StatCard label="Sources" value={overview.sources?.total || 0} sub={`${overview.sources?.active || 0} active`} color="blue" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Recent Activity">
          {activity?.recent_events?.length ? (
            <div className="space-y-3">
              {activity.recent_events.slice(0, 8).map((e: any) => (
                <div key={e.id} className="flex items-center justify-between text-sm">
                  <div className="flex-1 truncate">
                    <span className="text-gray-900 font-medium">{e.title || 'Event'}</span>
                    <span className="text-gray-400 ml-2">{e.source}</span>
                  </div>
                  <span className="text-xs text-gray-400 ml-4 whitespace-nowrap">{e.event_type}</span>
                </div>
              ))}
            </div>
          ) : <p className="text-gray-400 text-sm">No recent activity</p>}
        </Card>

        <Card title="Quick Actions" action={<Link to="/demo" className="text-sm text-brand-600 hover:underline">Full Demo</Link>}>
          <div className="space-y-3">
            <Link to="/trends" className="block p-3 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors">
              <p className="font-medium text-blue-900">View Trends</p>
              <p className="text-xs text-blue-600 mt-0.5">See what's trending in your content space</p>
            </Link>
            <Link to="/recommendations" className="block p-3 bg-purple-50 rounded-lg hover:bg-purple-100 transition-colors">
              <p className="font-medium text-purple-900">Recommendations</p>
              <p className="text-xs text-purple-600 mt-0.5">AI-powered content action items</p>
            </Link>
            <Link to="/sources" className="block p-3 bg-green-50 rounded-lg hover:bg-green-100 transition-colors">
              <p className="font-medium text-green-900">Data Sources</p>
              <p className="text-xs text-green-600 mt-0.5">Manage RSS, Reddit, API sources</p>
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
