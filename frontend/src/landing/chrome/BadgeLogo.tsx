import React from 'react';

export const BadgeLogo: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <div
      className={`relative w-[50px] h-[58px] border border-current flex flex-col items-center justify-between p-1.5 select-none transition-colors duration-300 ${className}`}
      title="Rerun · Autonomous Reproduction"
    >
      {/* Mountain-in-loop signature mark */}
      <svg
        viewBox="0 0 40 28"
        className="w-8 h-5 stroke-current fill-none"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {/* Mountain ridge */}
        <path d="M4 22 L14 8 L22 18 L27 12 L36 22 Z" fill="currentColor" fillOpacity="0.15" />
        <path d="M4 22 L14 8 L22 18 L27 12 L36 22" />
        {/* Retracing loop around peak */}
        <path
          d="M8 14 C12 6, 26 4, 30 14 C33 21, 23 25, 18 20 C14 16, 17 10, 23 10"
          strokeDasharray="2 2"
          opacity="0.85"
        />
      </svg>
      {/* Rerun mark text */}
      <div className="flex items-center justify-between w-full px-0.5 text-[8px] font-mono tracking-widest uppercase opacity-80">
        <span className="font-bold">R</span>
        <span className="text-[6px] tracking-normal">LAB</span>
      </div>
    </div>
  );
};
