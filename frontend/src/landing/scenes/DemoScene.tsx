import React, { useState } from 'react';
import { Link } from 'react-router-dom';

/**
 * One recorded run of case B4, told as five steps.
 *
 * Every panel below is driven off the selected step. The trail used to be clickable while
 * the three panels underneath stayed fixed on the final state, so picking step 1 still
 * showed the finished verdict and the story could not actually be read.
 */

type Tone = 'tool' | 'fail' | 'solver' | 'human' | 'ok';

interface TraceLine {
  n: number;
  who: string;
  text: string;
  tone: Tone;
}

const TRACE: TraceLine[] = [
  { n: 1, who: 'sandbox', text: "Started the container and ran the code", tone: 'tool' },
  { n: 2, who: 'sandbox', text: "Stopped with an error: no module named 'yaml'", tone: 'fail' },
  { n: 3, who: 'solver', text: 'Suggested a fix: add the missing package', tone: 'solver' },
  { n: 4, who: 'you', text: 'You read the fix and approved it', tone: 'human' },
  { n: 5, who: 'rerun', text: 'Ran again and matched the paper', tone: 'ok' },
];

const TONE_CLASS: Record<Tone, string> = {
  tool: 'text-tool',
  fail: 'text-fail',
  solver: 'text-solver',
  human: 'text-human',
  ok: 'text-ok',
};

const TONE_DOT: Record<Tone, string> = {
  tool: 'bg-tool',
  fail: 'bg-fail',
  solver: 'bg-solver',
  human: 'bg-human',
  ok: 'bg-ok',
};

interface Step {
  id: number;
  title: string;
  tag: string;
  /** Plain-language summary, shown under the trail. */
  summary: string;
  /** How many trace lines had happened by the end of this step. */
  traceThrough: number;
  detail: {
    heading: string;
    body: React.ReactNode;
  };
  verdict: {
    label: string;
    /** Tailwind classes for the verdict pill. */
    pill: string;
    lines: React.ReactNode;
  };
}

