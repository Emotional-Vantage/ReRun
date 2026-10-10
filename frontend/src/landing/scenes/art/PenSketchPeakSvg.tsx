import React from 'react';

export const PenSketchPeakSvg: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <svg
      viewBox="0 0 500 400"
      className={`select-none pointer-events-none fill-none stroke-current ${className}`}
      aria-hidden="true"
    >
      {/* Mountain Contour Silhouettes */}
      <path
        d="M 50 350 L 180 120 L 260 210 L 340 90 L 460 350 Z"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M 180 120 L 220 350 M 340 90 L 320 350 M 260 210 L 250 350"
        strokeWidth="1.2"
        strokeOpacity="0.7"
      />

      {/* Hand-drawn Hatching Shadows on left & right facets */}
      <g strokeWidth="0.8" strokeOpacity="0.55">
        {/* Summit 1 hatching */}
        <line x1="180" y1="120" x2="160" y2="150" />
        <line x1="185" y1="135" x2="165" y2="165" />
        <line x1="190" y1="150" x2="168" y2="182" />
        <line x1="195" y1="168" x2="172" y2="200" />
        <line x1="202" y1="185" x2="176" y2="220" />
        <line x1="208" y1="205" x2="180" y2="242" />
        <line x1="214" y1="228" x2="184" y2="268" />
        <line x1="218" y1="250" x2="188" y2="295" />
        <line x1="222" y1="275" x2="192" y2="322" />

        {/* Summit 2 hatching */}
        <line x1="340" y1="90" x2="355" y2="125" />
        <line x1="338" y1="110" x2="365" y2="148" />
        <line x1="335" y1="130" x2="375" y2="172" />
        <line x1="332" y1="152" x2="388" y2="198" />
        <line x1="328" y1="175" x2="400" y2="225" />
        <line x1="325" y1="200" x2="415" y2="255" />
        <line x1="322" y1="228" x2="430" y2="288" />
        <line x1="320" y1="260" x2="445" y2="325" />
      </g>
    </svg>
  );
};
