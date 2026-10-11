import React from 'react';
import { ShieldAlert } from 'lucide-react';
import type { ProjectBudgets } from '../../api/types';

interface BudgetBarProps {
  budgets?: ProjectBudgets;
}

export const BudgetBar: React.FC<BudgetBarProps> = ({ budgets }) => {
  const stepsUsed = budgets?.steps_used || 0;
  const patchesUsed = budgets?.patches_used || 0;
  const maxSteps = budgets?.max_steps ?? null;
  const maxPatches = budgets?.max_patches ?? null;

  const stepPct = maxSteps ? Math.min(100, Math.round((stepsUsed / maxSteps) * 100)) : 0;
  const patchPct = maxPatches ? Math.min(100, Math.round((patchesUsed / maxPatches) * 100)) : 0;
  const isStepWarning = maxSteps !== null && stepPct >= 80;

  return (
    <div className="flex flex-wrap items-center gap-6 text-xs font-mono bg-[#FAF7F0] border border-[#CDC5B4] rounded-lg px-4 py-2.5 shadow-sm text-[#1F2A44]">
      {/* Steps gauge */}
      <div className="flex items-center gap-2.5 flex-1 min-w-[11.25rem]">
        <div className="flex items-center justify-between w-full">
          <span className="text-[#4A5470]">Step Budget:</span>
          <span className={`font-semibold ${isStepWarning ? 'text-amber-700' : 'text-[#1F2A44]'}`}>
            {stepsUsed}{maxSteps !== null ? ` / ${maxSteps}` : ''}
          </span>
        </div>
        {maxSteps !== null && (
          <div className="w-24 h-2 bg-[#E5DFD3] rounded-full overflow-hidden border border-[#CDC5B4]">
            <div
              className={`h-full transition-all duration-300 rounded-full ${
                isStepWarning ? 'bg-amber-600' : 'bg-rust'
              }`}
              style={{ width: `${stepPct}%` }}
            />
          </div>
        )}
      </div>

      {/* Patches gauge */}
      <div className="flex items-center gap-2.5 flex-1 min-w-[11.25rem]">
        <div className="flex items-center justify-between w-full">
          <span className="text-[#4A5470]">Patch Budget:</span>
          <span className="text-[#1F2A44] font-semibold">
            {patchesUsed}{maxPatches !== null ? ` / ${maxPatches}` : ''}
          </span>
        </div>
        {maxPatches !== null && (
          <div className="w-20 h-2 bg-[#E5DFD3] rounded-full overflow-hidden border border-[#CDC5B4]">
            <div
              className="h-full bg-teal-600 transition-all duration-300 rounded-full"
              style={{ width: `${patchPct}%` }}
            />
          </div>
        )}
      </div>

      {isStepWarning && (
        <div className="flex items-center gap-1.5 text-amber-700 text-[11px] font-bold animate-pulse">
          <ShieldAlert className="w-4 h-4" />
          <span>Approaching step limit (80%)</span>
        </div>
      )}
    </div>
  );
};
