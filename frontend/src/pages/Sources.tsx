import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import Card from '../components/Card';
import Badge, { statusColor } from '../components/Badge';

export default function Sources() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [syncing, setSyncing] = useState<number | null>(null);
  const [testing, setTesting] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<any>(null);

  const load = () => {
    setLoading(true);
    api.listSources()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const syncSource = async (id: number) => {
    setSyncing(id);
    try {
      await api.syncSource(id);
      load();
    } catch {} finally {
      setSyncing(null);
    }
  };

  const testSource = async (id: number) => {
    setTesting(id);
    setTestResult(null);
    try {
      const result = await api.testSource(id);
      setTestResult({ id, ...result });
    } catch (e: any) {
      setTestResult({ id, ok: false, message: e.message });
    } finally {
      setTesting(null);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div></div>;
  if (error) return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Error: {error}</div>;

  const typeLabel: Record<string, string> = { rss: 'RSS Feed', reddit: 'Reddit', http_api: 'HTTP API', file_import: 'File Import' };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Data Sources</h1>
        <p className="text-gray-500 mt-1">{data?.total || 0} configured sources feeding your trend intelligence</p>
      </div>

      {testResult && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${testResult.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
          Source #{testResult.id}: {testResult.message}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(data?.items || []).map((s: any) => (
          <Card key={s.id}>
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="font-semibold text-gray-900">{s.name}</h3>
                <div className="flex items-center gap-2 mt-1">
                  <Badge text={typeLabel[s.source_type] || s.source_type} variant="blue" />
                  <Badge text={s.status} variant={statusColor(s.status)} />
                  {!s.enabled && <Badge text="disabled" variant="gray" />}
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-500 mb-3">
              <div>Fetched: <span className="font-medium text-gray-700">{s.items_fetched}</span></div>
              <div>Normalized: <span className="font-medium text-gray-700">{s.items_normalized}</span></div>
              <div>Failures: <span className={`font-medium ${s.failure_count > 0 ? 'text-red-600' : 'text-gray-700'}`}>{s.failure_count}</span></div>
              <div>Last sync: <span className="font-medium text-gray-700">{s.last_sync_at ? s.last_sync_at.split('T')[0] : 'never'}</span></div>
            </div>
            {s.last_error && <p className="text-xs text-red-500 mb-3 line-clamp-2">{s.last_error}</p>}
            <div className="flex gap-2">
              <button
                onClick={() => testSource(s.id)}
                disabled={testing === s.id}
                className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-xs hover:bg-gray-200 disabled:opacity-50"
              >
                {testing === s.id ? 'Testing...' : 'Test Connection'}
              </button>
              <button
                onClick={() => syncSource(s.id)}
                disabled={syncing === s.id}
                className="px-3 py-1.5 bg-brand-100 text-brand-700 rounded-lg text-xs hover:bg-brand-200 disabled:opacity-50"
              >
                {syncing === s.id ? 'Syncing...' : 'Sync Now'}
              </button>
            </div>
          </Card>
        ))}
        {(!data?.items?.length) && <p className="text-gray-400 py-8">No sources configured. <Link to="/demo" className="text-brand-600 underline">Seed demo data</Link> to create demo sources.</p>}
      </div>
    </div>
  );
}
