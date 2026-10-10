import React, { useState } from 'react';
import { PineBranchSvg } from './art/PineBranchSvg';
import { SquirrelSvg } from './art/SquirrelSvg';

interface StepItem {
  id: string;
  stepNum: string;
  title: string;
  subtitle: string;
  role: string;
  description: string;
  detail: string;
  caption: string;
  imageTheme: string;
}

const STEPS: StepItem[] = [
  {
    id: '01',
    stepNum: '01 / 05',
    title: 'INGEST CLAIM & CODE',
    subtitle: 'Extract target metric and environment specifications',
    role: 'ORCHESTRATOR',
    description:
      'We parse the research paper, extract claimed quantitative outcomes (e.g. accuracy, perplexity, speedup), and pin the original git commit and dependencies.',
    detail: 'Spec: 5 synthetic benchmark papers labelled with exact metric formulas.',
    caption: 'Target metric: 0.9560 accuracy',
    imageTheme: 'linear-gradient(180deg, #4A5D80 0%, #D8A58D 60%, #E8C3A7 100%)',
  },
  {
    id: '02',
    stepNum: '02 / 05',
    title: 'ISOLATED DOCKER SANDBOX',
    subtitle: 'Hermetic reproducibility without host side-effects',
    role: 'SOLVER',
    description:
      'The code executes inside a restricted container with pinned python wheels and deterministic seeds. Network access is quarantined after dependency fetching.',
    detail: 'Execution engine checks every system call and records container exit codes.',
    caption: 'Container ID: rer-sandbox-b4',
    imageTheme: 'linear-gradient(180deg, #2F4F93 0%, #4A5D80 60%, #8D7765 100%)',
  },
  {
    id: '03',
    stepNum: '03 / 05',
    title: 'EXECUTION TRACE & DIFF',
    subtitle: 'Measure real numbers against the published tables',
    role: 'TOOL',
    description:
      'Rerun extracts stdout metrics, standard deviations, and resource usage. We construct a cryptographic trace of every intermediate computation.',
    detail: 'No invented numbers: measured outcomes are checked within strict tolerances.',
    caption: 'Measured: 0.7812 (claimed 0.9560)',
    imageTheme: 'linear-gradient(180deg, #3E3B52 0%, #8D7765 60%, #B8572F 100%)',
  },
  {
    id: '04',
    stepNum: '04 / 05',
    title: 'CRITIC ROLE AUDIT',
    subtitle: 'Adversarial evaluation of code integrity and hyperparams',
    role: 'CRITIC',
    description:
      'The Critic agent verifies whether the solver modified evaluation seeds, tampered with test sets, or silently suppressed runtime warnings.',
    detail: 'Clear authority hierarchy: You > Rulebook > Critic > Solver.',
    caption: 'Auditor check: No seed manipulation',
    imageTheme: 'linear-gradient(180deg, #8A7A9A 0%, #D8CFC4 60%, #E9B2A0 100%)',
  },
  {
    id: '05',
    stepNum: '05 / 05',
    title: 'VERDICT STAMP & REPORT',
    subtitle: 'Definitive reproducible proof bundle',
    role: 'RULEBOOK',
    description:
      'A signed verification report is generated with verifiable reproduction hashes, artifact logs, and an unambiguous verdict: REPRODUCED, REPRODUCED WITH TOLERANCE, or REJECTED.',
    detail: 'Exportable JSON audit trail + human-readable markdown notebook.',
    caption: 'Final Verdict: REJECTED',
    imageTheme: 'linear-gradient(180deg, #14203B 0%, #34476F 60%, #E89650 100%)',
  },
];

