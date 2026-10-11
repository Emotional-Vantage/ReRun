import React, { useState } from 'react';
import { PineBranchSvg } from './art/PineBranchSvg';
import { SquirrelSvg } from './art/SquirrelSvg';
import { scrollToScene } from '../engine/SceneStage';

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
    stepNum: 'Step 1 of 5',
    title: 'READ THE PAPER',
    subtitle: 'Find the number the paper claims',
    role: 'RERUN',
    description:
      'We read the paper and pull out the exact result it claims \u2014 the accuracy, the error rate, whatever it reports. We also note the version of the code it used, so we test the same thing the authors did.',
    detail: 'You see every claim we found, and you confirm or correct it before anything runs.',
    caption: 'Paper claims: 0.9560 accuracy',
    imageTheme: 'linear-gradient(180deg, #4A5D80 0%, #D8A58D 60%, #E8C3A7 100%)',
  },
  {
    id: '02',
    stepNum: 'Step 2 of 5',
    title: 'RUN IT SAFELY',
    subtitle: 'In a sealed box, with no internet',
    role: 'SANDBOX',
    description:
      'The paper\u2019s code runs inside a locked container on your machine. It cannot reach the internet, cannot touch your files, and gets a fixed slice of memory and CPU.',
    detail: 'Research code is someone else\u2019s code. It never runs loose on your computer.',
    caption: 'Running in a sealed container',
    imageTheme: 'linear-gradient(180deg, #2F4F93 0%, #4A5D80 60%, #8D7765 100%)',
  },
  {
    id: '03',
    stepNum: 'Step 3 of 5',
    title: 'COMPARE THE NUMBERS',
    subtitle: 'What the code produced vs what the paper says',
    role: 'MEASURED',
    description:
      'We take the number the code actually produced and put it next to the number the paper claims. If the code crashed and produced nothing, we say so \u2014 we never fill the gap with a guess.',
    detail: 'Every number shown here was measured. Nothing is estimated or filled in.',
    caption: 'Measured 0.7812, paper says 0.9560',
    imageTheme: 'linear-gradient(180deg, #3E3B52 0%, #8D7765 60%, #B8572F 100%)',
  },
  {
    id: '04',
    stepNum: 'Step 4 of 5',
    title: 'CHECK THE FIX IS HONEST',
    subtitle: 'A second opinion before anything is applied',
    role: 'REVIEWER',
    description:
      'When Rerun suggests a fix, a separate reviewer checks it for cheating: changing the test data, fiddling with the random seed, or hiding warnings. A fix has to point at a real error or a line in the paper.',
    detail: 'You have the final say. Nothing is applied until you click approve.',
    caption: 'Checked: no test data was touched',
    imageTheme: 'linear-gradient(180deg, #8A7A9A 0%, #D8CFC4 60%, #E9B2A0 100%)',
  },
  {
    id: '05',
    stepNum: 'Step 5 of 5',
    title: 'WRITE IT ALL DOWN',
    subtitle: 'The result, and how we got there',
    role: 'REPORT',
    description:
      'You get a plain report: did it match or not, what was changed along the way, and a link from every statement back to the log line or file it came from.',
    detail: 'If we could not check something, the report says so instead of staying quiet.',
    caption: 'Result: matched the paper',
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
          How Rerun Works
        </h2>
        <div className="font-mono text-[11px] md:text-xs uppercase tracking-[0.28em] text-cream/70 mt-1.5">
          {cur.stepNum}
        </div>
      </div>

      {/* Main Content Area: Left Polaroid Stack + Right Paper Info Card */}
      <div className="relative z-10 w-full max-w-5xl flex flex-col md:flex-row items-center justify-center gap-6 md:gap-8 lg:gap-12 my-auto">
        {/* Left: Polaroid Stack */}
        <div className="relative w-[15.625rem] sm:w-[17.5rem] md:w-[18.75rem] lg:w-[20rem] h-[18.75rem] sm:h-[20.625rem] md:h-[21.875rem] lg:h-[23.75rem] flex items-center justify-center">
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
          className="w-full max-w-[30rem] bg-paper text-ink rounded-sm p-6 md:p-8 shadow-xl border border-kraft flex flex-col justify-between min-h-[21.25rem]"
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
              <span className="font-bold text-rust-ink">Good to know: </span>
              <span className="text-ink">{cur.detail}</span>
            </div>
          </div>

          {/*
            This was a styled <span> with `cursor-pointer hover:underline` and no handler:
            it looked like a link, and clicking it did nothing. It is now a real button
            that takes you to the recorded run, which is where a reader can actually see
            this step carried out on a real paper.
          */}
          <div className="mt-6 pt-3 border-t border-kraft/40 flex justify-between items-center text-xs font-mono">
            <button
              type="button"
              onClick={() => scrollToScene('demo')}
              className="text-rust-ink font-bold tracking-widest uppercase hover:underline focus:outline-none focus-visible:ring-1 focus-visible:ring-rust rounded-sm"
            >
              See this step in a real run →
            </button>
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