const STEPS: Step[] = [
  {
    id: 1,
    title: 'The code would not run',
    tag: 'Run 1 · error',
    summary:
      'We ran the paper’s own code, unchanged. It stopped within seconds because a package it needs was never listed.',
    traceThrough: 2,
    detail: {
      heading: 'What the container printed',
      body: (
        <div className="space-y-1.5">
          <div className="text-ink-soft text-[10px]">last lines of run 1</div>
          <div className="bg-[#FEE2E2] text-fail px-2 py-1 rounded border border-fail/20">
            ModuleNotFoundError: No module named 'yaml'
          </div>
          <p className="text-[11px] text-ink-soft leading-relaxed pt-1">
            Nothing was measured, so there is no number to compare yet.
          </p>
        </div>
      ),
    },
    verdict: {
      label: 'NO RESULT YET',
      pill: 'bg-fail text-cream',
      lines: (
        <>
          Exit code: <span className="font-bold text-fail">1</span>
          <br />
          Measured: <span className="font-bold">nothing</span>
        </>
      ),
    },
  },
  {
    id: 2,
    title: 'You approved the first fix',
    tag: 'Patch 1 · your call',
    summary:
      'Rerun worked out which package was missing and wrote the smallest possible fix. Nothing was applied until you said yes.',
    traceThrough: 4,
    detail: {
      heading: 'The change you approved',
      body: (
        <div className="space-y-1.5">
          <div className="text-ink-soft text-[10px]">requirements.txt</div>
          <div className="bg-[#DCFCE7] text-ok px-2 py-1 rounded border border-ok/20 font-semibold">
            + PyYAML==6.0.1
          </div>
          <p className="text-[11px] text-ink-soft leading-relaxed pt-1">
            One line. The reason given was the error above, not a guess about what might
            raise the score.
          </p>
        </div>
      ),
    },
    verdict: {
      label: 'FIX APPROVED',
      pill: 'bg-human text-ink',
      lines: (
        <>
          Changed: <span className="font-bold">1 line</span>
          <br />
          Approved by: <span className="font-bold">you</span>
        </>
      ),
    },
  },
  {
    id: 3,
    title: 'It ran, but the number was wrong',
    tag: 'Run 2 · wrong number',
    summary:
      'This is the failure that is easy to miss. The code finished with no error at all — but the accuracy it produced was well below what the paper claims.',
    traceThrough: 4,
    detail: {
      heading: 'Measured against the paper',
      body: (
        <div className="space-y-1.5">
          <div className="flex justify-between">
            <span className="text-ink-soft">Paper says</span>
            <span className="font-bold">0.9560</span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-soft">We measured</span>
            <span className="font-bold text-fail">0.8733</span>
          </div>
          <p className="text-[11px] text-ink-soft leading-relaxed pt-1">
            No error message, nothing in the log to debug. Most tools stop here.
          </p>
        </div>
      ),
    },
    verdict: {
      label: 'DOES NOT MATCH',
      pill: 'bg-fail text-cream',
      lines: (
        <>
          Exit code: <span className="font-bold text-ok">0</span>
          <br />
          Off by: <span className="font-bold text-fail">0.0827</span>
        </>
      ),
    },
  },
  {
    id: 4,
    title: 'A setting did not match the paper',
    tag: 'Patch 2 · backed by a quote',
    summary:
      'Rerun compared the settings in the code against the text of the paper and found one that disagreed. The fix has to quote the paper — it is not allowed to just try numbers until the score improves.',
    traceThrough: 4,
    detail: {
      heading: 'The setting that disagreed',
      body: (
        <div className="space-y-1.5">
          <div className="text-ink-soft text-[10px]">configs/default.yaml</div>
          <div className="bg-[#FEE2E2] text-fail px-2 py-0.5 rounded border border-fail/20">
            - learning_rate: 0.01
          </div>
          <div className="bg-[#DCFCE7] text-ok px-2 py-0.5 rounded border border-ok/20 font-semibold">
            + learning_rate: 0.5
          </div>
          <div className="text-[10px] text-ink-soft italic pt-1">
            Paper, page 1: &ldquo;learning rate was fixed to 0.5&rdquo;
          </div>
        </div>
      ),
    },
    verdict: {
      label: 'FIX APPROVED',
      pill: 'bg-human text-ink',
      lines: (
        <>
          Changed: <span className="font-bold">1 setting</span>
          <br />
          Evidence: <span className="font-bold">paper, p.1</span>
        </>
      ),
    },
  },
  {
    id: 5,
    title: 'It matched',
    tag: 'Run 3 · reproduced',
    summary:
      'The third run landed inside the margin the paper allows. Three runs, two fixes, and every step on the record.',
    traceThrough: 5,
    detail: {
      heading: 'Measured against the paper',
      body: (
        <div className="space-y-1.5">
          <div className="flex justify-between">
            <span className="text-ink-soft">Paper says</span>
            <span className="font-bold">0.9560</span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-soft">We measured</span>
            <span className="font-bold text-ok">0.9556</span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-soft">Allowed margin</span>
            <span className="font-bold">&plusmn; 0.01</span>
          </div>
          <p className="text-[11px] text-ink-soft leading-relaxed pt-1">
            Inside the margin, so this counts as reproduced.
          </p>
        </div>
      ),
    },
    verdict: {
      label: 'REPRODUCED',
      pill: 'bg-ok text-cream',
      lines: (
        <>
          Measured: <span className="font-bold text-ok">0.9556</span>
          <br />
          Paper: 0.9560 &plusmn; 0.01
        </>
      ),
    },
  },
];

