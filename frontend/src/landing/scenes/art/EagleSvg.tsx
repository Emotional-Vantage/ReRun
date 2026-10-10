import React from 'react';

export const EagleSvg: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <svg
      viewBox="0 0 160 120"
      className={`w-28 h-20 select-none pointer-events-none overflow-visible ${className}`}
      aria-hidden="true"
    >
      <style>{`
        @keyframes eagleSoar {
          0%, 100% {
            transform: translate3d(0, 0, 0) rotate(-1deg);
          }
          20% {
            transform: translate3d(3px, -6px, 0) rotate(-3.5deg);
          }
          45% {
            transform: translate3d(1px, -2px, 0) rotate(-0.5deg);
          }
          70% {
            transform: translate3d(-3px, 5px, 0) rotate(1.5deg);
          }
          85% {
            transform: translate3d(-1px, 2px, 0) rotate(0deg);
          }
        }

        @keyframes eagleLeftWing {
          0%, 100% {
            transform: rotate(0deg);
          }
          25% {
            transform: rotate(-4deg) scaleY(1.03);
          }
          65% {
            transform: rotate(2.5deg) scaleY(0.97);
          }
        }

        @keyframes eagleRightWing {
          0%, 100% {
            transform: rotate(0deg);
          }
          25% {
            transform: rotate(4deg) scaleY(1.03);
          }
          65% {
            transform: rotate(-2.5deg) scaleY(0.97);
          }
        }

        @keyframes eagleTail {
          0%, 100% {
            transform: rotate(0deg);
          }
          30% {
            transform: rotate(3deg);
          }
          75% {
            transform: rotate(-2.5deg);
          }
        }

        .eagle-glider {
          animation: eagleSoar 4.8s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
          transform-origin: 80px 56px;
          will-change: transform;
        }

        .eagle-wing-l {
          animation: eagleLeftWing 4.8s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
          transform-origin: 75px 56px;
          will-change: transform;
        }

        .eagle-wing-r {
          animation: eagleRightWing 4.8s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
          transform-origin: 88px 56px;
          will-change: transform;
        }

        .eagle-tail {
          animation: eagleTail 4.8s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
          transform-origin: 80px 68px;
          will-change: transform;
        }

        @media (prefers-reduced-motion: reduce) {
          .eagle-glider, .eagle-wing-l, .eagle-wing-r, .eagle-tail {
            animation: none !important;
          }
        }
      `}</style>

      <g className="eagle-glider">
        {/* Left Wing & Primary Feathers */}
        <g className="eagle-wing-l">
          <path
            d="M 12 18 C 35 15, 60 40, 75 58 C 72 45, 65 30, 60 15 C 57 8, 54 2, 50 0 C 42 12, 30 20, 12 18 Z"
            fill="#3D2B1F"
          />
          <path
            d="M 12 18 L 22 26 L 16 32 L 28 38 L 24 44 L 40 48 L 56 52"
            stroke="#271B14"
            strokeWidth="1.5"
            fill="#4A3525"
          />
        </g>

        {/* Right Wing & Primary Feathers */}
        <g className="eagle-wing-r">
          <path
            d="M 152 24 C 130 18, 102 42, 88 58 C 92 42, 100 26, 108 12 C 112 5, 118 0, 122 0 C 132 14, 142 22, 152 24 Z"
            fill="#3D2B1F"
          />
          <path
            d="M 152 24 L 140 30 L 144 38 L 132 42 L 134 50 L 118 52 L 104 54"
            stroke="#271B14"
            strokeWidth="1.5"
            fill="#4A3525"
          />
        </g>

        {/* Tail Feathers (white / cream) */}
        <g className="eagle-tail">
          <polygon
            points="76,68 84,68 96,82 64,82"
            fill="#F4F1E8"
            stroke="#D9D4C6"
            strokeWidth="1"
          />
        </g>

        {/* Body */}
        <ellipse cx="80" cy="56" rx="14" ry="18" fill="#4A3525" />

        {/* Head & Neck (white / cream) */}
        <circle cx="70" cy="46" r="8" fill="#F4F1E8" />

        {/* Beak & Eye (yellow/amber) */}
        <polygon points="62,45 66,43 66,49" fill="#E89650" />
        <circle cx="68" cy="45" r="1.2" fill="#1F2A44" />

        {/* Talons (yellow/amber) */}
        <line
          x1="75"
          y1="72"
          x2="73"
          y2="78"
          stroke="#E89650"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <line
          x1="85"
          y1="72"
          x2="87"
          y2="78"
          stroke="#E89650"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </g>
    </svg>
  );
};
