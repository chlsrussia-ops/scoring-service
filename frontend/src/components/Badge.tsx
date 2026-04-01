interface BadgeProps {
  text: string;
  variant?: 'green' | 'amber' | 'red' | 'blue' | 'gray' | 'purple';
}

const COLORS: Record<string, string> = {
  green: 'bg-green-100 text-green-800',
  amber: 'bg-amber-100 text-amber-800',
  red: 'bg-red-100 text-red-800',
  blue: 'bg-blue-100 text-blue-800',
  gray: 'bg-gray-100 text-gray-800',
  purple: 'bg-purple-100 text-purple-800',
};

export default function Badge({ text, variant = 'gray' }: BadgeProps) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${COLORS[variant]}`}>
      {text}
    </span>
  );
}

export function priorityColor(p: string): 'red' | 'amber' | 'green' | 'gray' {
  if (p === 'high') return 'red';
  if (p === 'medium') return 'amber';
  if (p === 'low') return 'green';
  return 'gray';
}

export function severityColor(s: string): 'red' | 'amber' | 'blue' | 'gray' {
  if (s === 'high' || s === 'critical') return 'red';
  if (s === 'medium') return 'amber';
  if (s === 'low' || s === 'info') return 'blue';
  return 'gray';
}

export function statusColor(s: string): 'green' | 'amber' | 'red' | 'gray' | 'blue' {
  if (s === 'active' || s === 'ok' || s === 'acknowledged') return 'green';
  if (s === 'syncing' || s === 'open' || s === 'dispatched') return 'amber';
  if (s === 'error' || s === 'failed') return 'red';
  if (s === 'rising' || s === 'accelerating') return 'blue';
  return 'gray';
}