export const DemoScene: React.FC = () => {
  const [activeStep, setActiveStep] = useState(4);
  const step = STEPS[activeStep];

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
          No. 06 · One real run, start to finish
        </div>
        <h2 className="font-serif text-3xl md:text-5xl uppercase tracking-[0.02em] text-ink leading-tight">
          How a run actually goes
        </h2>
        <p className="mt-1 text-xs md:text-sm font-mono text-ink-soft">
          Three tries and two fixes before the number matched. Pick a step to see what
          happened.
        </p>
      </div>

      {/* Clickable step trail */}
      <div className="relative z-10 w-full max-w-4xl py-3 px-4">
        <div className="relative w-full h-10 flex items-center justify-between">
          <div className="absolute inset-x-8 top-1/2 -translate-y-1/2 h-[2px] border-b-2 border-dashed border-rust" />

          {STEPS.map((st, i) => {
            const isActive = activeStep === i;
            const isDone = i < activeStep;
            return (
              <button
                key={st.id}
                type="button"
                onClick={() => setActiveStep(i)}
                aria-pressed={isActive}
                aria-label={`Step ${st.id}: ${st.title}`}
                className={`group relative z-10 flex flex-col items-center focus:outline-none focus-visible:ring-2 focus-visible:ring-rust rounded-full transition-all ${
                  isActive ? 'scale-110' : 'opacity-70 hover:opacity-100'
                }`}
              >
                <div
                  className={`w-7 h-7 rounded-full border-2 flex items-center justify-center font-mono text-[10px] font-bold shadow-md transition-colors ${
                    isActive
                      ? 'bg-rust text-cream border-cream'
                      : isDone
                      ? 'bg-ink text-cream border-kraft'
                      : 'bg-paper text-ink border-kraft group-hover:border-rust'
                  }`}
                >
                  {st.id}
                </div>
                <span
                  className={`absolute -bottom-5 whitespace-nowrap text-[9px] font-mono tracking-widest uppercase font-semibold transition-colors ${
                    isActive ? 'text-rust' : 'text-ink-soft'
                  }`}
                >
                  {st.tag}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Paper Field-Log Card — all three panels follow the selected step */}
      <div
        className="relative z-20 w-full max-w-4xl bg-paper text-ink p-5 md:p-6 rounded-sm shadow-2xl border border-kraft my-auto"
        style={{ transform: 'rotate(0.8deg)' }}
      >
        <div className="absolute -top-3 left-8 washi-tape-amber px-3 py-0.5 rounded text-[10px] font-mono text-ink font-bold uppercase tracking-wider shadow-sm transform -rotate-1">
          A real run we recorded
        </div>

        {/* Plain-language headline for the selected step */}
        <div className="pt-3 pb-4 border-b border-kraft/60">
          <h3 className="font-serif text-xl md:text-2xl text-ink-blue">
            Step {step.id} of {STEPS.length} — {step.title}
          </h3>
          <p className="font-mono text-[11px] md:text-xs text-ink-soft leading-relaxed mt-1 max-w-3xl">
            {step.summary}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-4">
          {/* Column 1: what had happened by this step */}
          <div className="bg-[#EDE8DA] p-3.5 rounded border border-kraft/70 font-mono text-xs space-y-2">
            <span className="text-[10px] uppercase tracking-wider text-ink-soft block font-bold">
              What happened so far
            </span>
            <div className="space-y-1.5 text-[11px]">
              {TRACE.map((line) => {
                const reached = line.n <= step.traceThrough;
                return (
                  <div
                    key={line.n}
                    className={`flex items-start gap-1.5 transition-opacity ${
                      reached ? TONE_CLASS[line.tone] : 'text-ink-soft opacity-35'
                    } ${reached && line.n === step.traceThrough ? 'font-bold' : ''}`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${
                        reached ? TONE_DOT[line.tone] : 'bg-ink-soft'
                      }`}
                    />
                    <span>
                      <span className="opacity-70">[{line.who}]</span> {line.text}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Column 2: the detail for this step */}
          <div className="bg-[#EDE8DA] p-3.5 rounded border border-kraft/70 font-mono text-xs space-y-2">
            <span className="text-[10px] uppercase tracking-wider text-ink-soft block font-bold">
              {step.detail.heading}
            </span>
            <div className="text-[11px]">{step.detail.body}</div>
          </div>

          {/* Column 3: where the run stood after this step */}
          <div className="bg-[#EDE8DA] p-3.5 rounded border border-kraft/70 flex flex-col justify-between items-center text-center">
            <div>
              <span className="text-[10px] uppercase tracking-wider text-ink-soft block font-bold mb-2">
                Where it stood
              </span>
              <div
                className={`inline-block px-3 py-1 font-mono text-xs font-bold uppercase tracking-widest rounded shadow-sm ${step.verdict.pill}`}
              >
                {step.verdict.label}
              </div>
              <div className="mt-2 text-[11px] font-mono text-ink leading-relaxed">
                {step.verdict.lines}
              </div>
            </div>

            <Link
              to="/new?case=b4"
              className="mt-3 w-full py-2 bg-ink hover:bg-ink-soft text-cream font-mono text-xs uppercase tracking-widest font-bold shadow-md transition-colors"
            >
              Try this run yourself →
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
        <span>NEXT — THE FIVE TEST CASES & FAQ</span>
        <span className="text-rust">→</span>
      </div>
    </div>
  );
};
