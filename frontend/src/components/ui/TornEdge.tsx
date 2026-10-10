import React from 'react';

interface TornEdgeProps {
  direction?: 'paper-to-night' | 'night-to-paper';
  caption?: string;
  subcaption?: string;
  className?: string;
}

export const TornEdge: React.FC<TornEdgeProps> = ({
  direction = 'paper-to-night',
  caption,
  subcaption,
  className = '',
}) => {
  const isPaperToNight = direction === 'paper-to-night';

  return (
    <div className={`relative w-full overflow-hidden select-none pointer-events-none ${className}`}>
      {/* Torn Jagged Edge SVG Mask / Path */}
      <div className="relative w-full">
        <svg
          viewBox="0 0 1440 48"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-8 md:h-12 block"
          preserveAspectRatio="none"
        >
          {/* Shadow layer */}
          <path
            d="M0 0 L40 12 L80 4 L130 16 L190 6 L250 18 L310 8 L370 20 L440 6 L510 18 L580 8 L650 22 L720 10 L790 24 L860 12 L930 22 L1000 8 L1070 20 L1140 10 L1210 24 L1280 8 L1350 20 L1400 10 L1440 18 V48 H0 Z"
            fill="rgba(0, 0, 0, 0.35)"
            transform="translate(0, 4)"
          />
          {/* Main Paper Edge */}
          <path
            d="M0 0 L40 12 L80 4 L130 16 L190 6 L250 18 L310 8 L370 20 L440 6 L510 18 L580 8 L650 22 L720 10 L790 24 L860 12 L930 22 L1000 8 L1070 20 L1140 10 L1210 24 L1280 8 L1350 20 L1400 10 L1440 18 V48 H0 Z"
            fill={isPaperToNight ? '#0B1220' : '#F6F3EA'}
          />
        </svg>
      </div>

      {/* Optional captions */}
      {(caption || subcaption) && (
        <div className={`w-full py-2 px-6 flex flex-col md:flex-row items-center justify-between text-[11px] font-mono tracking-widest uppercase pointer-events-auto ${
          isPaperToNight ? 'bg-[#0B1220] text-slate-400 border-b border-slate-800' : 'bg-[#FAF7F0] text-[#1F2A44] border-b border-[#CDC5B4]'
        }`}>
          {caption && <span>{caption}</span>}
          {subcaption && <span className="opacity-75">{subcaption}</span>}
        </div>
      )}
    </div>
  );
};
