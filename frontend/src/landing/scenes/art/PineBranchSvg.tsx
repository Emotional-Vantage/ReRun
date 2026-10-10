import React from 'react';

export const PineBranchSvg: React.FC<{ className?: string; flipped?: boolean }> = ({
  className = '',
  flipped = false,
}) => {
  return (
    <svg
      viewBox="0 0 160 120"
      className={`w-32 h-24 select-none pointer-events-none overflow-visible ${
        flipped ? '-scale-x-100' : ''
      } ${className}`}
      aria-hidden="true"
    >
      <style>{`
        @keyframes pineBoughSway {
          0%, 100% {
            transform: rotate(0deg);
          }
          40% {
            transform: rotate(-2.2deg) translateY(1px);
          }
          75% {
            transform: rotate(0.8deg);
          }
        }

        @keyframes pineConeSway1 {
          0%, 100% {
            transform: translate(48px, 28px) rotate(15deg);
          }
          45% {
            transform: translate(48px, 28px) rotate(20deg);
          }
          80% {
            transform: translate(48px, 28px) rotate(12deg);
          }
        }

        @keyframes pineConeSway2 {
          0%, 100% {
            transform: translate(78px, 38px) rotate(25deg);
          }
          50% {
            transform: translate(78px, 38px) rotate(31deg);
          }
          85% {
            transform: translate(78px, 38px) rotate(22deg);
          }
        }

        .pine-bough {
          animation: pineBoughSway 6.4s ease-in-out infinite;
          transform-origin: 0px 10px;
          will-change: transform;
        }

        .pine-cone-1 {
          animation: pineConeSway1 6.4s ease-in-out infinite;
          will-change: transform;
        }

        .pine-cone-2 {
          animation: pineConeSway2 6.4s ease-in-out infinite;
          will-change: transform;
        }

        @media (prefers-reduced-motion: reduce) {
          .pine-bough, .pine-cone-1, .pine-cone-2 {
            animation: none !important;
          }
        }
      `}</style>

      <g className="pine-bough">
        {/* Wooden branch */}
        <path
          d="M 0 10 Q 50 25, 90 20 T 150 15"
          stroke="#5A3A28"
          strokeWidth="5"
          strokeLinecap="round"
          fill="none"
        />
        <path
          d="M 60 22 Q 85 45, 110 55"
          stroke="#5A3A28"
          strokeWidth="3.5"
          strokeLinecap="round"
          fill="none"
        />

        {/* Pine Needles clusters (Pine green #2F5A3A) */}
        <g stroke="#2F5A3A" strokeWidth="1.8" strokeLinecap="round">
          {/* Main branch cluster */}
          <line x1="20" y1="14" x2="10" y2="35" />
          <line x1="25" y1="16" x2="20" y2="40" />
          <line x1="30" y1="18" x2="30" y2="42" />
          <line x1="40" y1="20" x2="35" y2="48" />
          <line x1="45" y1="21" x2="48" y2="50" />
          <line x1="50" y1="22" x2="60" y2="48" />

          {/* Second branch cluster */}
          <line x1="70" y1="30" x2="58" y2="55" />
          <line x1="75" y1="34" x2="68" y2="60" />
          <line x1="80" y1="38" x2="78" y2="65" />
          <line x1="88" y1="42" x2="88" y2="68" />
          <line x1="95" y1="47" x2="100" y2="70" />
          <line x1="102" y1="51" x2="112" y2="72" />

          {/* Tip cluster */}
          <line x1="110" y1="20" x2="125" y2="8" />
          <line x1="120" y1="18" x2="138" y2="10" />
          <line x1="130" y1="17" x2="152" y2="12" />
          <line x1="140" y1="16" x2="158" y2="20" />
        </g>

        {/* Pine Cones (Warm Amber/Brown #A8693A) */}
        {/* Cone 1 */}
        <g className="pine-cone-1">
          <ellipse cx="10" cy="18" rx="8" ry="14" fill="#A8693A" stroke="#5A3A28" strokeWidth="1" />
          {/* Cone scales */}
          <path d="M 4 10 Q 10 14, 16 10" stroke="#5A3A28" strokeWidth="1" fill="none" />
          <path d="M 3 16 Q 10 20, 17 16" stroke="#5A3A28" strokeWidth="1" fill="none" />
          <path d="M 4 22 Q 10 26, 16 22" stroke="#5A3A28" strokeWidth="1" fill="none" />
          <path d="M 7 28 Q 10 30, 13 28" stroke="#5A3A28" strokeWidth="1" fill="none" />
        </g>

        {/* Cone 2 */}
        <g className="pine-cone-2">
          <ellipse cx="8" cy="14" rx="7" ry="12" fill="#8D5528" stroke="#4A2F1C" strokeWidth="1" />
          <path d="M 3 8 Q 8 12, 13 8" stroke="#4A2F1C" strokeWidth="1" fill="none" />
          <path d="M 2 14 Q 8 18, 14 14" stroke="#4A2F1C" strokeWidth="1" fill="none" />
          <path d="M 4 20 Q 8 23, 12 20" stroke="#4A2F1C" strokeWidth="1" fill="none" />
        </g>
      </g>
    </svg>
  );
};
