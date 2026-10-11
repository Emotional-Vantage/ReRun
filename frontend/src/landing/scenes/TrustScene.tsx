import React from 'react';

export const TrustScene: React.FC = () => {
  const tiles = [
    {
      num: '01',
      title: 'Locked Sandbox',
      desc: 'Containers run with dropped privileges, non-root users, isolated networks, and 4GB memory / 128 PID quotas.',
      tilt: '-1.2deg',
    },
    {
      num: '02',
      title: 'Human Sign-off',
      desc: 'Every patch requires an explicit human click in the dashboard. No auto-approval, no shortcut bypasses.',
      tilt: '1.2deg',
    },
    {
      num: '03',
      title: 'No Metric Chasing',
      desc: 'Patches cannot be justified by "it improves the score". They must cite an error cause or verbatim paper quote.',
      tilt: '-0.8deg',
    },
    {
      num: '04',
      title: 'Hashed Evidence Ledger',
      desc: 'Every claim and conclusion links to a sha256-hashed artifact slice in the tamper-evident evidence ledger.',
      tilt: '1deg',
    },
    {
      num: '05',
      title: 'Computed Statuses',
      desc: 'The final reproduction status is calculated deterministically by mathematical tools, never narrated by LLMs.',
      tilt: '-1.4deg',
    },
    {
      num: '06',
      title: 'Never Accuses the Paper',
      desc: 'Failures are strictly framed as computational reproducibility limits of the codebase in the given environment.',
      tilt: '0.8deg',
    },
  ];

  return (
    <div
      className="relative w-full h-full overflow-hidden flex flex-col justify-between items-center px-6 pt-28 pb-6 md:pt-32 md:pb-8"
      style={{
        background: 'linear-gradient(180deg, var(--ember-top) 0%, var(--ember-bot) 100%)',
        color: 'var(--cream)',
      }}
    >
      {/* Campfire radial warm glow */}
      <div
        className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[37.5rem] h-[18.75rem] rounded-full pointer-events-none opacity-25 blur-3xl"
        style={{ background: 'var(--ember-glow)' }}
        aria-hidden="true"
      />

      {/* Floating Embers in the air */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden="true">
        {[
          [350, 420, 2], [420, 310, 1.5], [560, 480, 2.5], [680, 360, 2], [750, 240, 1],
          [820, 440, 2.8], [910, 320, 2], [1020, 460, 1.8], [1150, 290, 2.2], [1280, 380, 1.5]
        ].map(([cx, cy, r], i) => (
          <circle key={i} cx={cx} cy={cy} r={r} fill="var(--ember-glow)" opacity="0.6" />
        ))}
      </svg>

      {/* Header Zone */}
      <div className="relative z-10 text-center max-w-3xl mt-2 md:mt-4">
        <div className="text-[11px] font-mono uppercase tracking-[0.28em] text-cream/70 mb-1">
          No. 05 · Guardrails & Integrity
        </div>
        <h2 className="font-serif text-3xl md:text-5xl uppercase tracking-[0.02em] text-cream leading-tight">
          Built to be Trusted
        </h2>
        <p className="mt-2 text-xs md:text-sm font-mono text-cream/80 max-w-xl mx-auto">
          Scientific verification requires verifiable evidence, not persuasive text.
        </p>
      </div>

      {/* Six Cream Trail-Sign Tiles */}
      <div className="relative z-10 w-full max-w-5xl grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 my-auto">
        {tiles.map((t, idx) => (
          <div
            key={idx}
            className="group relative bg-cream text-ink rounded-sm p-5 shadow-xl border border-kraft/60 flex flex-col justify-between transition-all duration-300 hover:rotate-0 hover:scale-105"
            style={{ transform: `rotate(${t.tilt})` }}
          >
            <div>
              <div className="flex justify-between items-center mb-2 border-b border-kraft/60 pb-1.5">
                <span className="font-mono text-xs font-bold text-rust-ink">
                  {t.num} · GUARDRAIL
                </span>
                <span className="text-[9px] font-mono text-ink-soft">STRICT</span>
              </div>
              <h3 className="font-serif text-lg font-bold text-ink uppercase tracking-wide">
                {t.title}
              </h3>
              <p className="font-mono text-xs text-ink-soft leading-relaxed mt-2">{t.desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Bottom spacer */}
      <div className="h-6 pointer-events-none" />
    </div>
  );
};

export const TrustTeaser: React.FC = () => {
  return (
    <div
      className="relative w-full h-full flex items-center justify-between px-8 md:px-14 select-none overflow-hidden"
      style={{
        background: 'linear-gradient(180deg, var(--dawn-top) 0%, var(--dawn-low) 100%)',
        color: 'var(--ink)',
      }}
    >
      <div className="relative z-10 flex items-center gap-2 font-mono text-[11px] md:text-xs uppercase tracking-[0.22em] text-ink font-medium">
        <span className="text-rust">↓</span>
        <span>KEEP SCROLLING — THE RECORDED RUN</span>
      </div>

      <div className="relative z-10 flex items-center gap-2 font-mono text-[11px] md:text-xs uppercase tracking-[0.22em] text-ink-soft">
        <span>NEXT — THE ROUTE SO FAR · CASE B4</span>
        <span className="text-rust">→</span>
      </div>
    </div>
  );
};
