import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import Card from '../components/Card';
import Badge, { statusColor } from '../components/Badge';
import type { SourceItem } from '../api/types';

const TYPE_LABELS: Record<string, string> = { rss: 'RSS Feed', reddit: 'Reddit', http_api: 'HTTP API', file_import: 'File Import', twitter: 'Twitter' };
const TYPE_OPTIONS = [
  { value: 'rss', label: 'RSS Feed', placeholder: '{"feeds": ["https://example.com/feed"]}' },
  { value: 'reddit', label: 'Reddit', placeholder: '{"subreddits": ["technology"], "mock_mode": true}' },
  { value: 'http_api', label: 'HTTP API', placeholder: '{"endpoint": "https://api.example.com/data", "items_path": "results"}' },
  { value: 'file_import', label: 'File Import', placeholder: '{"content": "[{\\"title\\": \\"test\\"}]", "format": "json"}' },
];

export default function Sources() {
  const [data, setData] = useState<SourceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [syncing, setSyncing] = useState<number | null>(null);
  const [testing, setTesting] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<{ id: number; ok: boolean; message: string } | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newType, setNewType] = useState('rss');
  const [newConfig, setNewConfig] = useState('{"feeds": []}');
  const [creating, setCreating] = useState(false);

  const load = () => {
    setLoading(true);
    api.listSources()
      .then(d => setData(d.items || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const syncSource = async (id: number) => {
    setSyncing(id);
    try { await api.syncSource(id); load(); } catch {} finally { setSyncing(null); }
  };

  const testSource = async (id: number) => {
    setTesting(id);
    setTestResult(null);
    try {
      const r = await api.testSource(id);
      setTestResult({ id, ...r });
    } catch (e: any) {
      setTestResult({ id, ok: false, message: e.message });
    } finally { setTesting(null); }
  };

  const createSource = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      let config = {};
      try { config = JSON.parse(newConfig); } catch {}
      await api.createSource({ name: newName, source_type: newType, config_json: config });
      setShowCreate(false);
      setNewName('');
      setNewConfig('{"feeds": []}');
      load();
    } catch (e: any) {
      setError(e.message);
    } finally { setCreating(false); }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;
  if (error) return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Error: {error} <button onClick={() => setError('')} className="ml-2 underline">Dismiss</button></div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Data Sources</h1>
          <p className="text-gray-500 mt-1">{data.length} configured sources feeding your trend intelligence</p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm font-medium transition-colors"
        >
          {showCreate ? 'Cancel' : '+ Add Source'}
        </button>
      </div>

      {showCreate && (
        <Card title="Add New Source" className="mb-6">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input value={newName} onChange={e => setNewName(e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm" placeholder="My RSS Feed" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
              <select value={newType} onChange={e => { setNewType(e.target.value); setNewConfig(TYPE_OPTIONS.find(o => o.value === e.target.value)?.placeholder || '{}'); }} className="w-full px-3 py-2 border rounded-lg text-sm">
                {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Configuration (JSON)</label>
              <textarea value={newConfig} onChange={e => setNewConfig(e.target.value)} rows={3} className="w-full px-3 py-2 border rounded-lg text-sm font-mono" />
            </div>
            <button onClick={createSource} disabled={creating || !newName.trim()} className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 text-sm disabled:opacity-50">
              {creating ? 'Creating...' : 'Create Source'}
            </button>
          </div>
        </Card>
      )}

      {testResult && (
        <div className={'mb-4 p-3 rounded-lg text-sm ' + (testResult.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700')}>
          Source #{testResult.id}: {testResult.message}
          <button onClick={() => setTestResult(null)} className="ml-2 underline text-xs">Dismiss</button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {data.map(s => (
          <Card key={s.id}>
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="font-semibold text-gray-900">{s.name}</h3>
                <div className="flex items-center gap-2 mt-1">
                  <Badge text={TYPE_LABELS[s.source_type] || s.source_type} variant="blue" />
                  <Badge text={s.status} variant={statusColor(s.status)} />
                  {!s.enabled && <Badge text="disabled" variant="gray" />}
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-500 mb-3">
              <div>Fetched: <span className="font-medium text-gray-700">{s.items_fetched}</span></div>
              <div>Normalized: <span className="font-medium text-gray-700">{s.items_normalized}</span></div>
              <div>Failures: <span className={'font-medium ' + (s.failure_count > 0 ? 'text-red-600' : 'text-gray-700')}>{s.failure_count}</span></div>
              <div>Last sync: <span className="font-medium text-gray-700">{s.last_sync_at ? s.last_sync_at.split('T')[0] || s.last_sync_at.split(' ')[0] : 'never'}</span></div>
            </div>
            {s.last_error && <p className="text-xs text-red-500 mb-3 line-clamp-2">{s.last_error}</p>}
            <div className="flex gap-2">
              <button onClick={() => testSource(s.id)} disabled={testing === s.id} className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-xs hover:bg-gray-200 disabled:opacity-50">
                {testing === s.id ? 'Testing...' : 'Test Connection'}
              </button>
              <button onClick={() => syncSource(s.id)} disabled={syncing === s.id} className="px-3 py-1.5 bg-brand-100 text-brand-700 rounded-lg text-xs hover:bg-brand-200 disabled:opacity-50">
                {syncing === s.id ? 'Syncing...' : 'Sync Now'}
              </button>
            </div>
          </Card>
        ))}
        {!data.length && <p className="text-gray-400 py-8">No sources configured. <Link to="/demo" className="text-brand-600 underline">Seed demo data</Link> or click "+ Add Source".</p>}
      </div>
    </div>
  );
}
