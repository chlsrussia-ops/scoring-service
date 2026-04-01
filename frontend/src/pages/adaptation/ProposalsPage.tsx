import { useEffect, useState } from 'react';
import Card from '../../components/Card';
import Badge from '../../components/Badge';
import { api } from '../../api/client';

export default function ProposalsPage() {
  const [proposals, setProposals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.adaptationProposals()
      .then((d: any) => setProposals(d.proposals || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const riskColor = (r: string) => r === 'safe' ? 'green' : r === 'moderate' ? 'yellow' : 'red';
  const statusColor = (s: string) => {
    if (s === 'applied') return 'green';
    if (s === 'pending') return 'yellow';
    if (s === 'rejected' || s === 'rolled_back') return 'red';
    return 'gray';
  };

  if (loading) return <div className="animate-pulse text-gray-400">Loading proposals...</div>;

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Adaptation Proposals</h1>
      {proposals.length === 0 && (
        <Card><p className="text-gray-500">No proposals yet.</p></Card>
      )}
      <div className="space-y-4">
        {proposals.map((p: any) => (
          <Card key={p.id}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="font-semibold">#{p.id}</span>
                <Badge text={p.risk_level} variant="gray" />
                <Badge text={p.status} variant="gray" />
              </div>
              <span className="text-xs text-gray-400">{new Date(p.created_at).toLocaleString()}</span>
            </div>
            <div className="text-sm mb-2">
              <span className="text-gray-500">Type:</span> <span className="font-medium">{p.proposal_type}</span>
              <span className="text-gray-500 ml-3">Target:</span> <span className="font-medium">{p.target_type}/{p.target_id}</span>
            </div>
            <p className="text-sm text-gray-700 mb-3">{p.reason}</p>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="bg-gray-50 rounded p-2">
                <div className="text-xs text-gray-500 mb-1">Current</div>
                <pre className="text-xs overflow-auto">{JSON.stringify(p.current_value_json, null, 1)}</pre>
              </div>
              <div className="bg-blue-50 rounded p-2">
                <div className="text-xs text-blue-500 mb-1">Proposed</div>
                <pre className="text-xs overflow-auto">{JSON.stringify(p.proposed_value_json, null, 1)}</pre>
              </div>
            </div>
            {p.status === 'pending' && (
              <div className="flex gap-2 mt-3">
                <button onClick={() => api.approveProposal(p.id).then(load)} className="px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700">Approve</button>
                <button onClick={() => api.rejectProposal(p.id).then(load)} className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700">Reject</button>
                <button onClick={() => api.simulateProposal(p.id).then(r => alert(JSON.stringify(r, null, 2)))} className="px-3 py-1 bg-gray-200 text-gray-700 text-sm rounded hover:bg-gray-300">Simulate</button>
              </div>
            )}
            {p.status === 'approved' && (
              <div className="flex gap-2 mt-3">
                <button onClick={() => api.applyProposal(p.id).then(load)} className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">Apply</button>
              </div>
            )}
            {p.status === 'applied' && (
              <div className="flex gap-2 mt-3">
                <button onClick={() => api.rollbackProposal(p.id).then(load)} className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700">Rollback</button>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
