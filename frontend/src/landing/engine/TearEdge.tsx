import { getTear } from './tear';

export function TearEdge({ seed, edge }: { seed: number; edge: 'bottom' | 'top' }) {
  const t = getTear(seed, edge);
  return (
    <svg
      className={`tear-svg tear-${edge}`}
      viewBox="0 0 2400 80"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d={t.shadow} fill="var(--shadow-strip)" opacity=".7" />
      <path d={t.fibre} fill="var(--cream)" filter="url(#paper-fibre)" />
    </svg>
  );
}
