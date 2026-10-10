import React from 'react';
import { Check } from 'lucide-react';

interface PhaseBarProps {
  currentPhase: string;
}

const PHASES = [
  { id: 'INGEST', label: 'Ingest', desc: 'Scan repository & allow-list check' },
  { id: 'ANALYZE', label: 'Analyze', desc: 'Read paper PDF & extract claims' },
  { id: 'PLAN', label: 'Plan', desc: 'Synthesize run command & seed list' },
  { id: 'PREFLIGHT', label: 'Preflight', desc: 'Inspect GPU & environment readiness' },
  { id: 'RUN', label: 'Run', desc: 'Execute container in locked sandbox' },
  { id: 'DIAGNOSE', label: 'Diagnose', desc: 'Analyze errors or config drift' },
  { id: 'CRITIC_REVIEW', label: 'Review', desc: 'Independent 9-point Critic review' },
  { id: 'APPROVAL', label: 'Approve', desc: 'Human-in-the-loop patch approval' },
  { id: 'VALIDATE', label: 'Validate', desc: 'Parse output metrics & compute stats' },
  { id: 'REPORT', label: 'Report', desc: 'Generate verified reproduction report' },
];

export const PhaseBar: React.FC<PhaseBarProps> = ({ currentPhase }) => {
  const normPhase = (currentPhase || 'INGEST').toUpperCase();

  // Find index of current phase
  let activeIndex = PHASES.findIndex((p) => p.id === normPhase);
  if (normPhase === 'DONE') activeIndex = PHASES.length;
  if (normPhase === 'CLAIMS_CONFIRM') activeIndex = 1;
  if (normPhase === 'PATCH_PROPOSE' || normPhase === 'POLICY_CHECK') activeIndex = 5;
  if (normPhase === 'PATCH_APPLY') activeIndex = 7;
  if (normPhase === 'OBSERVE' || normPhase === 'COMPARE') activeIndex = 4;
  if (normPhase === 'STATUS') activeIndex = 8;

  return (
    <div className="w-full bg-[#E5DFD3] border-b border-[#CDC5B4] px-4 py-3 overflow-x-auto select-none text-[#1F2A44] font-mono shadow-sm">
      <div className="max-w-7xl mx-auto flex items-center justify-between min-w-[760px] gap-2">
        {PHASES.map((p, idx) => {
          const isDone = idx < activeIndex;
          const isCurrent = idx === activeIndex;

          return (
            <div key={p.id} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center shrink-0">
                <div
                  className={`w-7 h-7 rounded-sm flex items-center justify-center font-mono text-xs font-bold transition-all duration-300 ${
                    isCurrent
                      ? 'bg-rust text-[#FAF7F0] shadow-[0_0_12px_rgba(184,87,47,0.4)] scale-110 ring-2 ring-rust/50'
                      : isDone
                      ? 'bg-[#FAF7F0] text-rust border border-[#CDC5B4] shadow-sm font-bold'
                      : 'bg-[#D9D4C6] text-[#4A5470] border border-[#CDC5B4]'
                  }`}
                  style={{
                    clipPath: 'polygon(0% 2px, 2px 0%, calc(100% - 2px) 0%, 100% 2px, 100% calc(100% - 2px), calc(100% - 2px) 100%, 2px 100%, 0% calc(100% - 2px))',
                  }}
                  title={`${p.label}: ${p.desc}`}
                >
                  {isDone ? <Check className="w-3.5 h-3.5 stroke-[3] text-rust" /> : idx + 1}
                </div>

                <span
                  className={`mt-1.5 text-[10px] md:text-[11px] font-mono tracking-wider transition-colors uppercase ${
                    isCurrent
                      ? 'text-rust font-bold'
                      : isDone
                      ? 'text-[#1F2A44] font-semibold'
                      : 'text-[#4A5470]/70'
                  }`}
                >
                  {p.label}
                </span>
              </div>

              {idx < PHASES.length - 1 && (
                <div
                  className={`h-0.5 flex-1 mx-2 -mt-4 transition-colors ${
                    idx < activeIndex ? 'bg-rust/80' : 'bg-[#CDC5B4]'
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
