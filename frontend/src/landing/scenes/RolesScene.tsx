import React from 'react';

export const RolesScene: React.FC = () => {
  const roles = [
    {
      name: 'Solver',
      roleColor: 'var(--solver)',
      borderClass: 'border-[#14B8A6]',
      bgSeal: '#14B8A6',
      subtitle: 'Investigates & Proposes',
      tilt: '-2deg',
      desc: 'Diagnoses traceback logs, executes non-destructive file reads, and proposes minimal patches. Forbidden from applying code directly.',
      rule: 'Generates minimal unified diffs.',
    },
    {
      name: 'Critic',
      roleColor: 'var(--critic)',
      borderClass: 'border-[#A78BFA]',
      bgSeal: '#A78BFA',
      subtitle: 'Independent Reviewer',
      tilt: '1.5deg',
      desc: 'Validates 9 strict security & integrity checks. Rejects metric-chasing, ungrounded edits, and oversized modifications.',
      rule: 'Can only make decisions stricter.',
    },
    {
      name: 'Rulebook',
      roleColor: 'var(--tool)',
      borderClass: 'border-[#64748B]',
      bgSeal: '#64748B',
      subtitle: 'Deterministic Policy',
      tilt: '-1.2deg',
      desc: 'Hardcoded Python arbiter enforcing boundaries: maximum 5 files, maximum 200 lines, deny-list on networking and system configs.',
      rule: 'Mathematical gate, not an LLM.',
    },
    {
      name: 'You (Human)',
      roleColor: 'var(--human)',
      borderClass: 'border-[#F59E0B]',
      bgSeal: '#F59E0B',
      subtitle: 'Final Sign-off Gate',
      tilt: '2deg',
      desc: 'You confirm extracted paper claims and explicitly authorize every patch. No code enters the sandbox without your physical click.',
      rule: 'Complete sovereign authority.',
    },
  ];

  return (
    <div
      className="relative w-full h-full overflow-hidden flex flex-col justify-between items-center px-6 pt-28 pb-6 md:pt-32 md:pb-8"
      style={{
        background: 'var(--rose-paper)',
        color: 'var(--ink)',
      }}
    >
      {/* Background Lilac Mountain Silhouette */}
      <svg
        viewBox="0 0 1200 400"
        preserveAspectRatio="none"
        className="absolute inset-x-0 bottom-0 w-full h-64 pointer-events-none opacity-40"
        aria-hidden="true"
      >
        <path
          d="M 0 350 Q 300 200, 600 260 T 1200 220 L 1200 400 L 0 400 Z"
          fill="var(--mtn-lilac)"
        />
        <path
          d="M 0 380 Q 400 300, 800 340 T 1200 310 L 1200 400 L 0 400 Z"
          fill="var(--mtn-peach)"
          opacity="0.6"
        />
      </svg>

      {/* Header Zone */}
      <div className="relative z-10 text-center max-w-3xl mt-2 md:mt-4">
        <div className="text-[11px] font-mono uppercase tracking-[0.28em] text-ink-soft mb-1">
          No. 04 · Multi-Agent Governance
        </div>
        <h2 className="font-serif text-3xl md:text-5xl uppercase tracking-[0.02em] text-ink leading-tight">
          Meet the Roles
        </h2>
        {/* Authority trail */}
        <div className="mt-3 inline-flex items-center gap-2 px-4 py-1.5 bg-paper border border-kraft rounded-full text-xs font-mono font-bold text-rust-ink shadow-sm">
          <span>You (Human)</span>
          <span>&gt;</span>
          <span>Rulebook</span>
          <span>&gt;</span>
          <span>Critic</span>
          <span>&gt;</span>
          <span>Solver</span>
        </div>
      </div>

      {/* Four Taped Notes Grid */}
      <div className="relative z-10 w-full max-w-5xl grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 my-auto">
        {roles.map((r, i) => (
          <div
            key={i}
            className="group relative bg-paper rounded-sm p-6 shadow-lg border border-kraft transition-all duration-300 hover:rotate-0 hover:scale-105 hover:shadow-2xl flex flex-col justify-between min-h-[18.125rem]"
            style={{ transform: `rotate(${r.tilt})` }}
          >
            {/* Washi Tape on top */}
            <div
              className="absolute -top-3 left-1/2 -translate-x-1/2 w-16 h-5 washi-tape transform -rotate-1 z-20"
              aria-hidden="true"
            />

            {/* Note Header & Wax Seal */}
            <div>
              <div className="flex items-center justify-between mb-3 border-b border-kraft/60 pb-2">
                <span className="font-mono text-xs font-bold uppercase tracking-wider text-ink">
                  {r.name}
                </span>
                {/* Wax seal circle */}
                <div
                  className="w-5 h-5 rounded-full shadow-inner border border-black/20 flex items-center justify-center text-[9px] font-bold text-white"
                  style={{ background: r.bgSeal }}
                >
                  ✓
                </div>
              </div>

              <div className="text-[11px] font-mono text-rust-ink font-semibold tracking-wide uppercase mb-2">
                {r.subtitle}
              </div>

              <p className="font-mono text-xs text-ink-soft leading-relaxed">{r.desc}</p>
            </div>

            {/* Footer Rule tag */}
            <div className="mt-4 pt-2 border-t border-kraft/40 text-[10px] font-mono text-ink">
              <span className="font-bold">Policy: </span>
              <span>{r.rule}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Bottom spacer */}
      <div className="h-6 pointer-events-none" />
    </div>
  );
};

export const RolesTeaser: React.FC = () => {
  return (
    <div
      className="relative w-full h-full flex items-center justify-between px-8 md:px-14 select-none overflow-hidden"
      style={{
        background: 'linear-gradient(180deg, var(--ember-top) 0%, var(--ember-bot) 100%)',
        color: 'var(--cream)',
      }}
    >
      <div className="relative z-10 flex items-center gap-2 font-mono text-[11px] md:text-xs uppercase tracking-[0.22em] text-cream font-medium">
        <span className="text-rust">↓</span>
        <span>KEEP SCROLLING — SECURITY ARCHITECTURE</span>
      </div>

      <div className="relative z-10 flex items-center gap-2 font-mono text-[11px] md:text-xs uppercase tracking-[0.22em] text-cream/80">
        <span>NEXT — BUILT TO BE TRUSTED</span>
        <span className="text-rust">→</span>
      </div>
    </div>
  );
};
