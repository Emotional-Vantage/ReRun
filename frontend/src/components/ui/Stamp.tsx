import React from 'react';

interface StampProps {
  status: string;
  afterNPatches?: number;
  className?: string;
}

export const Stamp: React.FC<StampProps> = ({
  status,
  afterNPatches,
  className = '',
}) => {
  const normStatus = (status || 'UNKNOWN').toUpperCase();

  const isSuccess = normStatus === 'REPRODUCED';
  const isFailed = normStatus === 'NOT_REPRODUCED';
  const isPartial = normStatus === 'PARTIALLY_REPRODUCED';

  const borderColor = isSuccess
    ? 'border-emerald-600 text-emerald-600'
    : isFailed
    ? 'border-red-600 text-red-600'
    : isPartial
    ? 'border-amber-600 text-amber-600'
    : 'border-slate-500 text-slate-500';

  return (
    <div
      className={`inline-block border-2 md:border-[3px] border-dashed rounded px-4 py-2 transform -rotate-3 select-none uppercase tracking-widest font-mono ${borderColor} ${className}`}
      style={{
        boxShadow: 'inset 0 0 10px rgba(0,0,0,0.05)',
      }}
    >
      <div className="flex flex-col items-center justify-center text-center leading-none">
        <span className="text-[9px] tracking-[0.2em] opacity-80 mb-1">RERUN LAB · VERIFIED</span>
        <span className="text-base md:text-xl font-black tracking-wider">
          {normStatus.replace(/_/g, ' ')}
        </span>
        {afterNPatches !== undefined && afterNPatches > 0 && (
          <span className="text-[10px] tracking-normal font-sans font-medium mt-1 opacity-90 lowercase italic">
            after {afterNPatches} approved patch{afterNPatches > 1 ? 'es' : ''}
          </span>
        )}
      </div>
    </div>
  );
};
