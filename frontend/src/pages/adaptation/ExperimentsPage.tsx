import { useEffect, useState } from 'react';
import Card from '../../components/Card';
import Badge from '../../components/Badge';
import { api } from '../../api/client';

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listExperiments()
      .then((d: any) => setExperiments(d.experiments || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const verdictColor = (v: string | null) => {
    if (v === 'better') return 'green';
    if (v === 'worse') return 'red';
    if (v === 'neutral') return 'gray';
    return 'yellow';
  };

  if (loading) return <div className="animate-pulse text-gray-400">Loading experiments...</div>;

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Experiments</h1>
      {experiments.length === 0 && <Card><p className="text-gray-500">No experiments yet.</p></Card>}
      <div className="space-y-4">
        {experiments.map((e: any) => (
          <Card key={e.id}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="font-semibold">{e.name}</span>
                <Badge text={e.experiment_type} variant="purple" />
                <Badge text={e.status} variant="gray" />
              </div>
              <span className="text-xs text-gray-400">{new Date(e.created_at).toLocaleString()}</span>
            </div>
            {e.verdict && (
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm text-gray-500">Verdict:</span>
                <Badge text={e.verdict} variant="gray" />
                {e.verdict_reason && <span className="text-sm text-gray-600">{e.verdict_reason}</span>}
              </div>
            )}
            <div className="text-sm text-gray-500">Items evaluated: {e.items_evaluated}</div>
            {e.comparison_json && Object.keys(e.comparison_json).length > 0 && (
              <div className="mt-3 grid grid-cols-2 md:grid-cols-3 gap-2">
                {Object.entries(e.comparison_json).map(([key, comp]: [string, any]) => (
                  <div key={key} className="bg-gray-50 rounded p-2 text-xs">
                    <div className="text-gray-500 mb-1">{key.replace(/_/g, ' ')}</div>
                    <div>Base: {(comp.baseline * 100).toFixed(1)}%</div>
                    <div>Candidate: {(comp.candidate * 100).toFixed(1)}%</div>
                    <div className={comp.delta > 0 ? 'text-green-600' : comp.delta < 0 ? 'text-red-600' : 'text-gray-500'}>
                      Delta: {comp.delta > 0 ? '+' : ''}{(comp.delta * 100).toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
