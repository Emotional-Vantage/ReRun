import React, { useState } from 'react';
import { PenSketchPeakSvg } from './art/PenSketchPeakSvg';
import { PineBranchSvg } from './art/PineBranchSvg';

export const ProblemScene: React.FC = () => {
  const [flipped, setFlipped] = useState(false);

  return (
    <div
      className="relative w-full h-full overflow-hidden flex flex-col justify-center items-center px-4 pt-16 md:pt-20"
      style={{
        background: 'var(--kraft-light)',
        color: 'var(--ink)',
      }}
    >
      {/* Pen Sketch Peak behind the postcard */}
      <div className="absolute right-[5%] top-[10%] w-[480px] h-[380px] opacity-25 pointer-events-none hidden lg:block text-ink">
        <PenSketchPeakSvg />
      </div>

      {/* Floating Envelope with Letter & Wax Seal (Top Right) */}
      <style>{`
        @keyframes envelopeDrift {
          0%, 100% {
            transform: rotate(6deg) translate3d(0, 0, 0);
          }
          40% {
            transform: rotate(4deg) translate3d(2px, -5px, 0);
          }
          75% {
            transform: rotate(7.5deg) translate3d(-2px, 3px, 0);
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .envelope-drift {
            animation: none !important;
          }
        }
      `}</style>
      <div
        className="absolute right-[8%] top-[8%] z-10 hidden sm:block pointer-events-none select-none envelope-drift"
        style={{
          animation: 'envelopeDrift 7.2s ease-in-out infinite',
          transformOrigin: 'center center',
        }}
      >
        <div className="relative w-32 h-20 bg-[#E8E2D2] border border-kraft shadow-md flex items-center justify-center">
          {/* Letter peeking out */}
          <div className="absolute -top-4 w-24 h-12 bg-paper border border-kraft shadow-sm px-2 py-1 text-[7px] font-mono text-ink-soft">
            ---
            <div className="w-16 h-1 bg-ink/10 my-0.5" />
            <div className="w-12 h-1 bg-ink/10" />
          </div>
          {/* Blue Airmail stamp */}
          <div className="absolute bottom-2 right-2 w-5 h-4 bg-ink-blue/20 border border-ink-blue/40" />
          {/* Envelope fold flap */}
          <svg className="absolute inset-0 w-full h-full stroke-kraft fill-none" strokeWidth="1">
            <line x1="0" y1="0" x2="64" y2="40" />
            <line x1="128" y1="0" x2="64" y2="40" />
          </svg>
        </div>
      </div>

      {/* 3D Flip Postcard Container */}
      <div
        className="relative z-20 w-full max-w-[840px] h-[440px] sm:h-[470px] lg:h-[500px] perspective-1000 select-none"
        style={{
          transform: 'rotate(-1.2deg)',
        }}
      >
        <div
          className={`relative w-full h-full duration-700 transition-transform transform-style-3d shadow-2xl ${
            flipped ? 'rotate-y-180' : ''
          }`}
          style={{
            transformStyle: 'preserve-3d',
            transition: 'transform 0.7s cubic-bezier(0.4, 0.2, 0.2, 1)',
            transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
          }}
        >
          {/* ================= FRONT: IT CRASHES ================= */}
          <div
            className="absolute inset-0 w-full h-full bg-paper border border-kraft rounded-sm p-5 sm:p-6 md:p-7 flex flex-col md:flex-row gap-5 md:gap-6 backface-hidden shadow-xl"
            style={{ backfaceVisibility: 'hidden' }}
          >
            {/* Left Column: Framed Scenic Painting + Taped Polaroid */}
            <div className="relative w-full md:w-[44%] h-full flex flex-col justify-between">
              {/* Main picture frame */}
              <div className="relative w-full h-[78%] bg-frame-navy p-2 shadow-inner border border-ink/20">
                {/* Washi tape on top-left corner */}
                <div
                  className="absolute -top-3 -left-3 w-16 h-6 washi-tape z-30 transform -rotate-12"
                  aria-hidden="true"
                />
                {/* Mountain sunrise scene inside frame */}
                <div
                  className="w-full h-full overflow-hidden relative"
                  style={{
                    background: 'linear-gradient(180deg, #5A6987 0%, #D8A58D 60%, #E8C3A7 100%)',
                  }}
                >
                  {/* Distant mountain silhouettes */}
                  <svg viewBox="0 0 300 200" preserveAspectRatio="none" className="w-full h-full">
                    <polygon
                      points="0,140 80,90 160,130 220,70 300,120 300,200 0,200"
                      fill="#3E3B52"
                    />
                    <polygon
                      points="0,160 100,120 180,150 240,110 300,140 300,200 0,200"
                      fill="#14203B"
                    />
                    {/* Pine silhouettes */}
                    <g fill="#0B1220">
                      <polygon points="40,200 50,165 60,200" />
                      <polygon points="70,200 80,155 90,200" />
                      <polygon points="120,200 130,160 140,200" />
                      <polygon points="180,200 190,150 200,200" />
                    </g>
                  </svg>
                </div>
              </div>

              {/* Smaller overlapping polaroid with washi tape */}
              <div
                className="absolute -bottom-2 -left-2 w-[165px] bg-[#FFFFFF] p-2 pb-3 shadow-lg border border-kraft z-20"
                style={{ transform: 'rotate(4deg)' }}
              >
                {/* Tape */}
                <div className="absolute -top-2 left-6 w-12 h-4 washi-tape transform rotate-3" />
                <div className="w-full h-20 bg-[#4A5D80]/80 overflow-hidden flex items-center justify-center text-cream text-[10px] font-mono">
                  trace_log.py
                </div>
                <div className="mt-1 text-[9px] font-mono text-ink text-center">
                  docker build: exit 1
                </div>
              </div>
            </div>

            {/* Vertical divider with "PAR AVION · BY AIR MAIL" */}
            <div className="hidden md:flex flex-col items-center justify-between py-2 border-r border-kraft/60 pr-3">
              <span
                className="font-mono text-[9px] tracking-[0.3em] uppercase text-ink-soft select-none"
                style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
              >
                PAR AVION · BY AIR MAIL
              </span>
            </div>

            {/* Right Column: Postcard Writing Area */}
            <div className="flex-1 flex flex-col justify-between pl-0 md:pl-2">
              <div>
                {/* Top Row: Header & Postage Stamp */}
                <div className="flex justify-between items-start">
                  <div>
                    <h2 className="font-serif text-2xl md:text-3xl text-ink-blue uppercase tracking-wider leading-none">
                      Postcard
                    </h2>
                    <p className="text-[10px] font-mono uppercase tracking-widest text-ink-soft mt-1">
                      No. 02 · The Reproducibility Gap
                    </p>
                  </div>

                  {/* Stamp & Postmark */}
                  <div className="relative">
                    <div className="postage-stamp w-14 h-16 bg-[#EBE5D6] p-1 flex flex-col items-center justify-between text-center">
                      <div className="text-[7px] font-mono text-rust font-bold">RERUN</div>
                      <svg viewBox="0 0 20 14" className="w-7 h-5 stroke-rust fill-none">
                        <path d="M2 12 L7 4 L12 9 L15 6 L18 12 Z" />
                      </svg>
                      <div className="text-[6px] font-mono text-ink-soft">2026</div>
                    </div>
                    {/* Postmark cancellation rings */}
                    <div className="absolute -left-4 top-2 w-12 h-12 border border-ink/40 rounded-full pointer-events-none flex items-center justify-center">
                      <span className="text-[6px] font-mono text-ink/60 transform -rotate-12">
                        VERIFIED
                      </span>
                    </div>
                  </div>
                </div>

                {/* Postcard Ruled Lines Zone */}
                <div className="mt-4 postcard-lines">
                  <h3 className="font-serif text-xl md:text-2xl text-rust-ink uppercase tracking-wide">
                    It crashes.
                  </h3>

                  {/* Real error snippet box */}
                  <div className="my-2 p-2 bg-[#F3EDE2] border-l-2 border-fail font-mono text-[11px] text-ink leading-tight">
                    <code>ModuleNotFoundError: No module named 'yaml'</code>
                  </div>

                  <p className="font-serif italic text-sm md:text-base text-ink-blue leading-[28px] mt-1">
                    You can see the problem. Fixing it is slow. Researchers lose days on this loop. A
                    chatbot can't help, because it can't run the code and check the result.
                  </p>
                </div>
              </div>

              {/* Bottom Row: Signature & Flip Button */}
              <div className="flex justify-between items-center pt-2 border-t border-kraft/40">
                <span className="font-serif italic text-sm text-ink-blue">
                  — The Evaluation Team
                </span>

                <button
                  type="button"
                  onClick={() => setFlipped(true)}
                  className="px-3 py-1.5 font-mono text-xs uppercase tracking-widest text-rust-ink font-semibold hover:text-rust transition-colors flex items-center gap-1 focus:outline-none focus:ring-1 focus:ring-rust"
                >
                  TURN OVER ↻
                </button>
              </div>
            </div>
          </div>

          {/* ================= BACK: IT RUNS. THE NUMBER IS WRONG ================= */}
          <div
            className="absolute inset-0 w-full h-full bg-[#FAF7F0] border border-kraft rounded-sm p-6 md:p-8 flex flex-col justify-between backface-hidden shadow-xl"
            style={{
              backfaceVisibility: 'hidden',
              transform: 'rotateY(180deg)',
            }}
          >
            <div>
              {/* Back Header */}
              <div className="flex justify-between items-start border-b border-kraft/60 pb-3">
                <div>
                  <h2 className="font-serif text-2xl md:text-3xl text-ink uppercase tracking-wide leading-none">
                    It runs. The number is wrong.
                  </h2>
                  <p className="text-[10px] font-mono uppercase tracking-widest text-rust-ink mt-1 font-semibold">
                    The silent failure: clean exit code 0, incorrect metric
                  </p>
                </div>

                {/* Stamp */}
                <div className="postage-stamp w-12 h-14 bg-[#EBE5D6] p-1 flex flex-col items-center justify-center">
                  <span className="text-[7px] font-mono text-ink font-bold">CASE B4</span>
                </div>
              </div>

              {/* Back Content */}
              <div className="mt-4 postcard-lines">
                <div className="p-3 bg-paper border border-kraft font-mono text-xs my-2">
                  <div className="flex justify-between text-ink-soft text-[11px] mb-1">
                    <span>METRIC COMPARISON</span>
                    <span>STATUS: REJECTED</span>
                  </div>
                  <div className="flex justify-between font-bold">
                    <span className="text-fail">ACTUAL: 0.7812 (far below the claim)</span>
                    <span className="text-ink-soft">CLAIMED: 0.9560</span>
                  </div>
                </div>

                <p className="font-serif italic text-sm md:text-base text-ink-blue leading-[28px] mt-2">
                  No error, nothing to debug. Most tools stop here. Rerun starts here.
                </p>
                <p className="font-mono text-xs text-ink-soft mt-3 leading-relaxed">
                  P.S. We execute the code in isolated Docker environments, re-evaluate every
                  formula, and report the real ground truth.
                </p>
              </div>
            </div>

            {/* Bottom Row: Return button */}
            <div className="flex justify-between items-center pt-2 border-t border-kraft/40">
              <span className="font-mono text-[10px] uppercase tracking-widest text-ink-soft">
                BENCHMARK EVALUATION LOG
              </span>

              <button
                type="button"
                onClick={() => setFlipped(false)}
                className="px-3 py-1.5 font-mono text-xs uppercase tracking-widest text-rust-ink font-semibold hover:text-rust transition-colors flex items-center gap-1 focus:outline-none focus:ring-1 focus:ring-rust"
              >
                TURN OVER ↺
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export const ProblemTeaser: React.FC = () => {
  return (
    <div
      className="relative w-full h-full flex items-center justify-between px-8 md:px-14 select-none overflow-hidden"
      style={{
        background: 'linear-gradient(180deg, var(--night-top) 0%, var(--night-bot) 100%)',
        color: 'var(--cream)',
      }}
    >
      {/* Pine branch on the left */}
      <div className="absolute left-[-10px] bottom-[-20px] pointer-events-none opacity-80">
        <PineBranchSvg />
      </div>

      {/* Left Teaser Text */}
      <div className="relative z-10 pl-24 hidden sm:flex items-center gap-2 font-mono text-[11px] md:text-xs uppercase tracking-[0.22em] text-cream/80">
        <span>↓ KEEP SCROLLING — UNROLL FIELD NOTES</span>
      </div>

      {/* Right Teaser Text */}
      <div className="relative z-10 flex items-center gap-2 font-mono text-[11px] md:text-xs uppercase tracking-[0.22em] text-cream font-medium">
        <span>NEXT — HOW IT WORKS — FIELD NOTES</span>
        <span className="text-rust">→</span>
      </div>
    </div>
  );
};
