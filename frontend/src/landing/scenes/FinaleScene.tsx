import React from 'react';
import { Link } from 'react-router-dom';

export const FinaleScene: React.FC = () => {
  const cases = [
    {
      id: 'b1_control',
      name: 'B1: Control',
      tag: '0 Patches',
      desc: 'Correct paper code. Reproduces on Run 1.',
    },
    {
      id: 'b2_dependency',
      name: 'B2: Dependency',
      tag: '1 Patch',
      desc: 'Missing PyYAML. Traceback classified & fixed.',
    },
    {
      id: 'b3_silent_config',
      name: 'B3: Silent Config',
      tag: '1 Patch',
      desc: 'lr=0.01 vs paper 0.5. Config audited.',
    },
    {
      id: 'b4_combined',
      name: 'B4: Combined',
      tag: '2 Patches',
      desc: 'Missing PyYAML + config drift. Demo flow.',
    },
    {
      id: 'b5_unable',
      name: 'B5: Needs GPU',
      tag: 'Blocker Evidence',
      desc: 'Requires CUDA. UNABLE_TO_EXECUTE.',
    },
  ];

  const verdicts = [
    {
      status: 'REPRODUCED',
      desc: 'Primary claims fall within paper tolerance.',
      color: '#22C55E',
    },
    {
      status: 'PARTIALLY_REPRODUCED',
      desc: 'Some claims met, or minor deviation.',
      color: '#F59E0B',
    },
    {
      status: 'NOT_REPRODUCED',
      desc: 'Execution complete but number diverges.',
      color: '#EF4444',
    },
    {
      status: 'UNABLE_TO_EXECUTE',
      desc: 'Environmental blocker (e.g. missing CUDA).',
      color: '#64748B',
    },
    {
      status: 'INCONCLUSIVE',
      desc: 'No confirmed claim or unparseable output.',
      color: '#A78BFA',
    },
  ];

  return (
    <div
      className="relative w-full h-full overflow-hidden flex flex-col justify-between items-center px-6 pt-28 pb-6 md:pt-32 md:pb-8"
      style={{
        background: 'var(--night-deep)',
        color: 'var(--cream)',
      }}
    >
      {/* Background Starry Sky */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none opacity-40"
        aria-hidden="true"
      >
        {[
          [200, 100], [450, 180], [700, 90], [950, 160], [1200, 80],
          [1450, 150], [1700, 110], [300, 320], [600, 280], [1100, 310]
        ].map(([cx, cy], i) => (
          <circle key={i} cx={cx} cy={cy} r="1.2" fill="#F1ECE0" />
        ))}
      </svg>

      {/* Header Zone */}
      <div className="relative z-10 text-center max-w-3xl mt-2">
        <div className="text-[11px] font-mono uppercase tracking-[0.28em] text-cream/70 mb-1">
          No. 07 · The Benchmark Ground Truth
        </div>
        <h2 className="font-serif text-3xl md:text-5xl uppercase tracking-[0.02em] text-cream leading-tight">
          Five Cases to Retrace
        </h2>
        <div className="mt-2 text-xs font-mono text-rust tracking-widest uppercase font-semibold">
          Synthetic benchmark papers, labelled as such.
        </div>
      </div>

      {/* 5 Luggage-Tag Benchmark Cases */}
      <div className="relative z-10 w-full max-w-5xl grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5 my-auto">
        {cases.map((c) => (
          <div
            key={c.id}
            className={`group relative bg-paper text-ink p-4 rounded-sm shadow-lg border border-kraft flex flex-col justify-between transition-all hover:scale-105 ${
              c.id === 'b4_combined' ? 'ring-2 ring-rust' : ''
            }`}
            style={{
              clipPath:
                'polygon(0% 6px, 6px 0%, calc(100% - 6px) 0%, 100% 6px, 100% 100%, 0% 100%)',
            }}
          >
            {/* Luggage tag hole */}
            <div className="w-2.5 h-2.5 rounded-full border border-kraft bg-[#CDC8BA] mx-auto mb-2" />

            <div>
              <div className="flex justify-between items-center text-[10px] font-mono mb-1">
                <span className="font-bold text-ink">{c.name}</span>
              </div>
              <span className="inline-block text-[9px] font-mono px-1.5 py-0.5 bg-kraft-light text-ink uppercase tracking-wider font-semibold mb-2">
                {c.tag}
              </span>
              <p className="text-[11px] font-mono text-ink-soft leading-snug">{c.desc}</p>
            </div>

            <Link
              to={`/new?case=${c.id}`}
              className="mt-3 text-[10px] font-mono font-bold text-rust-ink uppercase tracking-wider hover:underline"
            >
              Retrace Case →
            </Link>
          </div>
        ))}
      </div>

      {/* Standardized Verdict Stamps */}
      <div className="relative z-10 w-full max-w-5xl border-t border-cream/20 pt-4">
        <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-cream/70 text-center mb-3">
          Five Standardized Computed Verdicts (Mathematical Evidence)
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 text-center">
          {verdicts.map((v) => (
            <div key={v.status} className="p-2.5 bg-night-bot/70 border border-cream/15 rounded-sm">
              <span
                className="inline-block text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded"
                style={{
                  color: v.color,
                  border: `1px solid ${v.color}40`,
                  background: `${v.color}15`,
                }}
              >
                {v.status}
              </span>
              <p className="text-[10px] font-mono text-cream/60 mt-1.5 leading-tight">{v.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Spacer */}
      <div className="h-2 pointer-events-none" />
    </div>
  );
};
