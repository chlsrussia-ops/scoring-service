import { useEffect, useState } from 'react';
import Card from '../../components/Card';
import Badge from '../../components/Badge';
import { api } from '../../api/client';

export default function QualityPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.evaluationScorecards()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="animate-pulse text-gray-400">Loading scorecards...</div>;

  const scorecards = data?.scorecards || [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Quality Scorecards</h1>
      {scorecards.length === 0 && (
        <Card><p className="text-gray-500">No evaluation data yet. Run an evaluation cycle first.</p></Card>
      )}
      <div className="space-y-6">
        {scorecards.map((sc: any, i: number) => (
          <Card key={i}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Window: {sc.window}</h2>
              {sc.evaluation_run_id && <Badge text="Run #{sc.evaluation_run_id}" variant="blue" />}
            </div>
            {sc.metrics ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Object.entries(sc.metrics).map(([key, val]: [string, any]) => (
                  <div key={key} className="bg-gray-50 rounded-lg p-3">
                    <div className="text-xs text-gray-500 mb-1">{key.replace(/_/g, ' ')}</div>
                    <div className="text-xl font-bold text-gray-900">
                      {typeof val === 'number' ? (val * 100).toFixed(1) + '%' : String(val)}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-400">{sc.message || 'No data'}</p>
            )}
            {sc.degradation_flags?.length > 0 && (
              <div className="mt-3">
                {sc.degradation_flags.map((f: string, j: number) => (
                  <Badge text={f} variant="red" />
                ))}
              </div>
            )}
            {sc.improvement_flags?.length > 0 && (
              <div className="mt-3">
                {sc.improvement_flags.map((f: string, j: number) => (
                  <Badge text={f} variant="green" />
                ))}
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
