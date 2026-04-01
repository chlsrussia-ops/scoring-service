import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import Card from '../components/Card';
import Badge, { severityColor, statusColor } from '../components/Badge';

export default function Alerts() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.dashboardAlerts()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div></div>;
  if (error) return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Error: {error}</div>;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Alerts</h1>
        <p className="text-gray-500 mt-1">{data?.total || 0} alerts dispatched to your content team</p>
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="pb-3 font-medium">Title</th>
                <th className="pb-3 font-medium">Type</th>
                <th className="pb-3 font-medium">Severity</th>
                <th className="pb-3 font-medium">Status</th>
                <th className="pb-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {(data?.items || []).map((a: any) => (
                <tr key={a.id} className="hover:bg-gray-50">
                  <td className="py-3">
                    <span className="font-medium text-gray-900">{a.title}</span>
                    {a.body && <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{a.body}</p>}
                  </td>
                  <td className="py-3"><Badge text={a.alert_type} variant="gray" /></td>
                  <td className="py-3"><Badge text={a.severity} variant={severityColor(a.severity)} /></td>
                  <td className="py-3"><Badge text={a.status} variant={statusColor(a.status)} /></td>
                  <td className="py-3 text-gray-500 text-xs">{a.created_at?.split('T')[0]}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(!data?.items?.length) && <p className="text-center text-gray-400 py-8">No alerts yet. <Link to="/demo" className="text-brand-600 underline">Seed demo data</Link></p>}
        </div>
      </Card>
    </div>
  );
}
