interface MiniChartProps {
  values: number[];
  color?: string;
  height?: number;
}

export default function MiniChart({ values, color = '#3b82f6', height = 32 }: MiniChartProps) {
  if (!values.length) return null;
  const max = Math.max(...values, 1);
  const w = 100 / values.length;

  return (
    <svg viewBox={`0 0 100 ${height}`} className="w-full" style={{ height }} preserveAspectRatio="none">
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={values.map((v, i) => `${i * w + w / 2},${height - (v / max) * (height - 4) - 2}`).join(' ')}
      />
    </svg>
  );
}
