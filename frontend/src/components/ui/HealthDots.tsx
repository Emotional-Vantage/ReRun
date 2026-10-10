import React, { useEffect, useState } from 'react';
import { fetchHealth } from '../../api/client';
import type { HealthResponse } from '../../api/types';

export const HealthDots: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth({ ok: false, docker: false, llm_primary: false, llm_fallback: false }));
  }, []);

  return (
    <div className="flex items-center gap-2 text-xs font-mono">
      {/* Docker status */}
      <div
        className="flex items-center gap-1.5 px-2 py-1 rounded bg-[#FAF7F0] border border-[#CDC5B4] shadow-sm"
        title={health?.docker ? 'Docker daemon running & isolated' : 'Docker daemon offline'}
      >
        <span
          className={`w-2 h-2 rounded-full ${
            health?.docker ? 'bg-emerald-500 shadow-[0_0_8px_#22c55e]' : 'bg-red-500'
          }`}
        />
        <span className="text-[#1F2A44] font-medium text-[11px]">Docker</span>
      </div>

      {/* LLM status */}
      <div
        className="flex items-center gap-1.5 px-2 py-1 rounded bg-[#FAF7F0] border border-[#CDC5B4] shadow-sm"
        title={health?.llm_primary ? 'LLM endpoint reachable' : 'LLM endpoint offline'}
      >
        <span
          className={`w-2 h-2 rounded-full ${
            health?.llm_primary ? 'bg-emerald-500 shadow-[0_0_8px_#22c55e]' : 'bg-red-500'
          }`}
        />
        <span className="text-[#1F2A44] font-medium text-[11px]">LLM</span>
      </div>
    </div>
  );
};
