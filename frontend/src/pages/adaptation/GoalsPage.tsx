import { useEffect, useState } from 'react';
import Card from '../../components/Card';
import Badge from '../../components/Badge';
import { api } from '../../api/client';

export default function GoalsPage() {
  const [goals, setGoals] = useState<any[]>([]);
  const [performance, setPerformance] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.listGoals().then((d: any) => setGoals(d.goals || [])),
      api.goalPerformance().then((d: any) => setPerformance(d.goals || [])).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="animate-pulse text-gray-400">Loading goals...</div>;

  const statusColor = (s: string) => {
    if (s === 'achieved') return 'green';
    if (s === 'on_track') return 'blue';
    if (s === 'at_risk') return 'yellow';
    return 'red';
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Optimization Goals</h1>
      {goals.length === 0 && <Card><p className="text-gray-500">No goals defined yet.</p></Card>}
      <div className="space-y-4">
        {goals.map((g: any) => {
          const perf = performance.find((p: any) => p.goal_id === g.id);
          return (
            <Card key={g.id}>
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-gray-900">{g.name}</h3>
                <div className="flex gap-2">
                  <Badge text={g.is_active ? 'Active' : 'Inactive'} variant="gray" />
                  {perf && <Badge text={perf.status} variant="gray" />}
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div>
                  <span className="text-gray-500">Metric:</span>{' '}
                  <span className="font-medium">{g.target_metric}</span>
                </div>
                <div>
                  <span className="text-gray-500">Direction:</span>{' '}
                  <span className="font-medium">{g.direction}</span>
                </div>
                <div>
                  <span className="text-gray-500">Target:</span>{' '}
                  <span className="font-medium">{g.target_value != null ? (g.target_value * 100).toFixed(1) + '%' : 'N/A'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Current:</span>{' '}
                  <span className="font-bold">{perf?.current_value != null ? (perf.current_value * 100).toFixed(1) + '%' : 'N/A'}</span>
                </div>
              </div>
              {perf?.progress_pct != null && (
                <div className="mt-3">
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div className={'h-2 rounded-full ' + (perf.progress_pct >= 100 ? 'bg-green-500' : perf.progress_pct >= 70 ? 'bg-blue-500' : 'bg-yellow-500')}
                      style={{ width: Math.min(perf.progress_pct, 100) + '%' }} />
                  </div>
                  <span className="text-xs text-gray-500 mt-1">{perf.progress_pct.toFixed(1)}%</span>
                </div>
              )}
              {perf?.guardrail_violations?.length > 0 && (
                <div className="mt-2">
                  {perf.guardrail_violations.map((v: string, i: number) => (
                    <Badge text={v} variant="red" />
                  ))}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
