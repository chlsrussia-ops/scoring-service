import { useEffect, useState } from 'react';
import { api } from '../api/client';
import Card from '../components/Card';
import type { DigestItem } from '../api/types';

export default function Digests() {
  const [digests, setDigests] = useState<DigestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [generating, setGenerating] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);

  const load = () => {
    setLoading(true);
    api.listDigests()
      .then(d => setDigests(d.items || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const generate = async () => {
    setGenerating(true);
    try {
      await api.generateDigest();
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;
  if (error) return <div className="bg-red-50 text-red-700 p-4 rounded-lg">Error: {error}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Executive Digests</h1>
          <p className="text-gray-500 mt-1">AI-generated intelligence briefings for your content team</p>
        </div>
        <button
          onClick={generate}
          disabled={generating}
          className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium transition-colors disabled:opacity-50"
        >
          {generating ? 'Generating...' : 'Generate New Digest'}
        </button>
      </div>

      {digests.length === 0 ? (
        <Card>
          <div className="text-center py-12">
            <p className="text-gray-400 mb-4">No digests generated yet</p>
            <button onClick={generate} disabled={generating} className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700">
              Generate First Digest
            </button>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {digests.map(d => (
            <Card key={d.id}>
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-gray-900">{d.title}</h3>
                  <p className="text-xs text-gray-500 mt-1">{d.created_at?.split('T')[0] || d.created_at?.split(' ')[0]}</p>
                </div>
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  {d.stats && Object.entries(d.stats).map(([k, v]) => (
                    <span key={k} className="px-2 py-1 bg-gray-100 rounded">{k}: {v}</span>
                  ))}
                </div>
              </div>

              {d.top_trends && d.top_trends.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-3">
                  {d.top_trends.map(t => (
                    <span key={t.id} className="px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs">
                      {t.topic} ({t.score.toFixed(0)})
                    </span>
                  ))}
                </div>
              )}

              <div className={`prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap ${expanded !== d.id ? 'line-clamp-6' : ''}`}>
                {d.summary || 'No summary available'}
              </div>
              {d.summary && d.summary.length > 300 && (
                <button
                  onClick={() => setExpanded(expanded === d.id ? null : d.id)}
                  className="text-sm text-purple-600 hover:underline mt-2"
                >
                  {expanded === d.id ? 'Show less' : 'Read full digest'}
                </button>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
