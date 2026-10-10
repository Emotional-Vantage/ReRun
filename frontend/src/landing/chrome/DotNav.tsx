import React from 'react';
import { SCENES } from '../engine/config';
import { scrollToScene } from '../engine/SceneStage';
import { useScene } from '../engine/store';

export const DotNav: React.FC = () => {
  const { scene, theme } = useScene();

  const isLight = theme === 'light';
  const colorClass = isLight ? 'text-ink border-ink' : 'text-cream border-cream';

  return (
    <nav
      aria-label="Scene navigation dots"
      className="fixed right-[28px] top-1/2 -translate-y-1/2 z-[90] hidden md:flex flex-col items-center gap-[22.7px] pointer-events-auto transition-colors duration-300"
    >
      {SCENES.map((s, idx) => {
        const isActive = scene === idx;
        return (
          <button
            key={s.id}
            onClick={() => scrollToScene(s.id)}
            aria-label={`Jump to scene ${idx + 1}: ${s.nav}`}
            aria-current={isActive ? 'true' : undefined}
            className={`group relative w-[11px] h-[11px] rounded-full border transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-rust ${colorClass} ${
              isActive
                ? 'bg-current scale-110'
                : 'bg-transparent opacity-40 hover:opacity-100 hover:scale-105'
            }`}
          >
            {/* Tooltip on hover */}
            <span
              className={`absolute right-6 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-150 px-2 py-0.5 text-[10px] font-mono tracking-widest uppercase whitespace-nowrap shadow-sm border ${
                isLight
                  ? 'bg-paper text-ink border-kraft'
                  : 'bg-night-deep text-cream border-cream/20'
              }`}
            >
              {s.nav}
            </span>
          </button>
        );
      })}
    </nav>
  );
};