export const FieldNotesScene: React.FC = () => {
  const [index, setIndex] = useState(0);
  const cur = STEPS[index];

  const prev = () => setIndex((i) => (i > 0 ? i - 1 : STEPS.length - 1));
  const next = () => setIndex((i) => (i < STEPS.length - 1 ? i + 1 : 0));

  return (
    <div
      className="relative w-full h-full overflow-hidden flex flex-col justify-between items-center px-5 pt-20 pb-4 md:pt-24 md:pb-6"
      style={{
        background: 'linear-gradient(180deg, var(--night-top) 0%, var(--night-bot) 100%)',
        color: 'var(--cream)',
      }}
    >
      {/* Decorative Art in Corners */}
      {/* Pine branch on top left */}
      <div className="absolute left-0 top-0 pointer-events-none opacity-90 hidden sm:block">
        <PineBranchSvg />
      </div>

      {/* Squirrel on branch on top right */}
      <div className="absolute right-4 top-2 pointer-events-none opacity-90 hidden md:block">
        <SquirrelSvg />
      </div>

      {/* Header Zone */}
      <div className="relative z-10 text-center max-w-3xl mt-1 md:mt-2">
        <h2 className="font-serif text-2xl sm:text-3xl md:text-4xl lg:text-5xl uppercase tracking-[0.02em] text-cream">
          How It Works — Field Notes
        </h2>
        <div className="font-mono text-[11px] md:text-xs uppercase tracking-[0.28em] text-cream/70 mt-1.5">
          {cur.stepNum}
        </div>
      </div>

      {/* Main Content Area: Left Polaroid Stack + Right Paper Info Card */}
      <div className="relative z-10 w-full max-w-5xl flex flex-col md:flex-row items-center justify-center gap-6 md:gap-8 lg:gap-12 my-auto">
        {/* Left: Polaroid Stack */}
        <div className="relative w-[250px] sm:w-[280px] md:w-[300px] lg:w-[320px] h-[300px] sm:h-[330px] md:h-[350px] lg:h-[380px] flex items-center justify-center">
          {/* Underneath Polaroid (Background tilt) */}
          <div
            className="absolute inset-x-2 inset-y-2 bg-[#FAF7F0] border border-kraft/60 shadow-md p-3 pb-8 transform -rotate-6 transition-transform opacity-70"
            aria-hidden="true"
          >
            <div className="w-full h-[80%] bg-[#3E3B52]/50" />
          </div>

          {/* Active Polaroid Card */}
          <div
            key={cur.id}
            className="relative w-full h-full bg-[#FFFFFF] border border-kraft/70 shadow-2xl p-3 md:p-4 pb-8 flex flex-col justify-between transform rotate-2 transition-all duration-300"
            style={{
              boxShadow: '0 12px 30px -5px rgba(0,0,0,0.4)',
            }}
          >
            {/* Washi Tape on top edge */}
            <div
              className="absolute -top-3 left-1/2 -translate-x-1/2 w-20 h-5 washi-tape transform rotate-1 z-20"
              aria-hidden="true"
            />

            {/* Picture inside polaroid */}
            <div
              className="w-full h-[76%] rounded-sm overflow-hidden relative shadow-inner flex flex-col justify-end p-3"
              style={{ background: cur.imageTheme }}
            >
              <svg
                viewBox="0 0 200 100"
                preserveAspectRatio="none"
                className="absolute inset-0 w-full h-full"
              >
                <polygon
                  points="0,70 60,40 120,65 160,35 200,60 200,100 0,100"
                  fill="#14203B"
                  opacity="0.8"
                />
                <polygon points="20,100 28,75 36,100" fill="#0B1220" />
                <polygon points="50,100 58,70 66,100" fill="#0B1220" />
                <polygon points="90,100 98,68 106,100" fill="#0B1220" />
                <polygon points="140,100 148,72 156,100" fill="#0B1220" />
              </svg>
              <span className="relative z-10 text-[10px] font-mono text-cream/90 bg-ink/60 px-2 py-0.5 self-start">
                STEP {cur.id}
              </span>
            </div>

            {/* Handwritten Caption Below */}
            <div className="mt-2 text-center">
              <span className="font-serif italic text-sm md:text-base text-ink-blue">
                {cur.caption}
              </span>
            </div>
          </div>
        </div>

        {/* Right: Paper Info Card */}
        <div
          className="w-full max-w-[480px] bg-paper text-ink rounded-sm p-6 md:p-8 shadow-xl border border-kraft flex flex-col justify-between min-h-[340px]"
          style={{ transform: 'rotate(-0.8deg)' }}
        >
          <div>
            {/* Top row: Title + Year/Role Tag */}
            <div className="flex items-start justify-between border-b border-kraft/60 pb-3 mb-4">
              <div>
                <h3 className="font-serif text-2xl md:text-3xl text-ink uppercase tracking-wide">
                  {cur.title}
                </h3>
                <p className="text-[10px] font-mono uppercase tracking-widest text-rust-ink font-semibold mt-0.5">
                  {cur.subtitle}
                </p>
              </div>
              <span className="text-[10px] font-mono uppercase px-2 py-1 bg-kraft-light text-ink border border-kraft font-semibold">
                {cur.role}
              </span>
            </div>

            {/* Body Description */}
            <p className="font-mono text-xs md:text-sm text-ink-soft leading-relaxed">
              {cur.description}
            </p>

            {/* Detail Spec */}
            <div className="mt-4 p-2.5 bg-[#EDE8DA] border border-kraft/70 text-[11px] font-mono text-ink">
              <span className="font-bold text-rust-ink">Note: </span>
              <span className="text-ink">{cur.detail}</span>
            </div>
          </div>

          {/* Action Link */}
          <div className="mt-6 pt-3 border-t border-kraft/40 flex justify-between items-center text-xs font-mono">
            <span className="text-rust-ink font-bold tracking-widest uppercase hover:underline cursor-pointer">
              INSPECT STEP ARTIFACT →
            </span>
            <span className="text-ink-soft text-[10px]">{cur.stepNum}</span>
          </div>
        </div>
      </div>

      {/* Carousel Controls Bottom Strip */}
      <div className="relative z-10 flex items-center gap-6 mt-4">
        {/* Previous Button */}
        <button
          onClick={prev}
          aria-label="Previous step"
          className="w-9 h-9 rounded-full border border-cream/40 flex items-center justify-center text-cream hover:bg-cream hover:text-ink active:scale-95 transition-all focus:outline-none focus:ring-1 focus:ring-rust"
        >
          ←
        </button>

        {/* Dashed Progress Indicators */}
        <div className="flex items-center gap-2">
          {STEPS.map((s, idx) => (
            <button
              key={s.id}
              onClick={() => setIndex(idx)}
              aria-label={`Go to step ${idx + 1}`}
              className={`h-[3px] transition-all duration-200 ${
                index === idx ? 'w-8 bg-rust' : 'w-4 bg-cream/40 hover:bg-cream/70'
              }`}
            />
          ))}
        </div>

        {/* Next Button */}
        <button
          onClick={next}
          aria-label="Next step"
          className="w-9 h-9 rounded-full border border-cream/40 flex items-center justify-center text-cream hover:bg-cream hover:text-ink active:scale-95 transition-all focus:outline-none focus:ring-1 focus:ring-rust"
        >
          →
        </button>
      </div>
    </div>
  );
};

export const FieldNotesTeaser: React.FC = () => {
  return (
    <div
      className="relative w-full h-full flex items-center justify-between px-8 md:px-14 select-none overflow-hidden"
      style={{
        background: 'var(--rose-paper)',
        color: 'var(--ink)',
      }}
    >
      <div className="relative z-10 flex items-center gap-2 font-mono text-[11px] md:text-xs uppercase tracking-[0.22em] text-ink font-medium">
        <span className="text-rust">↓</span>
        <span>KEEP SCROLLING — THE CREW AHEAD</span>
      </div>

      <div className="relative z-10 flex items-center gap-2 font-mono text-[11px] md:text-xs uppercase tracking-[0.22em] text-ink-soft">
        <span>NEXT — MEET THE ROLES · FOUR AGENTS</span>
        <span className="text-rust">→</span>
      </div>
    </div>
  );
};
