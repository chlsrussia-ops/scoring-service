import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Card from '../../components/Card';
import Badge from '../../components/Badge';
import { api } from '../../api/client';

interface AdaptationStatus {
  mode: string;
  enabled: boolean;
  pending_proposals: number;
  active_experiments: number;
  active_goals: number;
  recent_evaluations: number;
  recent_rollbacks: number;
  last_evaluation_at: string | null;
  degraded_metrics: string[];
  improvements: string[];
}

export default function AdaptationOverview() {
  const [status, setStatus] = useState<AdaptationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.adaptationStatus()
      .then(setStatus)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="animate-pulse text-gray-400">Loading adaptation status...</div>;
  if (error) return <div className="text-red-500">Error: {error}</div>;
  if (!status) return <div className="text-gray-500">No data</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Adaptation & Self-Improvement</h1>
          <p className="text-gray-500 mt-1">System learning loop status and controls</p>
        </div>
        <div className="flex gap-2">
          <Badge text={status.enabled ? 'Enabled' : 'Disabled'} variant="gray" />
          <Badge text={status.mode} variant="blue" />
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <Card>
          <div className="text-sm text-gray-500">Pending Proposals</div>
          <div className="text-3xl font-bold text-brand-600">{status.pending_proposals}</div>
        </Card>
        <Card>
          <div className="text-sm text-gray-500">Active Experiments</div>
          <div className="text-3xl font-bold text-purple-600">{status.active_experiments}</div>
        </Card>
        <Card>
          <div className="text-sm text-gray-500">Active Goals</div>
          <div className="text-3xl font-bold text-emerald-600">{status.active_goals}</div>
        </Card>
        <Card>
          <div className="text-sm text-gray-500">Recent Rollbacks</div>
          <div className={'text-3xl font-bold ' + (status.recent_rollbacks > 0 ? 'text-red-600' : 'text-gray-400')}>{status.recent_rollbacks}</div>
        </Card>
      </div>

      {status.degraded_metrics.length > 0 && (
        <Card className="mb-6 border-red-200 bg-red-50">
          <h3 className="font-semibold text-red-800 mb-2">Degraded Metrics</h3>
          <ul className="space-y-1">
            {status.degraded_metrics.map((m, i) => (
              <li key={i} className="text-red-700 text-sm">{m}</li>
            ))}
          </ul>
        </Card>
      )}

      {status.improvements.length > 0 && (
        <Card className="mb-6 border-green-200 bg-green-50">
          <h3 className="font-semibold text-green-800 mb-2">Recent Improvements</h3>
          <ul className="space-y-1">
            {status.improvements.map((m, i) => (
              <li key={i} className="text-green-700 text-sm">{m}</li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link to="/adaptation/quality" className="block">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <h3 className="font-semibold text-gray-900 mb-1">Quality Scorecards</h3>
            <p className="text-sm text-gray-500">View precision, usefulness, and quality metrics</p>
          </Card>
        </Link>
        <Link to="/adaptation/proposals" className="block">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <h3 className="font-semibold text-gray-900 mb-1">Proposals</h3>
            <p className="text-sm text-gray-500">Review and manage adaptation proposals</p>
          </Card>
        </Link>
        <Link to="/adaptation/goals" className="block">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <h3 className="font-semibold text-gray-900 mb-1">Goals</h3>
            <p className="text-sm text-gray-500">Track optimization goals and progress</p>
          </Card>
        </Link>
        <Link to="/adaptation/experiments" className="block">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <h3 className="font-semibold text-gray-900 mb-1">Experiments</h3>
            <p className="text-sm text-gray-500">Shadow runs, replays, and canary rollouts</p>
          </Card>
        </Link>
        <Link to="/adaptation/sources" className="block">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <h3 className="font-semibold text-gray-900 mb-1">Source Trust</h3>
            <p className="text-sm text-gray-500">Source learning and trust evolution</p>
          </Card>
        </Link>
      </div>

      {status.last_evaluation_at && (
        <p className="text-xs text-gray-400 mt-6">
          Last evaluation: {new Date(status.last_evaluation_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}
