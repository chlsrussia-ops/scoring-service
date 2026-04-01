import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import Card from '../components/Card';
import Badge, { severityColor, statusColor } from '../components/Badge';
import type { AlertItem } from '../api/types';

export default function Alerts() {
  const [data, setData] = useState<{ total: number; items: AlertItem[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    api.dashboardAlerts()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;
  if (error) return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Error: {error}</div>;

  let filtered = data?.items || [];
  if (filterSeverity) filtered = filtered.filter(a => a.severity === filterSeverity);
  if (filterStatus) filtered = filtered.filter(a => a.status === filterStatus);
  if (search) filtered = filtered.filter(a => a.title.toLowerCase().includes(search.toLowerCase()) || a.body?.toLowerCase().includes(search.toLowerCase()));

  const severities = [...new Set((data?.items || []).map(a => a.severity))];
  const statuses = [...new Set((data?.items || []).map(a => a.status))];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Alerts</h1>
          <p className="text-gray-500 mt-1">{data?.total || 0} alerts dispatched to your content team</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 mb-4">
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search alerts..." className="px-3 py-2 border rounded-lg text-sm w-64" />
        <select value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)} className="px-3 py-2 border rounded-lg text-sm">
          <option value="">All severities</option>
          {severities.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className="px-3 py-2 border rounded-lg text-sm">
          <option value="">All statuses</option>
          {statuses.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {(filterSeverity || filterStatus || search) && (
          <button onClick={() => { setFilterSeverity(''); setFilterStatus(''); setSearch(''); }} className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700">
            Clear filters
          </button>
        )}
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
              {filtered.map(a => (
                <tr key={a.id} className="hover:bg-gray-50">
                  <td className="py-3">
                    <span className="font-medium text-gray-900">{a.title}</span>
                    {a.body && <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{a.body}</p>}
                  </td>
                  <td className="py-3"><Badge text={a.alert_type} variant="gray" /></td>
                  <td className="py-3"><Badge text={a.severity} variant={severityColor(a.severity)} /></td>
                  <td className="py-3"><Badge text={a.status} variant={statusColor(a.status)} /></td>
                  <td className="py-3 text-gray-500 text-xs">{a.created_at?.split('T')[0] || a.created_at?.split(' ')[0]}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filtered.length && <p className="text-center text-gray-400 py-8">{(data?.items?.length || 0) > 0 ? 'No alerts match filters' : <>No alerts yet. <Link to="/demo" className="text-brand-600 underline">Seed demo data</Link></>}</p>}
        </div>
        <p className="text-xs text-gray-400 mt-3">{filtered.length} of {data?.total || 0} alerts shown</p>
      </Card>
    </div>
  );
}
