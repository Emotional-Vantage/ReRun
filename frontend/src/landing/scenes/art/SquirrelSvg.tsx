import React from 'react';

export const SquirrelSvg: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <svg
      viewBox="0 0 120 120"
      className={`w-24 h-24 select-none pointer-events-none overflow-visible ${className}`}
      aria-hidden="true"
    >
      <style>{`
        @keyframes squirrelTail {
          0%, 100% {
            transform: rotate(0deg);
          }
          18% {
            transform: rotate(-6deg) scale(1.02);
          }
          24% {
            transform: rotate(4deg);
          }
          30% {
            transform: rotate(-3.5deg);
          }
          36% {
            transform: rotate(1deg);
          }
          42% {
            transform: rotate(0deg);
          }
          75% {
            transform: rotate(-2deg);
          }
          82% {
            transform: rotate(0.5deg);
          }
        }

        @keyframes squirrelHead {
          0%, 100% {
            transform: rotate(0deg);
          }
          22% {
            transform: rotate(-3.5deg);
          }
          36% {
            transform: rotate(-3.5deg);
          }
          48% {
            transform: rotate(2.5deg);
          }
          62% {
            transform: rotate(0deg);
          }
          85% {
            transform: rotate(2deg);
          }
        }

        @keyframes squirrelPaws {
          0%, 100% {
            transform: translate(0, 0);
          }
          20%, 30% {
            transform: translate(-0.5px, -1px);
          }
          25% {
            transform: translate(0.5px, 0.5px);
          }
        }

        .sq-tail {
          animation: squirrelTail 5.5s cubic-bezier(0.34, 1.3, 0.64, 1) infinite;
          transform-origin: 54px 86px;
          will-change: transform;
        }

        .sq-head {
          animation: squirrelHead 5.5s ease-in-out infinite;
          transform-origin: 42px 60px;
          will-change: transform;
        }

        .sq-paws {
          animation: squirrelPaws 5.5s ease-in-out infinite;
          transform-origin: 30px 71px;
          will-change: transform;
        }

        @media (prefers-reduced-motion: reduce) {
          .sq-tail, .sq-head, .sq-paws {
            animation: none !important;
          }
        }
      `}</style>

      {/* Branch underneath */}
      <path d="M 0 105 Q 60 102, 120 100" stroke="#5A3A28" strokeWidth="6" strokeLinecap="round" />

      {/* Bushy Tail (Curling up and over back) */}
      <g className="sq-tail">
        <path
          d="M 50 90 C 85 95, 115 80, 110 45 C 105 20, 85 10, 75 18 C 65 25, 75 45, 80 55 C 85 65, 75 80, 52 82 Z"
          fill="var(--squirrel, #B05A30)"
        />
        {/* Tail fluff highlight */}
        <path
          d="M 105 45 C 102 28, 88 20, 80 25"
          stroke="#E89650"
          strokeWidth="2.5"
          strokeLinecap="round"
          fill="none"
        />
      </g>

      {/* Body & Foot */}
      <ellipse cx="48" cy="78" rx="16" ry="20" fill="var(--squirrel, #B05A30)" />
      {/* Cream Chest */}
      <ellipse cx="40" cy="80" rx="9" ry="14" fill="#F4F1E8" />
      {/* Foot perched on branch */}
      <ellipse cx="45" cy="98" rx="7" ry="4" fill="#8D5528" />

      {/* Head, Ear, Eye */}
      <g className="sq-head">
        <circle cx="42" cy="54" r="13" fill="var(--squirrel, #B05A30)" />
        {/* Ear */}
        <path d="M 44 43 L 49 32 L 53 44 Z" fill="var(--squirrel, #B05A30)" />
        <path d="M 46 41 L 49 36 L 51 42 Z" fill="#E89650" />

        {/* Eye & Nose */}
        <circle cx="36" cy="52" r="2.2" fill="#1F2A44" />
        <circle cx="35" cy="51" r="0.6" fill="#FFFFFF" />
        <circle cx="30" cy="56" r="1.5" fill="#1F2A44" />
      </g>

      {/* Paws holding acorn */}
      <g className="sq-paws">
        <ellipse cx="32" cy="72" rx="4" ry="3" fill="#B05A30" />
        {/* Acorn */}
        <ellipse cx="28" cy="70" rx="4" ry="5" fill="#A8693A" />
        <path d="M 24 67 Q 28 64, 32 67" stroke="#5A3A28" strokeWidth="1.5" fill="#5A3A28" />
      </g>
    </svg>
  );
};
