import { useEffect, useState } from 'react';
import Card from '../../components/Card';
import Badge from '../../components/Badge';
import { api } from '../../api/client';

export default function SourceTrustPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.sourceLearning()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="animate-pulse text-gray-400">Loading source trust...</div>;
  if (!data) return <div className="text-gray-500">No data</div>;

  const trustColor = (t: number) => t >= 1.1 ? 'green' : t >= 0.8 ? 'blue' : t >= 0.5 ? 'yellow' : 'red';

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Source Trust & Learning</h1>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <Card>
          <div className="text-sm text-gray-500">Total Sources</div>
          <div className="text-3xl font-bold">{data.total_sources}</div>
        </Card>
        <Card className={data.noisy_sources?.length > 0 ? 'border-red-200' : ''}>
          <div className="text-sm text-gray-500">Noisy Sources</div>
          <div className="text-3xl font-bold text-red-600">{data.noisy_sources?.length || 0}</div>
          {data.noisy_sources?.map((s: string) => <Badge text={s} variant="red" />)}
        </Card>
        <Card className={data.boosted_sources?.length > 0 ? 'border-green-200' : ''}>
          <div className="text-sm text-gray-500">Boosted Sources</div>
          <div className="text-3xl font-bold text-green-600">{data.boosted_sources?.length || 0}</div>
          {data.boosted_sources?.map((s: string) => <Badge text={s} variant="green" />)}
        </Card>
      </div>

      <Card>
        <h2 className="text-lg font-semibold mb-4">Source Details</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="pb-2">Source</th>
                <th className="pb-2">Trust</th>
                <th className="pb-2">Reliability</th>
                <th className="pb-2">Noise</th>
                <th className="pb-2">Confirmation</th>
                <th className="pb-2">Samples</th>
                <th className="pb-2">Updated</th>
              </tr>
            </thead>
            <tbody>
              {(data.sources || []).map((s: any, i: number) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="py-2 font-medium">{s.source_name}</td>
                  <td><Badge text={s.trust_score.toFixed(3)} variant="gray" /></td>
                  <td>{(s.reliability_score * 100).toFixed(1)}%</td>
                  <td className={s.noise_score > 0.3 ? 'text-red-600 font-medium' : ''}>{(s.noise_score * 100).toFixed(1)}%</td>
                  <td>{(s.confirmation_rate * 100).toFixed(1)}%</td>
                  <td>{s.sample_count}</td>
                  <td className="text-xs text-gray-400">{new Date(s.last_updated).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
