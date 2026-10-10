import React from 'react';

/**
 * Mountain ridges SVG inline art with rim lighting and subtle crack lines
 * Color tokens:
 * Far: --mtn-far (#3E3B52)
 * Mid-far: --mtn-clay (#94705A)
 * Mid: --mtn-tan (#8D7765)
 * Near: --mtn-rust (#8A5B45)
 */
export const MountainRidgesSvg: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <svg
      viewBox="0 0 1920 600"
      preserveAspectRatio="none"
      className={`w-full h-full pointer-events-none ${className}`}
      aria-hidden="true"
    >
      <defs>
        {/* Soft mist gradient between ridges */}
        <linearGradient id="mist-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#4A5D80" stopOpacity="0.4" />
          <stop offset="60%" stopColor="#CDC8BA" stopOpacity="0.15" />
          <stop offset="100%" stopColor="#3E3B52" stopOpacity="0" />
        </linearGradient>

        {/* Rim light filter */}
        <filter id="rim-glow" x="-10%" y="-10%" width="120%" height="120%">
          <feDropShadow dx="0" dy="-1.5" stdDeviation="1" floodColor="#F1ECE0" floodOpacity="0.35" />
        </filter>
      </defs>

      {/* Ridge 1: Far Mountain Range */}
      <g>
        <path
          d="M0 320 Q 240 210, 480 260 T 960 220 T 1440 270 T 1920 230 L 1920 600 L 0 600 Z"
          fill="var(--mtn-far)"
        />
        {/* Ridge 1 Rim Light */}
        <path
          d="M0 320 Q 240 210, 480 260 T 960 220 T 1440 270 T 1920 230"
          stroke="#F1ECE0"
          strokeWidth="1.2"
          strokeOpacity="0.25"
          fill="none"
        />
      </g>

      {/* Mist layer 1 */}
      <rect x="0" y="260" width="1920" height="120" fill="url(#mist-grad)" opacity="0.3" />

      {/* Ridge 2: Mid-Far Range (Clay) */}
      <g>
        <path
          d="M0 370 Q 200 290, 420 330 Q 640 370, 850 280 Q 1120 330, 1380 290 Q 1650 360, 1920 310 L 1920 600 L 0 600 Z"
          fill="var(--mtn-clay)"
        />
        <path
          d="M0 370 Q 200 290, 420 330 Q 640 370, 850 280 Q 1120 330, 1380 290 Q 1650 360, 1920 310"
          stroke="#F1ECE0"
          strokeWidth="1.5"
          strokeOpacity="0.3"
          fill="none"
        />
        {/* Subtle ridge hatch lines */}
        <path
          d="M420 330 L 450 370 M 850 280 L 890 350 M 850 280 L 820 340 M 1380 290 L 1410 360"
          stroke="#3E3B52"
          strokeWidth="1"
          strokeOpacity="0.3"
        />
      </g>

      {/* Ridge 3: Mid Range (Tan) */}
      <g>
        <path
          d="M0 430 Q 260 360, 520 410 Q 760 330, 1020 390 Q 1280 340, 1540 400 Q 1740 350, 1920 380 L 1920 600 L 0 600 Z"
          fill="var(--mtn-tan)"
        />
        <path
          d="M0 430 Q 260 360, 520 410 Q 760 330, 1020 390 Q 1280 340, 1540 400 Q 1740 350, 1920 380"
          stroke="#F1ECE0"
          strokeWidth="1.5"
          strokeOpacity="0.35"
          fill="none"
        />
        {/* Hatch lines */}
        <path
          d="M520 410 L 550 470 M 760 330 L 740 420 M 1020 390 L 1050 460 M 1540 400 L 1570 470"
          stroke="#5A3A28"
          strokeWidth="1"
          strokeOpacity="0.25"
        />
      </g>

      {/* Ridge 4: Near Range (Rust) */}
      <g>
        <path
          d="M0 500 Q 220 450, 480 480 Q 720 440, 960 490 Q 1200 430, 1480 470 Q 1720 420, 1920 450 L 1920 600 L 0 600 Z"
          fill="var(--mtn-rust)"
        />
        <path
          d="M0 500 Q 220 450, 480 480 Q 720 440, 960 490 Q 1200 430, 1480 470 Q 1720 420, 1920 450"
          stroke="#F1ECE0"
          strokeWidth="1.6"
          strokeOpacity="0.4"
          fill="none"
        />
      </g>

      {/* Foreground Ridge (Very Dark Navy/Charcoal to blend into the base) */}
      <path
        d="M0 550 Q 300 520, 600 550 Q 900 510, 1200 545 Q 1500 505, 1920 540 L 1920 600 L 0 600 Z"
        fill="#14203B"
        opacity="0.95"
      />
    </svg>
  );
};
