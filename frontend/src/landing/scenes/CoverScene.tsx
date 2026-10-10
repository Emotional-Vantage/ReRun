import React from 'react';
import { MountainRidgesSvg } from './art/MountainRidgesSvg';
import { EagleSvg } from './art/EagleSvg';
import { scrollToScene } from '../engine/SceneStage';

export const CoverScene: React.FC = () => {
  return (
    <div
      className="relative w-full h-full overflow-hidden flex flex-col justify-between"
      style={{
        background:
          'linear-gradient(180deg, var(--dusk-top) 0%, var(--dusk-mid) 48%, var(--dusk-low) 100%)',
        color: 'var(--cream)',
      }}
    >
      {/* 30 Stars with soft organic twinkling */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden="true">
        <style>{`
          @keyframes starTwinkle {
            0%, 100% {
              opacity: 0.35;
              transform: scale(0.9);
            }
            50% {
              opacity: 0.95;
              transform: scale(1.3);
            }
          }
          @keyframes tagFlutter {
            0%, 100% {
              transform: rotate(2.5deg) translate3d(0, 0, 0);
            }
            35% {
              transform: rotate(1.2deg) translate3d(2px, -3px, 0);
            }
            70% {
              transform: rotate(3.6deg) translate3d(-1px, 2px, 0);
            }
          }
          @media (prefers-reduced-motion: reduce) {
            .star-twinkle, .tag-flutter {
              animation: none !important;
            }
          }
        `}</style>
        {[
          [120, 80, 0.6], [240, 140, 0.4], [380, 70, 0.7], [520, 180, 0.3], [660, 95, 0.8],
          [780, 150, 0.5], [920, 65, 0.7], [1050, 130, 0.4], [1180, 85, 0.9], [1320, 175, 0.3],
          [1460, 105, 0.6], [1600, 160, 0.5], [1740, 75, 0.8], [1860, 120, 0.4],
          [180, 220, 0.5], [310, 280, 0.3], [490, 230, 0.6], [710, 260, 0.4], [890, 210, 0.7],
          [1100, 250, 0.5], [1280, 220, 0.8], [1490, 270, 0.4], [1680, 230, 0.6], [1820, 260, 0.3],
          [90, 310, 0.4], [420, 340, 0.5], [830, 320, 0.3], [1220, 330, 0.6], [1590, 310, 0.5], [1770, 350, 0.4]
        ].map(([cx, cy, op], i) => (
          <circle
            key={i}
            cx={cx}
            cy={cy}
            r="1.4"
            fill="#F1ECE0"
            opacity={op}
            className="star-twinkle"
            style={{
              animation: `starTwinkle ${(i % 3) + 3}s ease-in-out ${(i * 0.4) % 3.5}s infinite`,
              transformOrigin: `${cx}px ${cy}px`,
            }}
          />
        ))}
      </svg>

      {/* Mountain Ridges inline art (pinned to bottom of upper sheet) */}
      <div className="absolute inset-x-0 bottom-0 h-[62%] pointer-events-none">
        <MountainRidgesSvg />
      </div>

      {/* Gliding Eagle (top right) */}
      <div className="absolute right-[8%] xl:right-[12%] top-[11%] md:top-[13%] hidden md:block pointer-events-none">
        <EagleSvg />
      </div>

      {/* Floating Torn Tag (right side, tilted) */}
      <div
        className="absolute right-[3%] sm:right-[5%] xl:right-[8%] top-[32%] md:top-[30%] z-20 pointer-events-auto select-none hidden sm:block tag-flutter"
        style={{
          animation: 'tagFlutter 6.5s ease-in-out infinite',
          transformOrigin: 'top right',
        }}
      >
        <div
          className="relative px-4 py-3 md:px-5 md:py-4 shadow-lg text-center border border-kraft/60"
          style={{
            background: 'var(--paper)',
            color: 'var(--ink)',
            clipPath:
              'polygon(0% 4px, 3px 0%, calc(100% - 4px) 0%, 100% 3px, 99% calc(100% - 3px), calc(100% - 3px) 100%, 3px 99%, 0% calc(100% - 4px))',
          }}
        >
          <div className="font-serif italic text-sm md:text-base lg:text-lg text-ink-blue leading-tight">
            5 cases to retrace
          </div>
          <div className="font-serif italic text-xs md:text-sm text-ink-blue/80">
            from the benchmark set
          </div>
          <div className="mt-1.5 md:mt-2 text-[8px] md:text-[9px] font-mono tracking-[0.22em] uppercase text-rust-ink font-semibold">
            VERIFIED CODE TRACE
          </div>
        </div>
      </div>

      {/* Center Content Zone */}
      <div className="relative z-10 w-full max-w-5xl mx-auto px-5 sm:px-6 pt-20 md:pt-24 text-center flex flex-col items-center">
        {/* Eyebrow */}
        <div className="flex items-center gap-3 text-[10px] md:text-xs font-mono uppercase tracking-[0.25em] md:tracking-[0.28em] text-cream/75 mb-3 md:mb-4">
          <span className="w-5 md:w-6 h-[1px] bg-cream/40" />
          <span>AUTONOMOUS SCIENTIFIC VERIFICATION</span>
          <span className="w-5 md:w-6 h-[1px] bg-cream/40" />
        </div>

        {/* Headline: Guaranteed 2-Line Regular Weight Uppercase Libre Caslon */}
        <h1
          className="font-serif font-normal uppercase tracking-[0.02em] text-cream leading-[1.05] text-center max-w-4xl"
          style={{ fontSize: 'clamp(28px, 4.3vw, 70px)' }}
        >
          <span>Does the code</span>
          <br />
          <span className="whitespace-nowrap">reproduce the number?</span>
        </h1>

        {/* Sub-paragraph with soft contrast scrim */}
        <div
          className="mt-6 px-6 py-2 rounded-sm text-center max-w-[54ch]"
          style={{
            background: 'linear-gradient(rgba(58,63,92,.45), rgba(58,63,92,0))',
          }}
        >
          <p className="font-mono text-xs md:text-sm tracking-wider text-cream/90 leading-relaxed">
            Autonomous multi-agent verification in isolated containers. Retrace papers step by step,
            compare claimed numbers to actual run outputs, and inspect cryptographic execution
            traces.
          </p>
        </div>

        {/* Buttons Row */}
        <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
          {/* Primary Button: Torn Paper Cream with Ink Text */}
          <button
            onClick={() => scrollToScene('demo')}
            className="px-6 py-3 font-mono text-xs md:text-sm uppercase tracking-[0.2em] font-semibold text-ink bg-cream hover:bg-paper active:scale-95 transition-all shadow-md"
            style={{
              clipPath:
                'polygon(0% 3px, 2px 0%, calc(100% - 3px) 0%, 100% 2px, 99% calc(100% - 2px), calc(100% - 2px) 100%, 2px 99%, 0% calc(100% - 3px))',
            }}
          >
            Try the Demo (Case B4)
          </button>

          {/* Secondary Button: Outlined Cream */}
          <button
            onClick={() => scrollToScene('how-it-works')}
            className="px-6 py-3 font-mono text-xs md:text-sm uppercase tracking-[0.2em] text-cream border border-cream/40 hover:border-cream hover:bg-cream/10 active:scale-95 transition-all"
          >
            See How It Works
          </button>
        </div>
      </div>

      {/* Spacer to preserve balance */}
      <div className="h-10 pointer-events-none" />
    </div>
  );
};

export const CoverTeaser: React.FC = () => {
  return (
    <div
      className="relative w-full h-full flex items-center justify-between px-8 md:px-14 select-none overflow-hidden"
      style={{
        background: 'var(--kraft-light)',
        color: 'var(--ink)',
      }}
    >
      {/* Pine Tree Silhouettes in background */}
      <svg
        viewBox="0 0 1200 120"
        preserveAspectRatio="none"
        className="absolute inset-x-0 bottom-0 w-full h-full pointer-events-none opacity-30"
        aria-hidden="true"
      >
        <g fill="var(--kraft-tree)">
          {/* Pine trees along the band */}
          <polygon points="120,120 150,40 180,120" />
          <polygon points="160,120 190,50 220,120" />
          <polygon points="200,120 230,30 260,120" />
          <polygon points="280,120 310,60 340,120" />
          <polygon points="850,120 880,35 910,120" />
          <polygon points="900,120 930,55 960,120" />
          <polygon points="980,120 1010,25 1040,120" />
          <polygon points="1020,120 1050,45 1080,120" />
        </g>
      </svg>

      {/* Left Teaser Text */}
      <div className="relative z-10 flex items-center gap-2 font-mono text-[11px] md:text-xs uppercase tracking-[0.22em] text-ink font-medium">
        <span className="text-rust">↓</span>
        <span>KEEP SCROLLING — THE PAGE TEARS OPEN</span>
      </div>

      {/* Right Teaser Text */}
      <div className="relative z-10 hidden sm:flex items-center gap-2 font-mono text-[10px] md:text-[11px] uppercase tracking-[0.22em] text-ink-soft">
        <span>ISOLATED SANDBOX · HUMAN APPROVAL · VERDICT BY CODE</span>
      </div>
    </div>
  );
};
