import React, { useState } from 'react';
import { Link } from 'react-router-dom';

export const DemoScene: React.FC = () => {
  const [activeStep, setActiveStep] = useState(3);

  const steps = [
    {
      id: 1,
      title: 'Run 1: Crashes',
      tag: 'Env Error',
      desc: 'Exit code 1. ModuleNotFoundError: yaml.',
    },
    {
      id: 2,
      title: 'Patch 1: Approved',
      tag: 'Human Sign-off',
      desc: 'PyYAML==6.0.1 added. Critic checks pass.',
    },
    {
      id: 3,
      title: 'Run 2: Silent Divergence',
      tag: 'Wrong Metric',
      desc: 'Exit 0, accuracy 0.8733 vs 0.9560 claimed.',
    },
    {
      id: 4,
      title: 'Patch 2: Config Audit',
      tag: 'Grounding',
      desc: 'learning_rate 0.01 -> 0.5 citing paper p.1.',
    },
    {
      id: 5,
      title: 'Run 3: Verified',
      tag: 'Reproduced',
      desc: 'Observed 0.9556 ± 0.0018. Verdict REPRODUCED.',
    },
  ];

  return (
    <div
      className="relative w-full h-full overflow-hidden flex flex-col justify-between items-center px-6 pt-28 pb-6 md:pt-32 md:pb-8"
      style={{
        background:
          'linear-gradient(180deg, var(--dawn-top) 0%, var(--dawn-mid) 50%, var(--dawn-low) 100%)',
        color: 'var(--ink)',
      }}
    >
      {/* Topographic Contour Lines SVG Background */}
      <svg
        viewBox="0 0 1200 600"
        preserveAspectRatio="none"
        className="absolute inset-0 w-full h-full pointer-events-none opacity-30 stroke-ink/30 fill-none"
        aria-hidden="true"
      >
        <path d="M 0 150 Q 300 80, 600 130 T 1200 90" strokeWidth="1" />
        <path d="M 0 220 Q 350 180, 700 240 T 1200 190" strokeWidth="1" />
        <path d="M 0 310 Q 400 260, 800 330 T 1200 270" strokeWidth="1" />
        <path d="M 0 400 Q 450 360, 900 420 T 1200 360" strokeWidth="1" />
        {/* Summit Elevation Ring */}
        <ellipse cx="980" cy="180" rx="120" ry="60" strokeWidth="1" strokeDasharray="4 2" />
        <ellipse cx="980" cy="180" rx="60" ry="30" strokeWidth="1" />
      </svg>

      {/* Header Zone */}
      <div className="relative z-10 text-center max-w-3xl mt-2">
        <div className="text-[11px] font-mono uppercase tracking-[0.28em] text-ink-soft mb-1">
          No. 06 · The Route So Far · Case B4
        </div>
        <h2 className="font-serif text-3xl md:text-5xl uppercase tracking-[0.02em] text-ink leading-tight">
          The Route So Far
        </h2>
        <p className="mt-1 text-xs md:text-sm font-mono text-ink-soft">
          Retracing a run across 3 container attempts and 2 approved patches.
        </p>
      </div>

      {/* Dashed Route Trail with Interactive Flags */}
      <div className="relative z-10 w-full max-w-4xl py-3 px-4">
        {/* Trail Line */}
        <div className="relative w-full h-10 flex items-center justify-between">
          <div className="absolute inset-x-8 top-1/2 -translate-y-1/2 h-[2px] border-b-2 border-dashed border-rust" />

          {steps.map((st, i) => (
            <button
              key={st.id}
              onClick={() => setActiveStep(i)}
              className={`group relative z-10 flex flex-col items-center focus:outline-none transition-all ${
                activeStep === i ? 'scale-110' : 'opacity-70 hover:opacity-100'
              }`}
            >
              {/* Flag Node */}
              <div
                className={`w-7 h-7 rounded-full border-2 flex items-center justify-center font-mono text-[10px] font-bold shadow-md transition-colors ${
                  activeStep === i
                    ? 'bg-rust text-cream border-cream'
                    : 'bg-paper text-ink border-kraft hover:border-rust'
                }`}
              >
                {st.id}
              </div>
              <span className="absolute -bottom-5 whitespace-nowrap text-[9px] font-mono tracking-widest uppercase text-ink-soft font-semibold">
                {st.tag}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Paper Field-Log Card (Sample run recorded) */}
      <div
        className="relative z-20 w-full max-w-4xl bg-paper text-ink p-5 md:p-6 rounded-sm shadow-2xl border border-kraft my-auto"
        style={{ transform: 'rotate(0.8deg)' }}
      >
        {/* Taped Corner */}
        <div className="absolute -top-3 left-8 washi-tape-amber px-3 py-0.5 rounded text-[10px] font-mono text-ink font-bold uppercase tracking-wider shadow-sm transform -rotate-1">
          Sample run (recorded)
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-3">
          {/* Column 1: Live Container Trace */}
          <div className="bg-[#EDE8DA] p-3.5 rounded border border-kraft/70 font-mono text-xs space-y-2">
            <span className="text-[10px] uppercase tracking-wider text-ink-soft block font-bold">
              Execution Trace · Case B4
            </span>
            <div className="space-y-1.5 text-[11px]">
              <div className="flex items-center gap-1.5 text-tool">
                <span className="w-1.5 h-1.5 rounded-full bg-tool" />
                <span>#1 [tool] docker pull: cached</span>
              </div>
              <div className="flex items-center gap-1.5 text-fail font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-fail" />
                <span>#2 [tool] exit 1: No module 'yaml'</span>
              </div>
              <div className="flex items-center gap-1.5 text-solver font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-solver" />
                <span>#3 [solver] patch proposed</span>
              </div>
              <div className="flex items-center gap-1.5 text-human font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-human" />
                <span>#4 [human] patch 1 approved</span>
              </div>
              <div className="flex items-center gap-1.5 text-ok font-bold">
                <span className="w-1.5 h-1.5 rounded-full bg-ok" />
                <span>#5 [system] REPRODUCED (run 3)</span>
              </div>
            </div>
          </div>

          {/* Column 2: Grounding Config Diff */}
          <div className="bg-[#EDE8DA] p-3.5 rounded border border-kraft/70 font-mono text-xs space-y-2">
            <span className="text-[10px] uppercase tracking-wider text-ink-soft block font-bold">
              Config Alignment Diff
            </span>
            <div className="text-[11px] space-y-1">
              <div className="text-ink-soft text-[10px]">configs/default.yaml</div>
              <div className="bg-[#FEE2E2] text-fail px-2 py-0.5 rounded border border-fail/20">
                - learning_rate: 0.01
              </div>
              <div className="bg-[#DCFCE7] text-ok px-2 py-0.5 rounded border border-ok/20 font-semibold">
                + learning_rate: 0.5
              </div>
              <div className="text-[10px] text-ink-soft italic pt-1">
                Paper quote p.1: "learning rate was fixed to 0.5"
              </div>
            </div>
          </div>

          {/* Column 3: Verdict Stamp & Run CTA */}
          <div className="bg-[#EDE8DA] p-3.5 rounded border border-kraft/70 flex flex-col justify-between items-center text-center">
            <div>
              <span className="text-[10px] uppercase tracking-wider text-ink-soft block font-bold mb-2">
                Computed Verdict
              </span>
              <div className="inline-block px-3 py-1 bg-ok text-cream font-mono text-xs font-bold uppercase tracking-widest rounded shadow-sm">
                REPRODUCED
              </div>
              <div className="mt-2 text-[11px] font-mono text-ink">
                Observed: <span className="font-bold text-ok">0.9556</span>
                <br />
                Claimed: 0.9560 ± 0.01
              </div>
            </div>

            <Link
              to="/new?case=b4"
              className="mt-3 w-full py-2 bg-ink hover:bg-ink-soft text-cream font-mono text-xs uppercase tracking-widest font-bold shadow-md transition-colors"
            >
              RUN THE DEMO →
            </Link>
          </div>
        </div>
      </div>

      {/* Spacer */}
      <div className="h-4 pointer-events-none" />
    </div>
  );
};

export const DemoTeaser: React.FC = () => {
  return (
    <div
      className="relative w-full h-full flex items-center justify-between px-8 md:px-14 select-none overflow-hidden"
      style={{
        background: 'var(--night-deep)',
        color: 'var(--cream)',
      }}
    >
      <div className="relative z-10 flex items-center gap-2 font-mono text-[11px] md:text-xs uppercase tracking-[0.22em] text-cream font-medium">
        <span className="text-rust">↓</span>
        <span>KEEP SCROLLING — THE FINAL SUMMIT</span>
      </div>

      <div className="relative z-10 flex items-center gap-2 font-mono text-[11px] md:text-xs uppercase tracking-[0.22em] text-cream/80">
        <span>NEXT — BENCHMARKS, LIMITS & FAQ</span>
        <span className="text-rust">→</span>
      </div>
    </div>
  );
};
