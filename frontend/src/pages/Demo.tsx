import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import Card, { StatCard } from '../components/Card';

interface StepResult {
  step: string;
  status: 'pending' | 'running' | 'done' | 'error';
  result?: any;
}

export default function Demo() {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [steps, setSteps] = useState<StepResult[]>([]);
  const [runningAll, setRunningAll] = useState(false);

  const loadStatus = () => {
    api.demoStatus().then(setStatus).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(loadStatus, []);

  const runStep = async (name: string, fn: () => Promise<any>) => {
    setSteps(prev => [...prev.filter(s => s.step !== name), { step: name, status: 'running' }]);
    try {
      const result = await fn();
      setSteps(prev => prev.map(s => s.step === name ? { ...s, status: 'done', result } : s));
      loadStatus();
    } catch (e: any) {
      setSteps(prev => prev.map(s => s.step === name ? { ...s, status: 'error', result: e.message } : s));
    }
  };

  const runAll = async () => {
    setRunningAll(true);
    setSteps([]);
    try {
      await runStep('Seed demo data', api.demoSeed);
      await runStep('Sync sources', api.demoSyncSources);
      await runStep('Run analysis', api.demoRunAnalysis);
      await runStep('Generate AI summaries', api.demoGenerateAI);
      await runStep('Dispatch alerts', api.demoDispatchAlerts);
    } finally {
      setRunningAll(false);
      loadStatus();
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Demo Control Center</h1>
          <p className="text-gray-500 mt-1">Run the full TrendIntel demo pipeline in minutes</p>
        </div>
        <button
          onClick={runAll}
          disabled={runningAll}
          className="px-6 py-3 bg-brand-600 text-white rounded-lg hover:bg-brand-700 font-medium transition-colors disabled:opacity-50"
        >
          {runningAll ? 'Running Full Pipeline...' : 'Run Full Demo'}
        </button>
      </div>

      {status && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          <StatCard label="Events" value={status.events || 0} color="blue" />
          <StatCard label="Trends" value={status.trends || 0} color="green" />
          <StatCard label="Recommendations" value={status.recommendations || 0} color="purple" />
          <StatCard label="Alerts" value={status.alerts || 0} color="amber" />
          <StatCard label="Sources" value={status.sources || 0} color="blue" />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <Card title="Individual Steps">
          <div className="space-y-3">
            {[
              { label: 'Seed Demo Data', desc: '1200+ events, trends, recommendations, alerts', fn: api.demoSeed, step: 'seed' },
              { label: 'Sync Sources', desc: 'Fetch from RSS, Reddit (mock), APIs', fn: api.demoSyncSources, step: 'sync' },
              { label: 'Run Analysis', desc: 'Detect trends, generate signals', fn: api.demoRunAnalysis, step: 'analysis' },
              { label: 'Generate AI Summaries', desc: 'LLM-powered trend narratives & recommendations', fn: api.demoGenerateAI, step: 'ai' },
              { label: 'Dispatch Alerts', desc: 'Send alerts to content team channels', fn: api.demoDispatchAlerts, step: 'alerts' },
            ].map(item => {
              const stepState = steps.find(s => s.step === item.label || s.step === item.step);
              return (
                <div key={item.step} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <p className="font-medium text-sm text-gray-900">{item.label}</p>
                    <p className="text-xs text-gray-500">{item.desc}</p>
                  </div>
                  <button
                    onClick={() => runStep(item.label, item.fn)}
                    disabled={runningAll}
                    className="px-4 py-1.5 bg-white border border-gray-200 text-gray-700 rounded-lg text-xs hover:bg-gray-100 disabled:opacity-50"
                  >
                    Run
                  </button>
                </div>
              );
            })}
          </div>
        </Card>

        <Card title="Pipeline Progress">
          {steps.length > 0 ? (
            <div className="space-y-3">
              {steps.map(s => (
                <div key={s.step} className="flex items-center gap-3 text-sm">
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    s.status === 'done' ? 'bg-green-500' : s.status === 'running' ? 'bg-amber-500 animate-pulse' : s.status === 'error' ? 'bg-red-500' : 'bg-gray-300'
                  }`} />
                  <span className="font-medium">{s.step}</span>
                  <span className={`text-xs ml-auto ${s.status === 'done' ? 'text-green-600' : s.status === 'error' ? 'text-red-600' : 'text-gray-400'}`}>
                    {s.status === 'done' ? 'Complete' : s.status === 'running' ? 'Running...' : s.status === 'error' ? 'Failed' : 'Pending'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-400 text-sm">Run a step or the full pipeline to see progress here.</p>
          )}
        </Card>
      </div>

      <Card title="Demo Stories - What to Show">
        <div className="space-y-4">
          {[
            { title: 'News / Media Trend Spike', desc: 'AI content tools go viral - see how the platform detects and alerts your team.', links: [{ to: '/trends', label: 'View Trends' }] },
            { title: 'Reddit Topic Explosion', desc: 'Short-form video discussion explodes - real-time category tracking.', links: [{ to: '/trends', label: 'View Trends' }, { to: '/alerts', label: 'View Alerts' }] },
            { title: 'Category Anomaly', desc: 'Creator economy + AI emerges as unexpected theme - anomaly detection.', links: [{ to: '/recommendations', label: 'View Recommendations' }] },
          ].map(story => (
            <div key={story.title} className="p-4 border border-gray-100 rounded-lg">
              <h4 className="font-semibold text-gray-900">{story.title}</h4>
              <p className="text-sm text-gray-600 mt-1">{story.desc}</p>
              <div className="flex gap-2 mt-2">
                {story.links.map(l => (
                  <Link key={l.to} to={l.to} className="text-xs text-brand-600 hover:underline">{l.label} &rarr;</Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {status?.recent_runs?.length > 0 && (
        <Card title="Recent Runs" className="mt-6">
          <div className="space-y-2 text-sm">
            {status.recent_runs.map((r: any) => (
              <div key={r.id} className="flex items-center justify-between text-xs">
                <span className="font-medium">{r.action}</span>
                <span className={r.status === 'completed' ? 'text-green-600' : 'text-gray-400'}>{r.status}</span>
                <span className="text-gray-400">{r.started_at?.split('T')[0]}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
