export type Pt = [number, number];

// The tear SVG is 2400 x 80 user units with its baseline at y = 40, so a vertex
// may wander 40px either side of the baseline before it clips.
const W = 2400;
const STEP = 12;
const INSET = 40;

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

/** Deterministic PRNG: the same seed must always produce the same tear. */
export function mulberry32(a: number) {
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * A torn-paper baseline: a slow drifting wave carrying fine teeth, with the
 * occasional deep notch. The tail is blended back into the head so a tear can
 * tile horizontally without a visible seam.
 */
export function makeTear(seed: number, amp = 16): Pt[] {
  const r = mulberry32(seed);
  const n = W / STEP;
  const pts: Pt[] = [];
  let drift = 0;
  for (let i = 0; i <= n; i++) {
    drift = drift * 0.93 + (r() - 0.5) * 5;
    const tooth = (r() - 0.5) * amp;
    const notch = r() < 0.05 ? (r() - 0.5) * amp * 2.4 : 0;
    pts.push([i * STEP, drift * 3 + tooth + notch]);
  }
  const y0 = pts[0][1];
  for (let k = 0; k < 8; k++) {
    const w = (8 - k) / 8;
    pts[n - k][1] = pts[n - k][1] * (1 - w) + y0 * w;
  }
  return pts;
}

const px = (x: number) => `${((x / W) * 100).toFixed(3)}%`;

export function clipPolygon(pts: Pt[], edge: 'bottom' | 'top'): string {
  if (edge === 'bottom') {
    const line = pts
      .map(([x, y]) => `${px(x)} calc(100% - ${INSET}px + ${y.toFixed(1)}px)`)
      .reverse();
    return `polygon(0 0, 100% 0, ${line.join(', ')})`;
  }
  const line = pts.map(([x, y]) => `${px(x)} calc(${INSET}px + ${y.toFixed(1)}px)`);
  return `polygon(${line.join(', ')}, 100% 100%, 0 100%)`;
}

const cache = new Map<string, ReturnType<typeof build>>();

/**
 * Three curves share one baseline: the clip that cuts the sheet, a pale fibre
 * band of varying thickness just past the cut, and a grey shadow strip below it.
 */
function build(seed: number, edge: 'bottom' | 'top') {
  const A = makeTear(seed);
  const r = mulberry32(seed + 99);
  const dir = edge === 'bottom' ? 1 : -1;

  let th = 10;
  const B: Pt[] = A.map(([x, y]) => {
    th = clamp(th + (r() - 0.5) * 3, 6, 16);
    return [x, y + dir * th];
  });
  const S: Pt[] = B.map(([x, y]) => [x, y + dir * (6 + (r() - 0.5) * 3)]);

  const line = (p: Pt[]) =>
    p.map(([x, y], i) => `${i ? 'L' : 'M'}${x} ${(y + INSET).toFixed(1)}`).join('');
  const band = (a: Pt[], b: Pt[]) =>
    line(a) +
    [...b].reverse().map(([x, y]) => `L${x} ${(y + INSET).toFixed(1)}`).join('') +
    'Z';

  return { clip: clipPolygon(A, edge), fibre: band(A, B), shadow: band(B, S) };
}

export function getTear(seed: number, edge: 'bottom' | 'top') {
  const k = `${seed}:${edge}`;
  if (!cache.has(k)) cache.set(k, build(seed, edge));
  return cache.get(k)!;
}
